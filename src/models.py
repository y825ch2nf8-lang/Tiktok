"""Gemeinsame Datenmodelle - das "Vertragswerk" zwischen allen Modulen."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

SCENE_ROLES = ("hook", "curiosity", "info", "twist", "payoff", "cta")
CAMERA_MOVES = ("zoom_in", "zoom_out", "pan_left", "pan_right", "push_in", "drift_up")
SFX_TYPES = ("none", "whoosh", "impact", "bass_hit", "riser")


@dataclass
class Topic:
    title: str
    source: str                      # z.B. wikipedia_mostread / hackernews / llm_evergreen
    source_url: str = ""
    grounding: str = ""              # belegte Fakten (Quelltext) - einzige erlaubte Faktenbasis
    category: str = ""
    angle: str = ""                  # vorgeschlagener Blickwinkel
    scores: Dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Scene:
    index: int
    role: str
    narration: str
    visual_prompt: str
    search_query: str
    camera: str = "zoom_in"
    sfx: str = "none"
    emphasis: List[str] = field(default_factory=list)
    # Werden nach dem Voice-over gefuellt:
    start: float = 0.0
    end: float = 0.0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class ContentPackage:
    topic: str
    title: str
    hook: str
    hooks: List[str]
    script: str
    duration: float
    scenes: List[Scene]
    caption: str
    hashtags: List[str]
    cta: str
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WordTiming:
    text: str
    start: float
    end: float


@dataclass
class VoiceResult:
    audio_path: Path
    duration: float
    words: List[WordTiming]
    provider: str
    timing_source: str               # "provider" (exakt) oder "estimated" (geschaetzt)


@dataclass
class VisualAsset:
    scene_index: int
    path: Path
    kind: str                        # "video" | "image"
    provider: str
    prompt: str = ""
    credit: str = ""


@dataclass
class Shot:
    """Ein einzelner Schnitt im fertigen Video (Teil einer Szene)."""
    scene_index: int
    asset: VisualAsset
    start: float
    end: float
    camera: str
    source_offset: float = 0.0       # Startpunkt im Quellvideo (Sekunden)
    transition: str = "fade"

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class SfxEvent:
    kind: str                        # whoosh | impact | bass_hit | riser
    time: float                      # Zeitpunkt, an dem der Effekt "trifft"
    volume: float = 1.0


@dataclass
class RunContext:
    """Arbeitsverzeichnisse eines Laufs."""
    run_id: str
    root: Path
    audio_dir: Path
    visuals_dir: Path
    clips_dir: Path
    subtitles_dir: Path
    topic: Optional[Topic] = None
