"""Topic Engine: findet echte Themen, belegt sie mit Quelltext, bewertet und waehlt das beste.

Quellen (alle liefern *belegbaren* Text - das LLM darf spaeter nur daraus Fakten nehmen):
  * wikipedia_mostread  - meistgelesene Artikel von gestern (Wikimedia Feed API)
  * wikipedia_onthisday - historische Ereignisse des heutigen Tages
  * hackernews          - aktuelle Tech-/KI-/Wissenschafts-Stories (Artikeltext wird geladen)
  * llm_evergreen       - Brainstorming des LLM; Themen zaehlen NUR, wenn ein echter
                          Wikipedia-Artikel existiert (dessen Text wird die Faktenbasis)
  * samples             - Testmodus (data/samples/topics.json)
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from config import Config
from .llm_client import LLMClient
from .logger import log
from .models import Topic
from .schema import validate_brainstorm, validate_topic_scores
from .utils import PipelineError, http_get, load_json, save_json

_SKIP_PREFIXES = ("Spezial:", "Special:", "Wikipedia:", "Hauptseite", "Main_Page", "Portal:", "Datei:",
                  "File:", "Kategorie:", "Category:", "Liste_", "List_of", "Hilfe:", "Help:")


class TopicFinder:
    def __init__(self, cfg: Config, llm: LLMClient) -> None:
        self.cfg = cfg
        self.llm = llm
        self.lang = cfg.topics.wikipedia_lang
        self._sources: Dict[str, Callable[[], List[Topic]]] = {
            "wikipedia_mostread": self._wikipedia_mostread,
            "wikipedia_onthisday": self._wikipedia_onthisday,
            "hackernews": self._hackernews,
            "llm_evergreen": self._llm_evergreen,
            "samples": self._samples,
        }

    # ------------------------------------------------------------ oeffentliche API
    def find(self) -> List[Topic]:
        """Sammelt Kandidaten aus allen Quellen (einzelne Quellen duerfen ausfallen)."""
        topics: List[Topic] = []
        for name in self.cfg.topics.sources:
            fn = self._sources.get(name)
            if fn is None:
                log.warning(f"Unbekannte Themenquelle '{name}' ignoriert")
                continue
            try:
                found = fn()
                log.debug(f"Quelle {name}: {len(found)} Themen")
                topics.extend(found)
            except Exception as exc:
                log.warning(f"Themenquelle '{name}' fehlgeschlagen: {exc}")
        topics = self._dedupe(topics)
        topics = [t for t in topics if len(t.grounding) >= self._min_chars(t)]
        return topics[: self.cfg.topics.max_candidates]

    def score(self, topics: List[Topic]) -> List[Topic]:
        """Bewertet Themen per LLM (curiosity/emotion/share/watchtime/visual_ease) und sortiert."""
        if not topics:
            return []
        listing = "\n".join(f"[{i}] {t.title} -- {t.grounding[:220].replace(chr(10), ' ')}" for i, t in enumerate(topics))
        system = ("Du bist ein TikTok-Content-Stratege fuer Wissens-Kurzvideos. Du bewertest Themen streng und "
                  "differenziert (nutze die ganze Skala 0-10) und antwortest ausschliesslich mit gueltigem JSON.")
        user = f"""Bewerte jedes Thema fuer ein 30-Sekunden-TikTok im Stil "Dark Cinematic Knowledge".
Kriterien (0-10): curiosity (Neugier), emotion, share (Share-Potenzial), watchtime (haelt bis zum Ende),
visual_ease (einfach cinematic umsetzbar mit Stock-/B-Roll-Material).
Ordne ausserdem eine category zu (eine von: {', '.join(self.cfg.topics.categories)}) und schlage einen
kurzen angle vor (ueberraschender Blickwinkel, max. 15 Woerter). Erfinde keine Fakten.
Themen:
{listing}

Antworte als JSON:
{{"ratings": [{{"id": 0, "curiosity": 0, "emotion": 0, "share": 0, "watchtime": 0, "visual_ease": 0,
"category": "", "angle": ""}}]}}
Es muessen alle {len(topics)} Themen bewertet werden."""
        n = len(topics)
        ratings = self.llm.complete_json("topic_scores", system, user, lambda d: validate_topic_scores(d, n))
        w = self.cfg.topics.weights.to_dict()
        for r in ratings:
            t = topics[r["id"]]
            t.scores = {k: r[k] for k in w if k in r}
            t.category = r.get("category") or t.category
            t.angle = r.get("angle") or t.angle
            t.total_score = round(sum(t.scores.get(k, 0.0) * wt for k, wt in w.items()), 3)
        return sorted(topics, key=lambda t: t.total_score, reverse=True)

    def pick_best(self, ranked: List[Topic], used_titles: List[str]) -> Topic:
        used = {u.lower() for u in used_titles}
        for t in ranked:
            if t.title.lower() not in used:
                return t
        if ranked:
            log.warning("Alle Kandidaten wurden schon verwendet - nehme das hoechstbewertete erneut")
            return ranked[0]
        raise PipelineError("Keine Themen gefunden")

    def from_title(self, title: str) -> Topic:
        """Manuelles Thema (--topic): wird ebenfalls mit Wikipedia belegt."""
        topic = self._wikipedia_topic(title, source="manual", category="")
        if topic is None:
            raise PipelineError(f"Zu '{title}' gibt es keinen Wikipedia-Artikel als Faktenbasis. "
                                f"Bitte einen anderen Titel waehlen (z.B. exakter Artikelname).")
        return topic

    def save(self, topics: List[Topic]) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        save_json(self.cfg.path(f"data/topics/topics_{stamp}.json"), [t.to_dict() for t in topics])

    # ------------------------------------------------------------ Hilfen
    def _min_chars(self, topic: Topic) -> int:
        return 0 if topic.source == "samples" else int(self.cfg.topics.min_grounding_chars)

    @staticmethod
    def _dedupe(topics: List[Topic]) -> List[Topic]:
        seen, out = set(), []
        for t in topics:
            key = t.title.lower()
            if key not in seen:
                seen.add(key)
                out.append(t)
        return out

    def _wiki_api(self) -> str:
        return f"https://{self.lang}.wikipedia.org/w/api.php"

    def _wikipedia_extract(self, title: str) -> Optional[Dict[str, str]]:
        """Holt Klartext + kanonischen Titel + URL eines Wikipedia-Artikels (None = nicht vorhanden)."""
        params = {"action": "query", "format": "json", "prop": "extracts|info", "explaintext": 1,
                  "exchars": 3500, "redirects": 1, "inprop": "url", "titles": title}
        data = http_get(self._wiki_api(), params=params).json()
        for page in data.get("query", {}).get("pages", {}).values():
            if "missing" in page or not page.get("extract"):
                return None
            text = re.sub(r"\n{3,}", "\n\n", page["extract"]).strip()
            return {"title": page.get("title", title), "text": text, "url": page.get("fullurl", "")}
        return None

    def _wikipedia_topic(self, title: str, source: str, category: str,
                         prefix: str = "") -> Optional[Topic]:
        try:
            page = self._wikipedia_extract(title)
        except Exception as exc:
            log.debug(f"Wikipedia-Abruf '{title}' fehlgeschlagen: {exc}")
            return None
        if not page:
            return None
        return Topic(title=page["title"], source=source, source_url=page["url"],
                     grounding=(prefix + page["text"]).strip(), category=category)

    # ------------------------------------------------------------ Quellen
    def _feed(self) -> Dict[str, Any]:
        """Wikimedia-Feed von gestern (heute ist oft noch nicht vollstaendig)."""
        day = datetime.now(timezone.utc) - timedelta(days=1)
        url = (f"https://api.wikimedia.org/feed/v1/wikipedia/{self.lang}/featured/"
               f"{day:%Y}/{day:%m}/{day:%d}")
        return http_get(url).json()

    def _wikipedia_mostread(self) -> List[Topic]:
        articles = self._feed().get("mostread", {}).get("articles", [])
        out: List[Topic] = []
        for art in articles:
            title = art.get("normalizedtitle") or art.get("title", "").replace("_", " ")
            if not title or art.get("title", "").startswith(_SKIP_PREFIXES):
                continue
            t = self._wikipedia_topic(title, "wikipedia_mostread", "spannende aktuelle Themen")
            if t:
                out.append(t)
            if len(out) >= self.cfg.topics.count_per_source:
                break
        return out

    def _wikipedia_onthisday(self) -> List[Topic]:
        events = self._feed().get("onthisday", [])
        out: List[Topic] = []
        for ev in events:
            text = html.unescape(ev.get("text", "")).strip()
            year = ev.get("year")
            pages = ev.get("pages") or []
            if not text or not pages:
                continue
            main = pages[0]
            title = main.get("normalizedtitle") or main.get("title", "").replace("_", " ")
            t = self._wikipedia_topic(title, "wikipedia_onthisday", "Geschichte",
                                      prefix=f"Ereignis im Jahr {year}: {text}\n\n")
            if t:
                t.title = f"{t.title} ({year})"
                out.append(t)
            if len(out) >= self.cfg.topics.count_per_source // 2 + 2:
                break
        return out

    def _hackernews(self) -> List[Topic]:
        ids = http_get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:40]
        out: List[Topic] = []
        for sid in ids:
            try:
                item = http_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json").json()
            except Exception:
                continue
            url = (item or {}).get("url")
            if not item or item.get("type") != "story" or not url or item.get("score", 0) < 150:
                continue
            text = self._article_text(url)
            if len(text) < 600:
                continue
            out.append(Topic(title=item["title"], source="hackernews", source_url=url,
                             grounding=f"Titel: {item['title']}\nQuelle: {url}\n\n{text}",
                             category="Technologie"))
            if len(out) >= self.cfg.topics.count_per_source // 2:
                break
        return out

    @staticmethod
    def _article_text(url: str) -> str:
        """Sehr einfache Textextraktion (Absaetze); reicht als Faktenbasis, kein Anspruch auf Perfektion."""
        try:
            resp = http_get(url, timeout=15)
            if "html" not in resp.headers.get("content-type", ""):
                return ""
            body = re.sub(r"(?is)<(script|style|nav|footer|header|aside).*?</\1>", " ", resp.text)
            paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)
            cleaned = [html.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in paras]
            return "\n".join(p for p in cleaned if len(p) > 60)[:3500]
        except Exception:
            return ""

    def _llm_evergreen(self) -> List[Topic]:
        n = int(self.cfg.topics.max_llm_brainstorm)
        system = "Du bist Redakteur fuer Wissens-Kurzvideos. Antworte ausschliesslich mit gueltigem JSON."
        user = f"""Nenne {n} faszinierende, ueberraschende Themen fuer TikTok-Wissensvideos.
Kategorien: {', '.join(self.cfg.topics.categories)}.
WICHTIG: Gib fuer jedes Thema den exakten Titel eines REAL existierenden Wikipedia-Artikels
(Sprache: {self.lang}) an - nur Themen, die du sicher dort findest. Keine Behauptungen, nur Titel.
JSON: {{"topics": [{{"wikipedia_title": "", "category": ""}}]}}"""
        items = self.llm.complete_json("brainstorm", system, user, validate_brainstorm)
        out = []
        for it in items[:n]:
            t = self._wikipedia_topic(it["wikipedia_title"], "llm_evergreen", it["category"])
            if t:
                out.append(t)
            else:
                log.debug(f"Brainstorm-Thema ohne Wikipedia-Artikel verworfen: {it['wikipedia_title']}")
        return out

    def _samples(self) -> List[Topic]:
        data = load_json(self.cfg.path("data/samples/topics.json"), [])
        return [Topic(**{k: v for k, v in d.items() if k in Topic.__dataclass_fields__}) for d in data]
