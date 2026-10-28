"""Content-Generator: setzt Skript + Caption + Hashtags zu einem ContentPackage zusammen."""
from __future__ import annotations

from typing import Optional

from config import Config
from .llm_client import LLMClient
from .logger import log
from .models import ContentPackage, Scene, Topic
from .schema import validate_caption
from .script_generator import ScriptGenerator


class ContentGenerator:
    def __init__(self, cfg: Config, llm: LLMClient) -> None:
        self.cfg = cfg
        self.llm = llm
        self.scripts = ScriptGenerator(cfg, llm)

    def build(self, topic: Topic, max_words: Optional[int] = None) -> ContentPackage:
        log.info("Erstelle Skript...")
        draft = self.scripts.generate(topic, max_words=max_words)
        log.info(f"Skript fertig: \"{draft['title']}\" ({len(draft['scenes'])} Szenen, ca. {draft['duration']}s)")
        log.info("Erstelle Caption und Hashtags...")
        meta = self._caption(topic, draft["title"], draft["script"], draft["cta"])

        scenes = [Scene(index=i, role=s["role"], narration=s["narration"], visual_prompt=s["visual_prompt"],
                        search_query=s["search_query"], camera=s["camera"], sfx=s["sfx"],
                        emphasis=s["emphasis"]) for i, s in enumerate(draft["scenes"])]
        sources = list(dict.fromkeys([*draft.get("sources_used", []), topic.source_url]))
        return ContentPackage(
            topic=draft["topic"], title=draft["title"], hook=draft["hook"], hooks=draft["hooks"],
            script=draft["script"], duration=draft["duration"], scenes=scenes,
            caption=meta["caption"], hashtags=meta["hashtags"], cta=draft["cta"],
            sources=[s for s in sources if s],
        )

    def _caption(self, topic: Topic, title: str, script: str, cta: str) -> dict:
        system = "Du bist TikTok-Growth-Experte. Antworte ausschliesslich mit gueltigem JSON."
        user = f"""Schreibe die TikTok-Caption und Hashtags fuer dieses Video ({self.cfg.content.language_name}).
Titel: {title}
Kategorie: {topic.category}
Skript: {script}

Regeln:
- caption: max. 150 Zeichen, neugierig machend, verrate den Twist NICHT, kein Clickbait-Luegen, kein Hashtag im Text,
  1 passendes Emoji erlaubt.
- hashtags: 5-6 Stueck ohne Leerzeichen; Mix aus 2 breiten (z.B. #wissen, #fakten), 2 themenspezifischen und
  1-2 Nischen-Hashtags. Mit fuehrendem #.
JSON: {{"caption": "", "hashtags": ["#..."]}}"""
        return self.llm.complete_json("caption", system, user, lambda d: validate_caption(d, self.cfg))
