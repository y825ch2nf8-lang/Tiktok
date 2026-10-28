"""Untertitel: TikTok-Style Wort-fuer-Wort-Captions als ASS-Datei (von FFmpeg/libass gerendert).

* 1-3 Woerter pro Block, GROSSBUCHSTABEN, dicke Kontur, Pop-Animation
* aktuelles Wort in `active_color`, Schluesselwoerter dauerhaft in `emphasis_color`
* Position per `y_ratio` im sicheren Bereich (nicht an oberer/unterer TikTok-UI)
* Timing: exakte Wort-Zeiten aus dem Voice-over
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Set

from config import Config
from .models import ContentPackage, VoiceResult, WordTiming
from .utils import hex_to_ass, normalize_word, tokenize_words

_SENTENCE_END = (".", "!", "?", "…")
_SOFT_BREAK = (",", ";", ":", "–", "-")


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _clean(text: str) -> str:
    """ASS-Sonderzeichen entschaerfen."""
    return text.replace("{", "(").replace("}", ")").replace("\\", "")


class SubtitleGenerator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def generate(self, content: ContentPackage, voice: VoiceResult, out_dir: Path) -> Path:
        s = self.cfg.subtitles
        w, h = self.cfg.editing.width, self.cfg.editing.height
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "subtitles.ass"

        primary = hex_to_ass(s.primary_color)
        active = hex_to_ass(s.active_color)
        emph = hex_to_ass(s.emphasis_color)
        outline = hex_to_ass(s.outline_color)
        back = hex_to_ass("#000000", alpha=0x80)
        y = int(h * float(s.y_ratio))

        lines = [
            "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
            "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,{s.font_name},{s.font_size},{primary},{primary},{outline},{back},-1,0,0,0,100,100,1,0,1,"
            f"{s.outline},{s.shadow},5,90,90,0,1",
            "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        tokens = tokenize_words(" ".join(sc.narration for sc in content.scenes))
        if len(tokens) != len(voice.words):
            raise ValueError(f"Wort-Timing passt nicht zum Skript ({len(tokens)} vs {len(voice.words)} Woerter)")

        idx = 0
        for scene in content.scenes:
            n = len(tokenize_words(scene.narration))
            words = voice.words[idx: idx + n]
            idx += n
            scale = 112 if scene.role == "hook" else 100
            emphasis = self._emphasis_set(scene.emphasis, words)
            for chunk in self._chunks(words, int(s.max_words_per_chunk)):
                lines.extend(self._events(chunk, emphasis, active, emph, primary, y, w, scale, scene.end,
                                          bool(s.uppercase), bool(s.pop_animation)))

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    @staticmethod
    def _emphasis_set(emphasis: List[str], words: List[WordTiming]) -> Set[str]:
        keys = {normalize_word(e) for e in emphasis for e in e.split()}
        keys |= {normalize_word(wd.text) for wd in words if re.search(r"\d", wd.text)}   # Zahlen immer betonen
        keys.discard("")
        return keys

    @staticmethod
    def _chunks(words: List[WordTiming], max_words: int) -> List[List[WordTiming]]:
        chunks: List[List[WordTiming]] = []
        cur: List[WordTiming] = []
        for wd in words:
            cur.append(wd)
            ends_sentence = wd.text.endswith(_SENTENCE_END)
            soft = wd.text.endswith(_SOFT_BREAK) and len(cur) >= 2
            if len(cur) >= max_words or ends_sentence or soft:
                chunks.append(cur)
                cur = []
        if cur:
            # Einzelnes Restwort an den vorherigen Block haengen, falls Platz
            if chunks and len(cur) == 1 and len(chunks[-1]) < max_words + 1 and not chunks[-1][-1].text.endswith(_SENTENCE_END):
                chunks[-1].extend(cur)
            else:
                chunks.append(cur)
        return chunks

    @staticmethod
    def _events(chunk: List[WordTiming], emphasis: Set[str], active: str, emph: str, primary: str, y: int,
                x_center_w: int, scale: int, scene_end: float, upper: bool, pop: bool) -> List[str]:
        out: List[str] = []
        x = x_center_w // 2
        for i, cur in enumerate(chunk):
            start = cur.start
            # Das Wort bleibt aktiv bis das naechste beginnt; letztes Wort kurz nachklingen lassen
            end = chunk[i + 1].start if i + 1 < len(chunk) else min(cur.end + 0.18, max(scene_end, cur.end))
            if end <= start:
                end = start + 0.08
            parts = []
            for j, wd in enumerate(chunk):
                text = _clean(wd.text.upper() if upper else wd.text)
                key = normalize_word(wd.text)
                if j == i:
                    anim = f"\\fscx{scale}\\fscy{scale}"
                    if pop:
                        anim = f"\\fscx{scale - 12}\\fscy{scale - 12}\\t(0,90,\\fscx{scale + 6}\\fscy{scale + 6})" \
                               f"\\t(90,170,\\fscx{scale}\\fscy{scale})"
                    color = emph if key in emphasis else active
                    parts.append(f"{{\\1c{color}{anim}}}{text}{{\\r}}")
                elif key in emphasis:
                    parts.append(f"{{\\1c{emph}\\fscx{scale}\\fscy{scale}}}{text}{{\\r}}")
                else:
                    parts.append(f"{{\\fscx{scale}\\fscy{scale}}}{text}{{\\r}}")
            out.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,"
                       f"{{\\an5\\pos({x},{y})}}{' '.join(parts)}")
        return out
