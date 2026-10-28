"""Visual-Pipeline: pro Szene ein Clip oder Bild - aus austauschbaren Anbietern.

Anbieter (Reihenfolge in config.yaml unter visuals.providers):
  pexels      - Stock-Videos (Pexels API, kostenloser Key: STOCK_API_KEY)
  local       - eigene Dateien in assets/videos und assets/images
  ai_image    - KI-Bilder via OpenAI Images API (IMAGE_API_KEY)
  ai_video    - ADAPTER, noch NICHT implementiert (siehe AIVideoProvider)
  procedural  - lokal per FFmpeg erzeugte dunkle, atmosphaerische Hintergruende (kommt nie ohne Ergebnis)

`procedural` wird automatisch als letzte Rueckfalloption angehaengt, damit die Pipeline nie an
fehlenden Visuals scheitert.
"""
from __future__ import annotations

import base64
import hashlib
import random
import re
import zlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Set, Type

import requests

from config import Config
from .logger import log
from .models import ContentPackage, Scene, VisualAsset
from .utils import PipelineError, download_file, http_get, retry, run_ffmpeg

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class VisualProvider(ABC):
    name = "base"

    def __init__(self, cfg: Config, used: Set[str]) -> None:
        self.cfg = cfg
        self.used = used                      # bereits verwendete Quellen (Wiederholungen vermeiden)

    @abstractmethod
    def fetch(self, scene: Scene, dest_dir: Path, min_seconds: float) -> Optional[VisualAsset]:
        """Liefert ein Asset fuer die Szene oder None, wenn nichts Passendes gefunden wurde."""

    def style_prompt(self, scene: Scene) -> str:
        return f"{scene.visual_prompt}. {self.cfg.style.visual_suffix}"


# ------------------------------------------------------------------ Pexels
class PexelsProvider(VisualProvider):
    name = "pexels"
    API = "https://api.pexels.com/videos/search"

    def fetch(self, scene: Scene, dest_dir: Path, min_seconds: float) -> Optional[VisualAsset]:
        key = self.cfg.stock_api_key
        if not key:
            raise PipelineError("STOCK_API_KEY fehlt (Pexels) - Anbieter wird uebersprungen")
        words = scene.search_query.split()
        queries = [scene.search_query] + ([" ".join(words[:2])] if len(words) > 2 else [])
        for query in queries:
            asset = self._search(query, key, scene, dest_dir, min_seconds)
            if asset:
                return asset
        return None

    @retry(attempts=2, delay=2)
    def _search(self, query: str, key: str, scene: Scene, dest_dir: Path, min_seconds: float) -> Optional[VisualAsset]:
        resp = requests.get(self.API, headers={"Authorization": key},
                            params={"query": query, "orientation": "portrait", "size": "medium",
                                    "per_page": self.cfg.visuals.pexels_per_query}, timeout=20)
        if resp.status_code in (401, 403):
            raise PipelineError("Pexels verweigert Zugriff: STOCK_API_KEY pruefen")
        resp.raise_for_status()
        for video in resp.json().get("videos", []):
            vid = f"pexels:{video['id']}"
            if vid in self.used or video.get("duration", 0) < min_seconds:
                continue
            files = [f for f in video.get("video_files", [])
                     if f.get("file_type") == "video/mp4" and (f.get("height") or 0) > (f.get("width") or 0)]
            if not files:
                continue
            # moeglichst nah an 1920 hoch (aber nicht riesig)
            best = min(files, key=lambda f: abs((f.get("height") or 0) - 1920))
            dest = self.cfg.cache_dir / "pexels" / f"{video['id']}.mp4"
            if not dest.exists():
                download_file(best["link"], dest)
            self.used.add(vid)
            return VisualAsset(scene.index, dest, "video", self.name, query,
                               credit=f"Pexels / {video.get('user', {}).get('name', '')} {video.get('url', '')}".strip())
        return None


# ------------------------------------------------------------------ Lokal
class LocalProvider(VisualProvider):
    name = "local"

    def fetch(self, scene: Scene, dest_dir: Path, min_seconds: float) -> Optional[VisualAsset]:
        files: List[Path] = []
        for d in self.cfg.visuals.local_dirs:
            folder = self.cfg.path(d)
            if folder.is_dir():
                files += [p for p in sorted(folder.rglob("*")) if p.suffix.lower() in VIDEO_EXT | IMAGE_EXT]
        files = [p for p in files if str(p) not in self.used] or files
        if not files:
            return None
        keywords = {w.lower() for w in re.findall(r"\w+", scene.search_query)}

        def score(p: Path) -> int:
            return len(keywords & {w.lower() for w in re.findall(r"\w+", p.stem)})

        best = max(files, key=lambda p: (score(p), -(zlib.crc32(f'{p.name}{scene.index}'.encode()) % 1000)))
        self.used.add(str(best))
        kind = "video" if best.suffix.lower() in VIDEO_EXT else "image"
        return VisualAsset(scene.index, best, kind, self.name, scene.search_query)


# ------------------------------------------------------------------ KI-Bild (OpenAI)
class AIImageProvider(VisualProvider):
    name = "ai_image"

    def fetch(self, scene: Scene, dest_dir: Path, min_seconds: float) -> Optional[VisualAsset]:
        key = self.cfg.image_api_key
        if not key:
            raise PipelineError("IMAGE_API_KEY fehlt - KI-Bilder werden uebersprungen")
        prompt = self.style_prompt(scene)
        dest = dest_dir / f"scene_{scene.index:02d}_ai.png"
        cache = self.cfg.cache_dir / "ai_images" / (hashlib.sha1(prompt.encode()).hexdigest()[:16] + ".png")
        if cache.exists():
            return VisualAsset(scene.index, cache, "image", self.name, prompt)
        resp = requests.post("https://api.openai.com/v1/images/generations", timeout=180,
                             headers={"Authorization": f"Bearer {key}"},
                             json={"model": self.cfg.visuals.openai_image_model, "prompt": prompt, "n": 1,
                                   "size": self.cfg.visuals.openai_image_size})
        if resp.status_code in (401, 403):
            raise PipelineError("OpenAI Images verweigert Zugriff: IMAGE_API_KEY pruefen")
        resp.raise_for_status()
        item = resp.json()["data"][0]
        cache.parent.mkdir(parents=True, exist_ok=True)
        if item.get("b64_json"):
            cache.write_bytes(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            download_file(item["url"], cache)
        else:
            raise PipelineError("OpenAI Images lieferte weder b64_json noch url")
        return VisualAsset(scene.index, cache, "image", self.name, prompt)


# ------------------------------------------------------------------ KI-Video (ADAPTER)
class AIVideoProvider(VisualProvider):
    """ADAPTER - NICHT IMPLEMENTIERT.

    Hier kann ein KI-Video-Dienst angebunden werden (z.B. Runway, Luma Dream Machine, Kling, fal.ai,
    Replicate). Ich habe bewusst keine API erfunden. So gehst du vor:

      1. API-Doku des gewaehlten Dienstes lesen (Endpunkt, Auth, Polling auf fertiges Video).
      2. `fetch()` implementieren: self.style_prompt(scene) senden, 9:16 anfordern,
         fertiges Video nach `dest_dir` herunterladen.
      3. Rueckgabe: VisualAsset(scene.index, pfad_zur_mp4, "video", self.name, prompt)
      4. VIDEO_API_KEY in .env setzen und "ai_video" in config.yaml (visuals.providers) eintragen.
    """
    name = "ai_video"

    def fetch(self, scene: Scene, dest_dir: Path, min_seconds: float) -> Optional[VisualAsset]:
        raise NotImplementedError("ai_video ist nur ein Adapter - siehe Docstring in src/visual_generator.py")


# ------------------------------------------------------------------ Prozedural (immer verfuegbar)
class ProceduralProvider(VisualProvider):
    """Dunkle, atmosphaerische Bewegtbild-Hintergruende per FFmpeg (`gradients`-Quelle).

    Dient als sichere Rueckfallebene und fuer den Testmodus. Die Farbwelt folgt dem Dark-Cinematic-Look;
    die Szenenrolle bestimmt die Stimmung (Twist = dunkles Rot, Payoff = warmes Amber, sonst Teal/Blau).
    """
    name = "procedural"
    PALETTES = {
        "twist": ("0x1c060e", "0x8a1f36", "0x0e0408"),
        "payoff": ("0x1a0f05", "0x9a6420", "0x0c0703"),
        "cta": ("0x080e1e", "0x2f5aa0", "0x050810"),
        "default": [
            ("0x061a28", "0x1a7490", "0x040d14"),
            ("0x0c1230", "0x3a4fb0", "0x060818"),
            ("0x120e22", "0x5a3a92", "0x08060f"),
            ("0x072420", "0x20968a", "0x04100e"),
        ],
    }

    def fetch(self, scene: Scene, dest_dir: Path, min_seconds: float) -> Optional[VisualAsset]:
        pal = self.PALETTES.get(scene.role) or self.PALETTES["default"][scene.index % 4]
        seed = scene.index * 7919 + 13
        rnd = random.Random(seed)
        dur = max(min_seconds, scene.duration + 1.5, 4.0)
        dest = dest_dir / f"scene_{scene.index:02d}_procedural.mp4"
        angle = rnd.uniform(0, 1)
        grad = (f"gradients=s=270x480:c0={pal[0]}:c1={pal[1]}:c2={pal[2]}:nb_colors=3:"
                f"x0={int(angle * 270)}:y0=0:x1={int((1 - angle) * 270)}:y1=480:speed=0.03:seed={seed}:"
                f"duration={dur:.2f}:rate=30")
        run_ffmpeg(["-f", "lavfi", "-i", grad, "-vf", "gblur=sigma=3,eq=contrast=1.1:brightness=0.0,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-t", f"{dur:.2f}", dest],
                   f"Prozedurales Visual Szene {scene.index}")
        return VisualAsset(scene.index, dest, "video", self.name, scene.visual_prompt)


PROVIDERS: Dict[str, Type[VisualProvider]] = {
    "pexels": PexelsProvider, "local": LocalProvider, "ai_image": AIImageProvider,
    "ai_video": AIVideoProvider, "procedural": ProceduralProvider,
}


class VisualGenerator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.used: Set[str] = set()
        self._disabled: Dict[str, str] = {}

    def generate(self, content: ContentPackage, visuals_dir: Path) -> Dict[int, VisualAsset]:
        visuals_dir.mkdir(parents=True, exist_ok=True)
        chain = [n for n in self.cfg.visuals.providers if n in PROVIDERS]
        if "procedural" not in chain:
            chain.append("procedural")
        providers = [PROVIDERS[n](self.cfg, self.used) for n in chain]
        assets: Dict[int, VisualAsset] = {}
        for scene in content.scenes:
            min_s = float(self.cfg.visuals.min_clip_seconds)
            asset = None
            for p in providers:
                if p.name in self._disabled:
                    continue
                try:
                    asset = p.fetch(scene, visuals_dir, min_s)
                except NotImplementedError as exc:
                    self._disabled[p.name] = str(exc)
                    log.warning(f"Visual-Anbieter '{p.name}' nicht implementiert - uebersprungen")
                except PipelineError as exc:
                    self._disabled[p.name] = str(exc)          # Konfigurationsproblem: nicht erneut versuchen
                    log.warning(f"Visual-Anbieter '{p.name}' deaktiviert: {exc}")
                except Exception as exc:
                    log.warning(f"Szene {scene.index}: '{p.name}' fehlgeschlagen ({exc}) - naechster Anbieter")
                if asset:
                    break
            if asset is None:
                raise PipelineError(f"Kein Visual fuer Szene {scene.index} erzeugbar")
            log.debug(f"Szene {scene.index}: {asset.provider} -> {asset.path.name}")
            assets[scene.index] = asset
        counts: Dict[str, int] = {}
        for a in assets.values():
            counts[a.provider] = counts.get(a.provider, 0) + 1
        log.info("Visuals fertig: " + ", ".join(f"{k} x{v}" for k, v in counts.items()))
        return assets
