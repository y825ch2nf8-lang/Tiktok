"""Skript-Generator: virales Skript, Hooks und Szenenplan (inkl. Visual-Prompts) als validiertes JSON."""
from __future__ import annotations

from typing import Any, Dict, Optional

from config import Config
from .llm_client import LLMClient
from .models import CAMERA_MOVES, Topic
from .schema import validate_script

SYSTEM_PROMPT = """Du bist ein preisgekroenter Drehbuchautor fuer virale Wissens-Kurzvideos (TikTok/Shorts) im Stil \
"Dark Cinematic Knowledge": ruhige, tiefe Dokumentarfilm-Erzaehlung mit mysterioeser Spannung.

HARTE REGELN:
1. FAKTEN: Verwende AUSSCHLIESSLICH Fakten aus dem Abschnitt QUELLTEXT. Erfinde nichts - keine Zahlen, Namen, \
Daten oder Zitate, die dort nicht stehen. Wenn etwas unklar ist, lass es weg. Keine Uebertreibungen, die der \
Quelltext nicht stuetzt.
2. Der Hook (erste Zeile) fesselt in unter 2 Sekunden. KEINE Begruessung, kein "Hast du gewusst", keine Einleitung.
3. Struktur: HOOK -> CURIOSITY GAP -> INFORMATION/STORY -> TWIST -> PAYOFF -> CTA.
4. Kurze, gesprochene Saetze. Klingt wie ein Mensch, nicht wie ein Lexikon. Keine Emojis, keine Hashtags im Text.
5. Alle 1-3 Sekunden ein neuer Bildgedanke: jede Szene hat 4-12 gesprochene Woerter.
6. Antworte ausschliesslich mit EINEM gueltigen JSON-Objekt, ohne Markdown und ohne Erklaerung."""


class ScriptGenerator:
    def __init__(self, cfg: Config, llm: LLMClient) -> None:
        self.cfg = cfg
        self.llm = llm

    def generate(self, topic: Topic, max_words: Optional[int] = None) -> Dict[str, Any]:
        c = self.cfg.content
        target = c.target_duration
        words_lo = int(c.min_duration * c.words_per_second)
        words_hi = int((c.max_duration - 5) * c.words_per_second)
        if max_words:
            words_hi = min(words_hi, max_words)
        words_target = min(int(target * c.words_per_second), words_hi)
        user = f"""THEMA: {topic.title}
KATEGORIE: {topic.category or 'frei'}
VORGESCHLAGENER BLICKWINKEL: {topic.angle or 'waehle den ueberraschendsten'}
SPRACHE des Skripts: {c.language_name}
ZIELLAENGE: ca. {words_target} gesprochene Woerter (erlaubt {words_lo}-{words_hi}), also ~{target} Sekunden.
SZENEN: {c.min_scenes}-{c.max_scenes}

QUELLTEXT (einzige erlaubte Faktenbasis):
\"\"\"
{topic.grounding[:4000]}
\"\"\"

AUFGABE:
1. Schreibe 4 verschiedene Hook-Varianten (hooks), waehle die staerkste (hook).
2. Schreibe das Skript als Szenenliste. scenes[0] ist role "hook" und beginnt mit dem gewaehlten Hook.
   Rollen in dieser Reihenfolge: hook, curiosity, info (mehrere), twist, payoff, cta (letzte Szene).
3. Pro Szene:
   - narration: gesprochener Text ({c.language_name}).
   - visual_prompt: ENGLISCHER, konkreter Bild-/Video-Prompt (Motiv, Licht, Kamera, Stimmung) passend zur \
Narration, cinematic und dunkel. Ohne Text im Bild.
   - search_query: 2-4 englische Stichwoerter, mit denen man passendes Stock-Footage findet \
(keine Eigennamen, wenn sie kaum Footage haben).
   - camera: eines von {', '.join(CAMERA_MOVES)} (abwechslungsreich).
   - sfx: none | whoosh | impact | bass_hit | riser (sparsam; impact/bass_hit bei Hook und Twist, riser vor dem Twist).
   - emphasis: 0-2 Woerter aus der narration, die visuell hervorgehoben werden sollen (exakt wie geschrieben).
4. cta: kurzer Call-to-Action (z.B. Folgen/Kommentieren), natuerlich, nicht aufdringlich; er ist auch der Text der \
letzten Szene.
5. sources_used: Liste der Quellen (URLs/Titel) aus dem Quelltext.

JSON-Format:
{{"topic": "", "title": "", "hooks": ["","","",""], "hook": "", "cta": "", "sources_used": [""],
"scenes": [{{"role": "hook", "narration": "", "visual_prompt": "", "search_query": "", "camera": "zoom_in",
"sfx": "impact", "emphasis": [""]}}]}}"""
        return self.llm.complete_json("script", SYSTEM_PROMPT, user, lambda d: validate_script(d, self.cfg))
