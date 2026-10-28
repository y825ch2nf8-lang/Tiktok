"""LLM-Schnittstelle mit automatischem Retry bei ungueltigem JSON.

`LLMClient.complete_json()` ruft das Modell auf, extrahiert JSON, validiert es
und meldet Validierungsfehler im naechsten Versuch zurueck ans Modell.
Der Testmodus nutzt `MockLLMClient` (keine API-Aufrufe, Beispieldaten aus data/samples).
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

import requests

from config import Config
from .logger import log
from .utils import PipelineError, extract_json, load_json

Validator = Callable[[Any], Any]


class LLMClient(ABC):
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    @abstractmethod
    def _chat(self, system: str, messages: List[Dict[str, str]]) -> str:
        """Ein Aufruf, liefert den Antworttext."""

    def complete_json(self, task: str, system: str, user: str, validator: Validator,
                      max_retries: Optional[int] = None) -> Any:
        """Fragt das Modell nach JSON, validiert und wiederholt bei Fehlern."""
        retries = max_retries if max_retries is not None else self.cfg.content.max_retries
        messages: List[Dict[str, str]] = [{"role": "user", "content": user}]
        last_error = "unbekannt"
        for attempt in range(1, retries + 1):
            try:
                text = self._chat(system, messages)
            except PipelineError:
                raise
            except Exception as exc:  # Netzwerk, Rate-Limit, ...
                last_error = f"API-Fehler: {exc}"
                log.warning(f"[{task}] {last_error} (Versuch {attempt}/{retries})")
                time.sleep(min(2 ** attempt, 20))
                continue
            try:
                return validator(extract_json(text))
            except Exception as exc:
                errs = getattr(exc, "errors", None) or [str(exc)]
                last_error = "; ".join(errs)
                log.warning(f"[{task}] Ungueltige LLM-Antwort (Versuch {attempt}/{retries}): {last_error}")
                messages = [
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": text},
                    {"role": "user", "content":
                        "Deine Antwort war ungueltig. Fehler:\n- " + "\n- ".join(errs) +
                        "\nGib die KOMPLETTE korrigierte Antwort erneut aus - ausschliesslich als gueltiges JSON, "
                        "ohne Erklaerung und ohne Markdown."},
                ]
        raise PipelineError(f"LLM-Aufgabe '{task}' nach {retries} Versuchen fehlgeschlagen: {last_error}")


class AnthropicClient(LLMClient):
    URL = "https://api.anthropic.com/v1/messages"

    def _chat(self, system: str, messages: List[Dict[str, str]]) -> str:
        key = self.cfg.llm_api_key
        if not key:
            raise PipelineError("LLM_API_KEY fehlt. Trage ihn in die .env ein (siehe README) oder nutze --test.")
        body = {
            "model": self.cfg.llm.model,
            "max_tokens": self.cfg.llm.max_tokens,
            "temperature": self.cfg.llm.temperature,
            "system": system,
            "messages": messages,
        }
        resp = requests.post(
            self.URL, json=body, timeout=self.cfg.llm.timeout,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        )
        if resp.status_code in (401, 403):
            raise PipelineError(f"LLM-Zugriff verweigert ({resp.status_code}): LLM_API_KEY pruefen. {resp.text[:200]}")
        if resp.status_code == 404:
            raise PipelineError(f"Modell '{self.cfg.llm.model}' nicht gefunden: {resp.text[:200]}")
        resp.raise_for_status()
        parts = resp.json().get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


class OpenAICompatibleClient(LLMClient):
    """OpenAI /v1/chat/completions (auch fuer kompatible Server via LLM_BASE_URL)."""

    def _chat(self, system: str, messages: List[Dict[str, str]]) -> str:
        key = self.cfg.llm_api_key
        if not key:
            raise PipelineError("LLM_API_KEY fehlt. Trage ihn in die .env ein.")
        base = (self.cfg.secret("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        body = {
            "model": self.cfg.llm.model,
            "temperature": self.cfg.llm.temperature,
            "messages": [{"role": "system", "content": system}, *messages],
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(f"{base}/chat/completions", json=body, timeout=self.cfg.llm.timeout,
                             headers={"Authorization": f"Bearer {key}"})
        if resp.status_code in (401, 403):
            raise PipelineError(f"LLM-Zugriff verweigert ({resp.status_code}): LLM_API_KEY pruefen.")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class MockLLMClient(LLMClient):
    """Testmodus: liefert Beispieldaten aus data/samples/, ohne Netzwerk."""

    def _chat(self, system: str, messages: List[Dict[str, str]]) -> str:  # pragma: no cover
        raise PipelineError("MockLLMClient hat keinen Chat - nutze complete_json().")

    def complete_json(self, task: str, system: str, user: str, validator: Validator,
                      max_retries: Optional[int] = None) -> Any:
        sample = load_json(self.cfg.path(f"data/samples/{task}.json"))
        if sample is None:
            raise PipelineError(f"Testdaten data/samples/{task}.json fehlen")
        log.debug(f"[{task}] Testmodus: verwende Beispieldaten")
        return validator(sample)


def create_llm(cfg: Config) -> LLMClient:
    if cfg.test_mode:
        return MockLLMClient(cfg)
    provider = str(cfg.llm.provider).lower()
    if provider == "anthropic":
        return AnthropicClient(cfg)
    if provider == "openai":
        return OpenAICompatibleClient(cfg)
    raise PipelineError(f"Unbekannter LLM-Provider '{provider}' (erlaubt: anthropic, openai)")
