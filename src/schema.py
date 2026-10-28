"""Robuste JSON-Validierung fuer alle LLM-Antworten.

Jeder Validator gibt eine *bereinigte* Struktur zurueck oder wirft `ValidationError`
mit einer Liste konkreter Fehler. Diese Fehlerliste wird dem LLM beim Retry
zurueckgemeldet, damit es gezielt korrigieren kann.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .models import CAMERA_MOVES, SCENE_ROLES, SFX_TYPES
from .utils import tokenize_words


def _norm(text: str) -> str:
    """Kleinbuchstaben, nur Buchstaben/Ziffern/Leerzeichen - fuer robuste Textvergleiche."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


class ValidationError(ValueError):
    def __init__(self, errors: List[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _str(data: Dict[str, Any], key: str, errors: List[str], *, min_len: int = 1,
         max_len: int = 5000) -> str:
    value = data.get(key)
    if not isinstance(value, str) or len(value.strip()) < min_len:
        errors.append(f"'{key}' muss ein nicht-leerer String sein")
        return ""
    value = value.strip()
    if len(value) > max_len:
        errors.append(f"'{key}' ist zu lang ({len(value)} > {max_len} Zeichen)")
    return value


def _str_list(data: Dict[str, Any], key: str, errors: List[str], *, min_items: int = 0,
              max_items: int = 50) -> List[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f"'{key}' muss eine Liste von Strings sein")
        return []
    items = [v.strip() for v in value if v.strip()]
    if len(items) < min_items:
        errors.append(f"'{key}' braucht mindestens {min_items} Eintraege")
    return items[:max_items]


# ------------------------------------------------------------------ Themen-Bewertung
def validate_topic_scores(data: Any, n_topics: int) -> List[Dict[str, Any]]:
    """Erwartet {"ratings": [{"id": 0, "curiosity": 0-10, ...}]}."""
    errors: List[str] = []
    if isinstance(data, dict):
        data = data.get("ratings")
    if not isinstance(data, list):
        raise ValidationError(["Erwartet wird ein Objekt {\"ratings\": [...]}"])
    out: List[Dict[str, Any]] = []
    seen = set()
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"ratings[{i}] ist kein Objekt")
            continue
        idx = item.get("id")
        if not isinstance(idx, int) or not 0 <= idx < n_topics:
            errors.append(f"ratings[{i}].id muss eine Ganzzahl 0..{n_topics - 1} sein")
            continue
        entry: Dict[str, Any] = {"id": idx}
        for key in ("curiosity", "emotion", "share", "watchtime", "visual_ease"):
            v = item.get(key)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= 10:
                errors.append(f"ratings[{i}].{key} muss eine Zahl 0-10 sein")
            else:
                entry[key] = float(v)
        entry["category"] = str(item.get("category", "")).strip()
        entry["angle"] = str(item.get("angle", "")).strip()
        seen.add(idx)
        out.append(entry)
    if len(seen) < max(1, n_topics // 2):
        errors.append(f"Es wurden nur {len(seen)} von {n_topics} Themen bewertet")
    if errors:
        raise ValidationError(errors)
    return out


def validate_brainstorm(data: Any) -> List[Dict[str, str]]:
    """Erwartet {"topics": [{"wikipedia_title": "...", "category": "..."}]}."""
    if isinstance(data, dict):
        data = data.get("topics")
    if not isinstance(data, list) or not data:
        raise ValidationError(["Erwartet wird {\"topics\": [{\"wikipedia_title\": ..., \"category\": ...}]}"])
    out = []
    errors = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or not isinstance(item.get("wikipedia_title"), str) \
                or not item["wikipedia_title"].strip():
            errors.append(f"topics[{i}].wikipedia_title fehlt")
            continue
        out.append({"wikipedia_title": item["wikipedia_title"].strip(),
                    "category": str(item.get("category", "")).strip()})
    if errors and not out:
        raise ValidationError(errors)
    return out


# ------------------------------------------------------------------ Skript
def validate_script(data: Any, cfg: Any) -> Dict[str, Any]:
    """Validiert die Skript-Antwort. `cfg` ist die Config (Dauer-/Szenenlimits)."""
    if not isinstance(data, dict):
        raise ValidationError(["Wurzel muss ein JSON-Objekt sein"])
    c = cfg.content
    errors: List[str] = []

    result: Dict[str, Any] = {
        "topic": _str(data, "topic", errors, max_len=200),
        "title": _str(data, "title", errors, max_len=120),
        "hooks": _str_list(data, "hooks", errors, min_items=2, max_items=6),
        "hook": _str(data, "hook", errors, max_len=300),
        "cta": _str(data, "cta", errors, max_len=200),
        "sources_used": _str_list(data, "sources_used", errors) if "sources_used" in data else [],
    }

    scenes_raw = data.get("scenes")
    scenes: List[Dict[str, Any]] = []
    if not isinstance(scenes_raw, list):
        errors.append("'scenes' muss eine Liste sein")
        scenes_raw = []
    if not c.min_scenes <= len(scenes_raw) <= c.max_scenes:
        errors.append(f"Anzahl Szenen {len(scenes_raw)} ausserhalb {c.min_scenes}..{c.max_scenes}")

    for i, sc in enumerate(scenes_raw):
        if not isinstance(sc, dict):
            errors.append(f"scenes[{i}] ist kein Objekt")
            continue
        sub: List[str] = []
        narration = _str(sc, "narration", sub, max_len=400)
        visual = _str(sc, "visual_prompt", sub, max_len=500)
        query = _str(sc, "search_query", sub, max_len=80)
        role = str(sc.get("role", "")).strip().lower()
        if role not in SCENE_ROLES:
            sub.append(f"role muss eines von {SCENE_ROLES} sein")
        camera = str(sc.get("camera", "zoom_in")).strip().lower()
        if camera not in CAMERA_MOVES:
            camera = "zoom_in"          # unkritisch: still korrigieren
        sfx = str(sc.get("sfx", "none")).strip().lower()
        if sfx not in SFX_TYPES:
            sfx = "none"
        emphasis = sc.get("emphasis", [])
        emphasis = [e.strip() for e in emphasis if isinstance(e, str) and e.strip()] \
            if isinstance(emphasis, list) else []
        if sub:
            errors.extend(f"scenes[{i}]: {e}" for e in sub)
            continue
        scenes.append({"role": role, "narration": narration, "visual_prompt": visual,
                       "search_query": query, "camera": camera, "sfx": sfx, "emphasis": emphasis})

    result["scenes"] = scenes

    if scenes:
        words = sum(len(tokenize_words(s["narration"])) for s in scenes)
        est = words / float(c.words_per_second)
        result["duration"] = round(est, 1)
        lo, hi = c.min_duration - 2, c.max_duration - 1
        if not lo <= est <= hi:
            errors.append(
                f"Das Skript hat {words} Woerter = ca. {est:.0f}s; erlaubt sind {c.min_duration}-{c.max_duration}s "
                f"(ca. {int(c.min_duration * c.words_per_second)}-{int((c.max_duration - 4) * c.words_per_second)} Woerter)")
        if scenes[0]["role"] != "hook":
            errors.append("scenes[0].role muss 'hook' sein")
        if scenes[-1]["role"] != "cta":
            errors.append("Die letzte Szene muss role='cta' haben")
        first = _norm(scenes[0]["narration"])
        if result["hook"] and _norm(result["hook"])[:25] not in first:
            # Der Hook muss die erste gesprochene Zeile sein.
            errors.append("scenes[0].narration muss mit dem gewaehlten 'hook' beginnen")
        if first.split()[:1] and first.split()[0] in {"hallo", "hey", "willkommen", "servus", "moin", "hi"}:
            errors.append("Keine Begruessung im Hook")

    result["script"] = " ".join(s["narration"] for s in scenes)
    if errors:
        raise ValidationError(errors)
    return result


# ------------------------------------------------------------------ Caption
def validate_caption(data: Any, cfg: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError(["Wurzel muss ein JSON-Objekt sein"])
    errors: List[str] = []
    caption = _str(data, "caption", errors, max_len=cfg.export.tiktok_max_caption)
    tags_raw = _str_list(data, "hashtags", errors, min_items=3, max_items=20)
    tags: List[str] = []
    for t in tags_raw:
        t = "#" + t.lstrip("#").replace(" ", "")
        if len(t) > 1 and t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    if len(tags) < 3:
        errors.append("Mindestens 3 verschiedene Hashtags noetig")
    if errors:
        raise ValidationError(errors)
    return {"caption": caption, "hashtags": tags[: cfg.export.max_hashtags]}
