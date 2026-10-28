"""FFmpeg Video-Editor: Szenen -> Shots -> Clips -> Uebergaenge -> Grading -> Untertitel -> MP4.

Ablauf:
  1. plan_shots():   lange Szenen werden in Shots (<= max_shot_seconds) zerlegt, Kamerabewegungen wechseln
  2. render_clip():  jeder Shot wird einzeln als 1080x1920/30fps-Clip mit Kamera-Zoom/Pan gerendert
  3. assemble():     xfade-Uebergaenge, Dark-Cinematic-Grading (Kontrast, Teal/Orange, Vignette, Grain),
                     ASS-Untertitel, Audio-Mux, H.264/AAC
Bei einem Fehler wird automatisch ein "Safe Mode" (harte Schnitte, kein Grain) versucht.
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from config import Config
from .logger import log
from .models import CAMERA_MOVES, ContentPackage, Shot, VisualAsset
from .utils import PipelineError, probe_duration, run_ffmpeg


class VideoEditor:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.e = cfg.editing
        self.W, self.H, self.FPS = int(self.e.width), int(self.e.height), int(self.e.fps)
        self._asset_dur: Dict[Path, float] = {}

    # ------------------------------------------------------------------ Planung
    def plan_shots(self, content: ContentPackage, assets: Dict[int, VisualAsset]) -> List[Shot]:
        max_shot = float(self.e.max_shot_seconds)
        min_shot = float(self.e.min_shot_seconds)
        shots: List[Shot] = []
        cam_cycle = list(CAMERA_MOVES)
        trans_cycle = list(self.e.transitions)
        scene_no = 0
        for scene in content.scenes:
            dur = scene.end - scene.start
            if dur <= 0.05:
                continue
            n = max(1, math.ceil(dur / max_shot))
            while n > 1 and dur / n < min_shot:
                n -= 1
            asset = assets[scene.index]
            adur = self._duration_of(asset)
            step = dur / n
            consumed = 0.0
            cam = scene.camera if scene.camera in CAMERA_MOVES else "zoom_in"
            for k in range(n):
                s, e = scene.start + k * step, scene.start + (k + 1) * step
                if k > 0:                       # Perspektivwechsel innerhalb der Szene
                    cam = cam_cycle[(cam_cycle.index(cam) + 2) % len(cam_cycle)]
                offset = 0.0
                if asset.kind == "video" and adur > step + 0.2:
                    offset = min(consumed, max(0.0, adur - step - 0.1))
                consumed += step
                if k == 0:
                    trans = self.e.twist_transition if scene.role == "twist" else trans_cycle[scene_no % len(trans_cycle)]
                else:
                    trans = "fade"
                shots.append(Shot(scene.index, asset, s, e, cam, offset, trans))
            scene_no += 1
        if not shots:
            raise PipelineError("Keine Shots geplant (Szenen ohne Dauer?)")
        shots[0].start = 0.0
        return shots

    def _duration_of(self, asset: VisualAsset) -> float:
        if asset.kind == "image":
            return 9999.0
        if asset.path not in self._asset_dur:
            self._asset_dur[asset.path] = probe_duration(asset.path)
        return self._asset_dur[asset.path]

    # ------------------------------------------------------------------ Kamera
    def _camera_filters(self, camera: str, length: float) -> str:
        """Zoom/Pan-Filterkette; `t` laeuft von 0 bis `length` im Clip."""
        z = float(self.e.zoom_strength)
        p = f"min(1,t/{length:.3f})"                           # Fortschritt 0..1
        scale = {
            "zoom_in": f"1+{z}*{p}", "zoom_out": f"1+{z}*(1-{p})", "push_in": f"1+{1.7 * z}*{p}",
            "pan_left": f"1+{z}", "pan_right": f"1+{z}", "drift_up": f"1+{z}",
        }[camera]
        x = {"pan_left": f"(iw-{self.W})*(1-{p})", "pan_right": f"(iw-{self.W})*{p}"}.get(camera, f"(iw-{self.W})/2")
        y = f"(ih-{self.H})*(1-{p})" if camera == "drift_up" else f"(ih-{self.H})/2"
        return (f"scale=w='2*trunc({self.W}*({scale})/2)':h='2*trunc({self.H}*({scale})/2)':eval=frame,"
                f"crop={self.W}:{self.H}:x='{x}':y='{y}'")

    def render_clip(self, shot: Shot, length: float, out: Path) -> Path:
        a = shot.asset
        pre = (f"scale={self.W}:{self.H}:force_original_aspect_ratio=increase,crop={self.W}:{self.H},setsar=1")
        vf = f"setpts=PTS-STARTPTS,{pre},{self._camera_filters(shot.camera, length)},fps={self.FPS},format=yuv420p"
        if a.kind == "image":
            src = ["-loop", "1", "-framerate", str(self.FPS), "-i", a.path]
        else:
            src = ["-stream_loop", "-1", "-ss", f"{shot.source_offset:.3f}", "-i", a.path]
        run_ffmpeg([*src, "-t", f"{length:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(self.FPS), out],
                   f"Clip fuer Szene {shot.scene_index}")
        return out

    # ------------------------------------------------------------------ Zusammenbau
    def _transition_durations(self, shots: List[Shot], safe: bool) -> List[float]:
        """T_j fuer die Verbindung zwischen Shot j und j+1 (Laenge len(shots)-1)."""
        base = 0.0 if safe else float(self.e.transition_seconds)
        out = []
        for j in range(len(shots) - 1):
            nxt = shots[j + 1]
            same_scene = nxt.scene_index == shots[j].scene_index
            t = min(0.1, base) if same_scene else base
            if nxt.transition == "fadeblack" and not same_scene and not safe:
                t = max(t, base * 1.5)
            limit = 0.45 * min(shots[j].duration, nxt.duration)
            out.append(round(min(t, limit), 3))
        return out

    def render(self, content: ContentPackage, assets: Dict[int, VisualAsset], subtitles: Optional[Path],
               audio: Path, duration: float, out_path: Path, work_dir: Path) -> Path:
        shots = self.plan_shots(content, assets)
        log.info(f"Rendere Video... ({len(shots)} Shots, {duration:.1f}s)")
        try:
            return self._render(shots, subtitles, audio, duration, out_path, work_dir, safe=False)
        except PipelineError as exc:
            log.warning(f"Rendering fehlgeschlagen, versuche Safe Mode (harte Schnitte, ohne Grain): {exc}")
            return self._render(shots, subtitles, audio, duration, out_path, work_dir, safe=True)

    def _render(self, shots: List[Shot], subtitles: Optional[Path], audio: Path, duration: float,
                out_path: Path, work_dir: Path, safe: bool) -> Path:
        clips_dir = work_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        trans = self._transition_durations(shots, safe)
        n = len(shots)
        clips: List[Path] = []
        for j, shot in enumerate(shots):
            t_prev = trans[j - 1] if j > 0 else 0.0
            t_next = trans[j] if j < n - 1 else 0.0
            begin = shot.start - t_prev / 2
            end = (shot.end if j < n - 1 else duration) + t_next / 2
            length = max(0.2, end - begin)
            clip = clips_dir / f"shot_{j:03d}{'_safe' if safe else ''}.mp4"
            self.render_clip(shot, length, clip)
            clips.append(clip)

        # Filtergraph
        inputs: List[str] = []
        for c in clips:
            inputs += ["-i", str(c)]
        chains: List[str] = []
        if n == 1:
            chains.append("[0:v]null[vx]")
        elif safe or all(t <= 0 for t in trans):
            chains.append("".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vx]")
        else:
            prev = "[0:v]"
            for j in range(n - 1):
                off = shots[j + 1].start - trans[j] / 2
                label = f"[x{j}]" if j < n - 2 else "[vx]"
                chains.append(f"{prev}[{j + 1}:v]xfade=transition={shots[j + 1].transition}:"
                              f"duration={trans[j]:.3f}:offset={max(0.0, off):.3f}{label}")
                prev = label

        g = self.e.grade
        post = [f"tpad=stop_mode=clone:stop_duration=1"]
        post.append(f"eq=contrast={g.contrast}:saturation={g.saturation}:brightness={g.brightness}")
        post.append("colorbalance=rs=-0.04:gs=0.0:bs=0.06:rm=-0.01:bm=0.02:rh=0.05:gh=0.01:bh=-0.04")
        if g.vignette and not safe:
            post.append("vignette=angle=PI/4.5")
        if int(g.grain) > 0 and not safe:
            post.append(f"noise=alls={int(g.grain)}:allf=t")
        post.append("format=yuv420p")
        if subtitles is not None:
            fonts = self.cfg.path("assets/fonts")
            sub_local = work_dir / "subs.ass"
            shutil.copyfile(subtitles, sub_local)
            font_arg = ""
            if fonts.is_dir() and any(p.suffix.lower() in (".ttf", ".otf") for p in fonts.iterdir()):
                local_fonts = work_dir / "fonts"
                if local_fonts.exists():
                    shutil.rmtree(local_fonts)
                shutil.copytree(fonts, local_fonts, ignore=shutil.ignore_patterns(".gitkeep"))
                font_arg = ":fontsdir=fonts"
            post.append(f"ass=subs.ass{font_arg}")
        chains.append(f"[vx]{','.join(post)}[v]")

        inputs += ["-i", str(audio)]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg([*inputs, "-filter_complex", ";".join(chains), "-map", "[v]", "-map", f"{n}:a",
                    "-c:v", "libx264", "-preset", self.e.video_preset, "-crf", str(self.e.video_crf),
                    "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(self.FPS),
                    "-c:a", "aac", "-b:a", self.e.audio_bitrate, "-ar", "44100",
                    "-t", f"{duration:.3f}", "-movflags", "+faststart", out_path],
                   "Finales Rendering", cwd=work_dir)
        return out_path
