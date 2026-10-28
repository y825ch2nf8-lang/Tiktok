"""Hilfsfunktionen: Retry, FFmpeg/FFprobe, JSON-Extraktion, HTTP, Dateinamen."""
from __future__ import annotations

import functools
import json
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, Tuple, Type, TypeVar

import requests

from .logger import log

T = TypeVar("T")

USER_AGENT = "tiktok-bot/1.0 (educational content automation)"


class PipelineError(RuntimeError):
    """Fehler in einem Pipeline-Schritt (mit lesbarer Meldung)."""


# ---------------------------------------------------------------- Retry
def retry(
    attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    no_retry: Tuple[Type[BaseException], ...] = (NotImplementedError,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Dekorator: wiederholt eine Funktion mit exponentiellem Backoff."""

    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            wait = delay
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except no_retry:
                    raise
                except exceptions as exc:
                    if attempt == attempts:
                        raise
                    log.warning(f"{fn.__name__} fehlgeschlagen ({exc}); Versuch {attempt}/{attempts}, "
                                f"neuer Versuch in {wait:.0f}s")
                    time.sleep(wait)
                    wait *= backoff
            raise AssertionError("unreachable")

        return wrapper

    return deco


# ---------------------------------------------------------------- FFmpeg
def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise PipelineError(
            f"'{name}' wurde nicht gefunden. Bitte FFmpeg installieren und zum PATH hinzufuegen (siehe README)."
        )
    return path


def run_ffmpeg(args: Sequence[str], desc: str = "ffmpeg", cwd: Optional[Path] = None) -> None:
    """Fuehrt ffmpeg aus; wirft PipelineError mit dem Ende des Fehlerlogs.

    `cwd` erlaubt relative Dateinamen in Filtern (vermeidet Escaping-Probleme mit Windows-Pfaden).
    """
    cmd = [require_binary("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", *map(str, args)]
    log.debug("ffmpeg: " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd) if cwd else None)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-12:])
        raise PipelineError(f"{desc} fehlgeschlagen (Exit {proc.returncode}):\n{tail}")


def probe_duration(path: Path) -> float:
    """Dauer einer Audio-/Videodatei in Sekunden."""
    cmd = [require_binary("ffprobe"), "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(proc.stdout.strip())
    except ValueError:
        raise PipelineError(f"Dauer von {path} konnte nicht gelesen werden: {proc.stderr.strip()}") from None


def probe_video_size(path: Path) -> Tuple[int, int]:
    cmd = [require_binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    try:
        w, h = out.split("x")
        return int(w), int(h)
    except ValueError:
        raise PipelineError(f"Videogroesse von {path} unlesbar") from None


# ---------------------------------------------------------------- JSON
def extract_json(text: str) -> Any:
    """Zieht das erste JSON-Objekt/-Array aus einer LLM-Antwort (auch mit ```-Zaeunen)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Ausgewogene Klammern suchen
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break
            start = text.find(opener, start + 1)
    raise ValueError("Kein gueltiges JSON in der Antwort gefunden")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)


def load_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


# ---------------------------------------------------------------- HTTP
def http_get(url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None,
             timeout: float = 20) -> requests.Response:
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    return resp


def download_file(url: str, dest: Path, timeout: float = 60) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
    return dest


# ---------------------------------------------------------------- Text
def slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].strip("-") or "video"


_WORD_RE = re.compile(r"\S+")


def tokenize_words(text: str) -> list[str]:
    """Wort-Tokenisierung, die ueberall (TTS, Szenen, Untertitel) identisch genutzt wird."""
    return _WORD_RE.findall(text)


def normalize_word(word: str) -> str:
    return re.sub(r"[^\w]", "", word, flags=re.UNICODE).lower()


def hex_to_ass(color: str, alpha: int = 0) -> str:
    """'#RRGGBB' -> ASS '&HAABBGGRR'."""
    c = color.lstrip("#")
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper().replace("&H", "&H", 1)
