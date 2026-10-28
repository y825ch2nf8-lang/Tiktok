"""Logging im Format `[INFO] Nachricht` plus Datei-Log."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")

_COLORS = {
    "DEBUG": "\033[90m",
    "INFO": "\033[36m",
    "SUCCESS": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[41m",
}
_RESET = "\033[0m"


class _Formatter(logging.Formatter):
    def __init__(self, color: bool) -> None:
        super().__init__("[%(levelname)s] %(message)s")
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if self.color:
            return f"{_COLORS.get(record.levelname, '')}{text}{_RESET}"
        return text


class BotLogger(logging.Logger):
    def success(self, msg: str, *args: object, **kwargs: object) -> None:
        if self.isEnabledFor(SUCCESS):
            self._log(SUCCESS, msg, args, **kwargs)  # type: ignore[arg-type]


logging.setLoggerClass(BotLogger)
log: BotLogger = logging.getLogger("tiktok_bot")  # type: ignore[assignment]


def setup_logging(log_dir: Optional[Path] = None, verbose: bool = False) -> BotLogger:
    """Konfiguriert Konsole (+ optional Datei). Mehrfachaufruf ist harmlos."""
    log.handlers.clear()
    log.setLevel(logging.DEBUG)
    log.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(_Formatter(color=sys.stdout.isatty()))
    log.addHandler(console)

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "tiktok_bot.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(fh)
    return log
