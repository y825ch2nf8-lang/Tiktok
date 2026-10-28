"""Pipeline: orchestriert alle Module mit Retry, Fallbacks und Logging.

Grundsatz: Ein fehlgeschlagener Schritt bricht den Lauf nur ab, wenn es keine sinnvolle Alternative gibt.
  Themen-Quelle faellt aus   -> andere Quellen
  Themen-Bewertung scheitert -> Reihenfolge der Quellen
  TTS-Anbieter faellt aus    -> naechster Anbieter (voice.fallback_providers)
  Visual-Anbieter faellt aus -> naechster Anbieter, zuletzt prozedurale Hintergruende
  Untertitel scheitern       -> Video ohne Untertitel (Warnung)
  Sound-Mix scheitert        -> nur Voice-over
  Rendering scheitert        -> Safe Mode (harte Schnitte)
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, TypeVar

from config import Config
from .content_generator import ContentGenerator
from .exporter import Exporter
from .llm_client import create_llm
from .logger import log
from .models import ContentPackage, RunContext, Topic, VisualAsset, VoiceResult
from .sound_design import SoundDesigner
from .subtitle_generator import SubtitleGenerator
from .topic_finder import TopicFinder
from .utils import PipelineError, require_binary
from .video_editor import VideoEditor
from .visual_generator import VisualGenerator
from .voice_generator import VoiceGenerator, assign_scene_times

T = TypeVar("T")


class Pipeline:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.llm = create_llm(cfg)
        self.topics = TopicFinder(cfg, self.llm)
        self.content = ContentGenerator(cfg, self.llm)
        self.voice = VoiceGenerator(cfg)
        self.visuals = VisualGenerator(cfg)
        self.subtitles = SubtitleGenerator(cfg)
        self.sound = SoundDesigner(cfg)
        self.editor = VideoEditor(cfg)
        self.exporter = Exporter(cfg)
        self.warnings: List[str] = []

    # ------------------------------------------------------------------ Hilfen
    def _step(self, name: str, fn: Callable[[], T], retries: Optional[int] = None) -> T:
        """Fuehrt einen Schritt mit Wiederholungen aus. Konfigurationsfehler werden nicht wiederholt."""
        tries = (retries if retries is not None else int(self.cfg.pipeline.step_retries)) + 1
        last: Optional[Exception] = None
        for attempt in range(1, tries + 1):
            try:
                return fn()
            except PipelineError as exc:
                last = exc
                if "fehlt" in str(exc) or "nicht gefunden" in str(exc):   # Setup-Probleme: Retry sinnlos
                    break
                log.warning(f"{name}: {exc} (Versuch {attempt}/{tries})")
            except Exception as exc:
                last = exc
                log.warning(f"{name}: unerwarteter Fehler: {exc!r} (Versuch {attempt}/{tries})")
            if attempt < tries:
                time.sleep(float(self.cfg.pipeline.retry_delay))
        raise PipelineError(f"Schritt '{name}' fehlgeschlagen: {last}")

    def _context(self) -> RunContext:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = self.cfg.work_root / run_id
        ctx = RunContext(run_id=run_id, root=root, audio_dir=root / "audio", visuals_dir=root / "visuals",
                         clips_dir=root / "clips", subtitles_dir=root / "subtitles")
        for d in (ctx.audio_dir, ctx.visuals_dir, ctx.clips_dir, ctx.subtitles_dir):
            d.mkdir(parents=True, exist_ok=True)
        return ctx

    def _warn(self, msg: str) -> None:
        self.warnings.append(msg)
        log.warning(msg)

    # ------------------------------------------------------------------ Themen
    def select_topic(self, manual: Optional[str] = None) -> Topic:
        if manual:
            log.info(f"Verwende vorgegebenes Thema: {manual}")
            return self._step("Thema laden", lambda: self.topics.from_title(manual))

        log.info("Suche Themen...")
        candidates = self._step("Themensuche", self.topics.find)
        if not candidates:
            raise PipelineError("Keine Themen gefunden (Netzwerk? Quellen in config.yaml pruefen)")
        log.info(f"{len(candidates)} Themen gefunden")
        try:
            ranked = self._step("Themenbewertung", lambda: self.topics.score(candidates))
        except PipelineError as exc:
            self._warn(f"Bewertung fehlgeschlagen ({exc}) - verwende Reihenfolge der Quellen")
            ranked = candidates
        self.topics.save(ranked)
        best = self.topics.pick_best(ranked, self.exporter.used_titles())
        log.info(f"Bestes Thema: {best.title} (Score {best.total_score:.2f}, {best.category or 'ohne Kategorie'})")
        return best

    # ------------------------------------------------------------------ Hauptlauf
    def run(self, manual_topic: Optional[str] = None) -> Path:
        require_binary("ffmpeg")
        require_binary("ffprobe")
        self.warnings = []
        ctx = self._context()
        cfg = self.cfg
        try:
            topic = self.select_topic(manual_topic)
            ctx.topic = topic

            content = self._step("Skripterstellung", lambda: self.content.build(topic), retries=1)
            voice = self._make_voice(content, ctx, topic)
            assign_scene_times(content, voice)

            log.info("Erstelle Visuals...")
            assets = self._step("Visuals", lambda: self.visuals.generate(content, ctx.visuals_dir), retries=1)

            log.info("Erstelle Untertitel...")
            sub_path: Optional[Path] = None
            if cfg.subtitles.enabled:
                try:
                    sub_path = self.subtitles.generate(content, voice, ctx.subtitles_dir)
                except Exception as exc:
                    self._warn(f"Untertitel fehlgeschlagen ({exc}) - Video wird ohne Untertitel gerendert")

            log.info("Erstelle Sound Design...")
            mix_path = ctx.audio_dir / "final_mix.wav"
            try:
                self.sound.mix(voice.audio_path, content, voice.duration, mix_path)
            except Exception as exc:
                self._warn(f"Sound Design fehlgeschlagen ({exc}) - verwende nur das Voice-over")
                self.sound.mix_voice_only(voice.audio_path, voice.duration, mix_path)

            tmp_video = ctx.root / "video.mp4"
            self._step("Rendering", lambda: self.editor.render(content, assets, sub_path, mix_path,
                                                               voice.duration, tmp_video, ctx.root), retries=0)

            final = self.exporter.export(tmp_video, content, topic, voice, assets, ctx.run_id, self.warnings)
            log.success(f"Video fertig:\n{final.relative_to(cfg.root) if final.is_relative_to(cfg.root) else final}")
            return final
        finally:
            if not cfg.export.keep_work and ctx.root.exists():
                shutil.rmtree(ctx.root, ignore_errors=True)

    def _make_voice(self, content: ContentPackage, ctx: RunContext, topic: Topic) -> VoiceResult:
        voice = self._step("Voice-over", lambda: self.voice.generate(content, ctx.audio_dir), retries=0)
        max_d = float(self.cfg.content.max_duration)
        if voice.duration > max_d + 0.5:
            words = len(content.script.split())
            target = int(words * max_d / voice.duration * 0.92)
            self._warn(f"Voice-over {voice.duration:.1f}s zu lang - Skript wird auf ca. {target} Woerter gekuerzt")
            new_content = self._step("Skript kuerzen", lambda: self.content.build(topic, max_words=target), retries=0)
            content.__dict__.update(new_content.__dict__)
            voice = self._step("Voice-over", lambda: self.voice.generate(content, ctx.audio_dir), retries=0)
        if voice.duration < float(self.cfg.content.min_duration) - 3:
            self._warn(f"Voice-over nur {voice.duration:.1f}s (Ziel >= {self.cfg.content.min_duration}s)")
        return voice
