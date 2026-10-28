"""Zentrale Konfiguration.

Laedt `config.yaml` (Einstellungen) und `.env` (API-Keys) und stellt beides als
`Config`-Objekt bereit. Zugriff per Attribut: ``cfg.audio.music_volume``.
Keys stehen ausschliesslich in der Umgebung / `.env`, nie im Code.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


class Section:
    """Duenner Wrapper um ein Dict mit Attribut-Zugriff (rekursiv)."""

    def __init__(self, data: Dict[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        try:
            value = self._data[name]
        except KeyError:
            raise AttributeError(f"Unbekannte Config-Option: '{name}'") from None
        return Section(value) if isinstance(value, dict) else value

    def __setattr__(self, name: str, value: Any) -> None:
        self._data[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        value = self._data.get(name, default)
        return Section(value) if isinstance(value, dict) else value

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class Config(Section):
    """Gesamtkonfiguration inkl. Secrets, Pfaden und Testmodus-Flag."""

    def __init__(self, data: Dict[str, Any], test_mode: bool = False) -> None:
        super().__init__(data)
        object.__setattr__(self, "test_mode", test_mode)
        object.__setattr__(self, "root", PROJECT_ROOT)

    # --- Secrets (nur aus Umgebung) -------------------------------------
    @staticmethod
    def secret(name: str) -> str:
        return os.environ.get(name, "").strip()

    @property
    def llm_api_key(self) -> str:
        return self.secret("LLM_API_KEY")

    @property
    def tts_api_key(self) -> str:
        return self.secret("TTS_API_KEY")

    @property
    def image_api_key(self) -> str:
        return self.secret("IMAGE_API_KEY")

    @property
    def video_api_key(self) -> str:
        return self.secret("VIDEO_API_KEY")

    @property
    def stock_api_key(self) -> str:
        return self.secret("STOCK_API_KEY")

    # --- Pfade -----------------------------------------------------------
    def path(self, relative: str) -> Path:
        p = Path(relative)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def finished_dir(self) -> Path:
        return self.path(self.export.output_dir)

    @property
    def work_root(self) -> Path:
        return self.path(self.export.work_dir)

    @property
    def log_dir(self) -> Path:
        return self.path("output/logs")

    @property
    def cache_dir(self) -> Path:
        return self.path("data/cache")


TEST_OVERRIDES: Dict[str, Any] = {
    "voice": {"provider": "mock", "fallback_providers": ["mock"]},
    "visuals": {"providers": ["local", "procedural"]},
    "topics": {"sources": ["samples"]},
    "editing": {"video_preset": "veryfast", "video_crf": 23},
}


def load_config(path: Optional[Path] = None, test_mode: bool = False) -> Config:
    """Laedt .env und config.yaml. Im Testmodus werden teure Anbieter abgeschaltet."""
    load_dotenv(PROJECT_ROOT / ".env")
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if test_mode:
        _deep_merge(data, copy.deepcopy(TEST_OVERRIDES))

    # Umgebungsvariablen duerfen einzelne Optionen ueberschreiben
    env_map = {
        "LLM_PROVIDER": ("llm", "provider"),
        "LLM_MODEL": ("llm", "model"),
        "TTS_PROVIDER": ("voice", "provider"),
    }
    if not test_mode:
        for env_name, (sec, key) in env_map.items():
            value = os.environ.get(env_name, "").strip()
            if value:
                data.setdefault(sec, {})[key] = value

    return Config(data, test_mode=test_mode)
