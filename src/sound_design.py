"""Sound Design: Hintergrundmusik, Ambience und Soundeffekte automatisch zum Voice-over mischen.

* Eigene Dateien haben Vorrang:  assets/music/*.mp3|wav  und  assets/sounds/<typ>*.wav|mp3
  (typ = whoosh, impact, bass_hit, riser, ambient)
* Fehlt etwas, wird es lokal per FFmpeg synthetisiert (dunkler Drone, Whoosh, Impact, Riser, ...)
* Musik wird per Sidechain-Compressor automatisch unter dem Voice-over abgesenkt (Ducking)
* Alle Pegel stammen aus config.yaml (audio.*)
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

from config import Config
from .logger import log
from .models import ContentPackage, SfxEvent
from .utils import probe_duration, run_ffmpeg

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

# Synthese-Rezepte (FFmpeg lavfi). Laenge in Sekunden.
SFX_RECIPES: Dict[str, tuple] = {
    "whoosh": (0.9, "anoisesrc=d=0.9:c=pink:a=0.8:r=44100,highpass=f=450,lowpass=f=7000,"
                    "afade=t=in:d=0.5:curve=qsin,afade=t=out:st=0.45:d=0.45:curve=exp,volume=1.4"),
    "impact": (1.6, "aevalsrc='0.95*sin(2*PI*(42+70*exp(-t*16))*t)*exp(-t*3.2)+0.35*(random(0)*2-1)*exp(-t*28)':"
                    "d=1.6:s=44100,lowpass=f=2500,aecho=0.7:0.5:90|180:0.35|0.2"),
    "bass_hit": (1.0, "aevalsrc='0.95*sin(2*PI*(36+90*exp(-t*28))*t)*exp(-t*5.5)':d=1.0:s=44100,lowpass=f=300"),
    "riser": (2.5, "aevalsrc='(0.45*sin(2*PI*(140*t+110*t*t))+0.22*(random(0)*2-1)*t/2.5)*pow(t/2.5,2)':"
                   "d=2.5:s=44100,highpass=f=80,afade=t=out:st=2.4:d=0.1"),
}
# Zeitpunkt des "Treffers" innerhalb des Effekts (Sekunden ab Dateianfang)
HIT_OFFSET = {"whoosh": 0.5, "impact": 0.0, "bass_hit": 0.0}


class SoundDesigner:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.cache = cfg.cache_dir / "sfx"
        self.cache.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ Assets
    def _user_file(self, folder: str, prefix: Optional[str] = None) -> Optional[Path]:
        d = self.cfg.path(folder)
        if not d.is_dir():
            return None
        files = [p for p in sorted(d.iterdir()) if p.suffix.lower() in AUDIO_EXT
                 and (prefix is None or p.stem.lower().startswith(prefix))]
        return random.choice(files) if files else None

    def sfx_file(self, kind: str) -> Path:
        user = self._user_file("assets/sounds", kind)
        if user:
            return user
        path = self.cache / f"{kind}.wav"
        if not path.exists():
            _, recipe = SFX_RECIPES[kind]
            run_ffmpeg(["-f", "lavfi", "-i", recipe, "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", path],
                       f"Synthese Soundeffekt {kind}")
        return path

    def music_file(self, duration: float) -> Path:
        user = self._user_file("assets/music")
        if user:
            log.debug(f"Musik: {user.name}")
            return user
        path = self.cache / f"drone_{int(duration) + 4}s.wav"
        if not path.exists():
            d = duration + 4
            expr = ("0.30*sin(2*PI*55*t)+0.20*sin(2*PI*82.41*t)+0.14*sin(2*PI*110*t+0.6*sin(2*PI*0.13*t))"
                    "+0.10*sin(2*PI*130.81*t)+0.06*sin(2*PI*164.81*t+0.9*sin(2*PI*0.21*t))")
            graph = (f"aevalsrc='{expr}':d={d}:s=44100,lowpass=f=1100,tremolo=f=0.12:d=0.5,"
                     f"aecho=0.8:0.8:700|1300:0.35|0.25")
            run_ffmpeg(["-f", "lavfi", "-i", graph, "-ac", "2", "-c:a", "pcm_s16le", path], "Synthese Hintergrundmusik")
        return path

    def ambient_file(self, duration: float) -> Path:
        user = self._user_file("assets/sounds", "ambient")
        if user:
            return user
        path = self.cache / f"ambient_{int(duration) + 4}s.wav"
        if not path.exists():
            d = duration + 4
            run_ffmpeg(["-f", "lavfi", "-i", f"anoisesrc=d={d}:c=brown:a=0.5:r=44100,lowpass=f=420,highpass=f=40,"
                                              f"tremolo=f=0.1:d=0.4", "-ac", "2", "-c:a", "pcm_s16le", path],
                       "Synthese Ambience")
        return path

    # ------------------------------------------------------------------ Planung
    def plan_events(self, content: ContentPackage) -> List[SfxEvent]:
        """Leitet aus den Szenen (LLM-Vorgaben + Regeln) die Soundeffekte ab."""
        a = self.cfg.audio
        if not a.sfx_enabled:
            return []
        vol = {"whoosh": a.whoosh_volume, "impact": a.impact_volume,
               "bass_hit": a.bass_hit_volume, "riser": a.riser_volume}
        events: List[SfxEvent] = []
        for i, sc in enumerate(content.scenes):
            kind = sc.sfx
            if i == 0 and kind in ("none", "whoosh"):
                kind = "impact"                       # Hook bekommt immer einen Treffer
            if sc.role == "twist" and kind in ("none", "whoosh"):
                kind = "bass_hit"
            if kind == "none" and i > 0 and a.whoosh_on_cuts:
                kind = "whoosh"
            if kind == "none":
                continue
            t = max(0.0, sc.start)
            events.append(SfxEvent(kind, t, float(vol[kind]) * float(a.sfx_volume)))
            if sc.role == "twist" and kind != "riser" and sc.start > 3.0:
                events.append(SfxEvent("riser", t, float(vol["riser"]) * float(a.sfx_volume)))
        return events

    # ------------------------------------------------------------------ Mix
    def mix(self, voice_path: Path, content: ContentPackage, duration: float, out_path: Path) -> Path:
        """Mischt Voice, Musik (geduckt), Ambience und SFX zu einer Stereo-WAV mit Ziel-Lautheit."""
        a = self.cfg.audio
        events = self.plan_events(content)
        inputs: List[str] = ["-i", str(voice_path)]
        chains: List[str] = []
        labels: List[str] = []
        fmt = "aformat=sample_rates=44100:channel_layouts=stereo"
        D = f"{duration:.3f}"

        chains.append(f"[0:a]{fmt},highpass=f=70,acompressor=threshold=0.12:ratio=3:attack=8:release=80:makeup=1.6,"
                      f"volume={a.voice_volume},apad,atrim=0:{D},asplit=2[vo][vosc]")
        labels.append("[vo]")
        n = 1

        if a.music_enabled:
            inputs += ["-stream_loop", "-1", "-i", str(self.music_file(duration))]
            fo = float(a.music_fade_out)
            chains.append(f"[{n}:a]{fmt},atrim=0:{D},asetpts=PTS-STARTPTS,afade=t=in:d={a.music_fade_in},"
                          f"afade=t=out:st={max(0.0, duration - fo):.2f}:d={fo},volume={a.music_volume}[mus]")
            chains.append(f"[mus][vosc]sidechaincompress=threshold={a.duck_threshold}:ratio={a.duck_ratio}:"
                          f"attack={a.duck_attack_ms}:release={a.duck_release_ms}:makeup=1[musduck]")
            labels.append("[musduck]")
            n += 1
        else:
            chains[0] = chains[0].replace("asplit=2[vo][vosc]", "anull[vo]")

        if a.ambient_enabled:
            inputs += ["-stream_loop", "-1", "-i", str(self.ambient_file(duration))]
            chains.append(f"[{n}:a]{fmt},atrim=0:{D},asetpts=PTS-STARTPTS,afade=t=in:d=1.5,"
                          f"afade=t=out:st={max(0.0, duration - 2):.2f}:d=2,volume={a.ambient_volume}[amb]")
            labels.append("[amb]")
            n += 1

        for ev in events:
            f = self.sfx_file(ev.kind)
            if ev.kind == "riser":
                start = ev.time - probe_duration(f)
            else:
                start = ev.time - HIT_OFFSET.get(ev.kind, 0.0)
            if start < -0.05 and ev.kind == "riser":
                continue
            ms = max(0, int(start * 1000))
            inputs += ["-i", str(f)]
            chains.append(f"[{n}:a]{fmt},adelay={ms}|{ms},volume={ev.volume:.3f},apad,atrim=0:{D}[sfx{n}]")
            labels.append(f"[sfx{n}]")
            n += 1

        total = len(labels)
        # amix skaliert jeden Eingang mit 1/N; alle Eingaenge sind gleich lang -> mit volume=N exakt ausgleichen
        chains.append(f"{''.join(labels)}amix=inputs={total}:duration=longest:dropout_transition=0,volume={total},"
                      f"loudnorm=I={a.target_lufs}:TP={a.true_peak}:LRA=9,alimiter=limit=0.97,atrim=0:{D}[out]")
        run_ffmpeg([*inputs, "-filter_complex", ";".join(chains), "-map", "[out]", "-ar", "44100", "-ac", "2",
                    "-c:a", "pcm_s16le", out_path], "Audio-Mix")
        log.info(f"Sound Design fertig: {len(events)} Soundeffekte, Musik {'an' if a.music_enabled else 'aus'}")
        return out_path

    def mix_voice_only(self, voice_path: Path, duration: float, out_path: Path) -> Path:
        """Notfall-Variante: nur Voice-over, normalisiert."""
        run_ffmpeg(["-i", voice_path, "-af",
                    f"aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I={self.cfg.audio.target_lufs}:"
                    f"TP={self.cfg.audio.true_peak}:LRA=9,atrim=0:{duration:.3f}",
                    "-c:a", "pcm_s16le", out_path], "Voice-only-Mix")
        return out_path
