"""Exporter: Dateinamen vergeben, Video verifizieren, Metadaten + Caption speichern."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config import Config
from .models import ContentPackage, Topic, VisualAsset, VoiceResult
from .utils import PipelineError, load_json, probe_duration, require_binary, save_json


class Exporter:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.out_dir = cfg.finished_dir

    def next_basename(self) -> str:
        """z.B. 2026-10-28_001_dark-cinematic-knowledge"""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        pattern = re.compile(rf"^{today}_(\d{{3}})_")
        used = [int(m.group(1)) for p in self.out_dir.glob(f"{today}_*.mp4") if (m := pattern.match(p.name))]
        return f"{today}_{(max(used) + 1 if used else 1):03d}_{self.cfg.style.name}"

    def verify(self, video: Path) -> Dict[str, Any]:
        """Prueft Format laut Vorgabe: 1080x1920, H.264, 30fps, mit Audio."""
        cmd = [require_binary("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(video)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            streams = json.loads(proc.stdout)["streams"]
        except (json.JSONDecodeError, KeyError):
            raise PipelineError(f"Ausgabedatei {video} ist kein gueltiges Video") from None
        v = next((s for s in streams if s["codec_type"] == "video"), None)
        a = next((s for s in streams if s["codec_type"] == "audio"), None)
        if not v or not a:
            raise PipelineError("Ausgabevideo hat keine Video- oder Audiospur")
        num, den = (v.get("r_frame_rate", "30/1").split("/") + ["1"])[:2]
        fps = float(num) / float(den or 1)
        info = {"width": v["width"], "height": v["height"], "codec": v["codec_name"], "fps": round(fps, 2),
                "duration": round(probe_duration(video), 2), "audio_codec": a["codec_name"]}
        problems = []
        if (info["width"], info["height"]) != (self.cfg.editing.width, self.cfg.editing.height):
            problems.append(f"Aufloesung {info['width']}x{info['height']}")
        if info["codec"] != "h264":
            problems.append(f"Codec {info['codec']}")
        if abs(fps - self.cfg.editing.fps) > 0.1:
            problems.append(f"FPS {fps}")
        if problems:
            raise PipelineError("Ausgabeformat weicht ab: " + ", ".join(problems))
        return info

    def export(self, video_tmp: Path, content: ContentPackage, topic: Topic, voice: VoiceResult,
               assets: Dict[int, VisualAsset], run_id: str, warnings: List[str]) -> Path:
        info = self.verify(video_tmp)
        base = self.next_basename()
        final = self.out_dir / f"{base}.mp4"
        shutil.move(str(video_tmp), final)

        credits = sorted({a.credit for a in assets.values() if a.credit})
        meta: Dict[str, Any] = {
            **content.to_dict(),
            "file": final.name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "run_id": run_id,
            "style": self.cfg.style.name,
            "video": info,
            "voice": {"provider": voice.provider, "timing": voice.timing_source},
            "topic_info": {"title": topic.title, "source": topic.source, "source_url": topic.source_url,
                           "category": topic.category, "scores": topic.scores, "total_score": topic.total_score},
            "visual_providers": {str(i): a.provider for i, a in assets.items()},
            "visual_credits": credits,
            "test_mode": self.cfg.test_mode,
            "warnings": warnings,
        }
        save_json(self.out_dir / f"{base}.json", meta)
        full_caption = f"{content.caption}\n\n{' '.join(content.hashtags)}"
        (self.out_dir / f"{base}_caption.txt").write_text(full_caption + "\n", encoding="utf-8")
        # Kopien fuer die Datenablage
        save_json(self.cfg.path(f"data/scripts/{base}.json"), {"script": content.script, "scenes": [
            {"role": s.role, "narration": s.narration, "visual_prompt": s.visual_prompt} for s in content.scenes]})
        save_json(self.cfg.path(f"data/metadata/{base}.json"), meta)
        if not self.cfg.test_mode:
            self._remember_topic(topic)
        return final

    def _remember_topic(self, topic: Topic) -> None:
        path = self.cfg.path("data/topics/used.json")
        used = load_json(path, [])
        used.append({"title": topic.title, "date": datetime.now().isoformat(timespec="seconds")})
        save_json(path, used)

    def used_titles(self) -> List[str]:
        return [u["title"] for u in load_json(self.cfg.path("data/topics/used.json"), [])]
