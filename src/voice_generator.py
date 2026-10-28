"""Voice-over: austauschbare TTS-Anbieter hinter einer gemeinsamen Schnittstelle.

Neuen Anbieter hinzufuegen:
  1. Klasse von `TTSProvider` ableiten und `synthesize()` implementieren
  2. In `PROVIDERS` eintragen
  3. In config.yaml unter voice.provider auswaehlen

Wort-Timing: Anbieter mit exakten Zeitstempeln (edge, elevenlabs, mock) liefern diese direkt.
Alle anderen werden ueber `map_tokens_to_times()` aus der Audiodauer geschaetzt.
"""
from __future__ import annotations

import asyncio
import base64
import math
import random
import struct
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Type

import requests

from config import Config
from .logger import log
from .models import ContentPackage, VoiceResult, WordTiming
from .utils import PipelineError, probe_duration, run_ffmpeg, tokenize_words


@dataclass
class RawSpeech:
    """Rohergebnis eines Anbieters (vor Padding / Tempo-Anpassung)."""
    path: Path
    words: Optional[List[WordTiming]]      # None = keine Zeitstempel verfuegbar


class TTSProvider(ABC):
    name = "base"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    @abstractmethod
    def synthesize(self, text: str, out_path: Path) -> RawSpeech:
        """Schreibt Audio nach out_path (mp3/wav) und liefert optional Wort-Zeitstempel."""


# ------------------------------------------------------------------ Edge (kostenlos, kein Key)
class EdgeTTS(TTSProvider):
    name = "edge"

    def synthesize(self, text: str, out_path: Path) -> RawSpeech:
        try:
            import edge_tts
        except ImportError:
            raise PipelineError("Paket 'edge-tts' fehlt: pip install edge-tts") from None
        v = self.cfg.voice

        async def run() -> List[WordTiming]:
            kwargs = dict(voice=v.edge_voice, rate=v.edge_rate, pitch=v.edge_pitch)
            try:
                comm = edge_tts.Communicate(text, boundary="WordBoundary", **kwargs)
            except TypeError:                       # aeltere Versionen kennen `boundary` nicht
                comm = edge_tts.Communicate(text, **kwargs)
            words: List[WordTiming] = []
            with open(out_path, "wb") as fh:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        fh.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / 1e7           # 100-ns-Einheiten
                        words.append(WordTiming(chunk["text"], start, start + chunk["duration"] / 1e7))
            return words

        words = asyncio.run(run())
        if not out_path.exists() or out_path.stat().st_size < 1000:
            raise PipelineError("Edge-TTS lieferte kein Audio (Netzwerk/Firewall?)")
        return RawSpeech(out_path, words or None)


# ------------------------------------------------------------------ ElevenLabs
class ElevenLabsTTS(TTSProvider):
    name = "elevenlabs"

    def synthesize(self, text: str, out_path: Path) -> RawSpeech:
        key = self.cfg.tts_api_key
        v = self.cfg.voice
        if not key:
            raise PipelineError("TTS_API_KEY fehlt (ElevenLabs).")
        if not v.elevenlabs_voice_id:
            raise PipelineError("voice.elevenlabs_voice_id fehlt in config.yaml (Voice-ID aus der ElevenLabs-Bibliothek).")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{v.elevenlabs_voice_id}/with-timestamps"
        body = {
            "text": text,
            "model_id": v.elevenlabs_model,
            "voice_settings": {"stability": v.elevenlabs_stability, "similarity_boost": v.elevenlabs_similarity,
                               "style": v.elevenlabs_style, "use_speaker_boost": True},
        }
        resp = requests.post(url, json=body, params={"output_format": "mp3_44100_128"},
                             headers={"xi-api-key": key}, timeout=120)
        if resp.status_code in (401, 403):
            raise PipelineError(f"ElevenLabs verweigert Zugriff ({resp.status_code}): TTS_API_KEY pruefen. {resp.text[:200]}")
        resp.raise_for_status()
        data = resp.json()
        out_path.write_bytes(base64.b64decode(data["audio_base64"]))
        words = self._words_from_alignment(data.get("alignment") or data.get("normalized_alignment"))
        return RawSpeech(out_path, words)

    @staticmethod
    def _words_from_alignment(al: Optional[dict]) -> Optional[List[WordTiming]]:
        if not al:
            return None
        chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
        words: List[WordTiming] = []
        buf, w_start, w_end = "", 0.0, 0.0
        for ch, s, e in zip(chars, starts, ends):
            if ch.isspace():
                if buf:
                    words.append(WordTiming(buf, w_start, w_end))
                    buf = ""
                continue
            if not buf:
                w_start = s
            buf += ch
            w_end = e
        if buf:
            words.append(WordTiming(buf, w_start, w_end))
        return words or None


# ------------------------------------------------------------------ OpenAI TTS
class OpenAITTS(TTSProvider):
    name = "openai"

    def synthesize(self, text: str, out_path: Path) -> RawSpeech:
        key = self.cfg.tts_api_key
        if not key:
            raise PipelineError("TTS_API_KEY fehlt (OpenAI).")
        v = self.cfg.voice
        body = {"model": v.openai_model, "voice": v.openai_voice, "input": text, "response_format": "mp3"}
        if "tts" in v.openai_model and v.openai_instructions:
            body["instructions"] = v.openai_instructions
        resp = requests.post("https://api.openai.com/v1/audio/speech", json=body,
                             headers={"Authorization": f"Bearer {key}"}, timeout=120)
        if resp.status_code in (401, 403):
            raise PipelineError(f"OpenAI-TTS verweigert Zugriff ({resp.status_code}): TTS_API_KEY pruefen.")
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
        return RawSpeech(out_path, None)           # keine Zeitstempel -> Schaetzung


# ------------------------------------------------------------------ Mock (Testmodus)
class MockTTS(TTSProvider):
    """Erzeugt lokal ein sanftes "Sprach-Placeholder"-Audio (kurze Toene je Wort). Keine Netzwerk-/API-Nutzung."""
    name = "mock"
    RATE = 24000

    def synthesize(self, text: str, out_path: Path) -> RawSpeech:
        tokens = tokenize_words(text)
        rng = random.Random(7)
        t, words, spans = 0.0, [], []
        for tok in tokens:
            dur = 0.07 * max(2, len(tok)) + 0.03
            words.append(WordTiming(tok, t, t + dur))
            spans.append((t, t + dur, rng.choice([150, 165, 180, 200])))
            t += dur + 0.04
            if tok[-1] in ".!?":
                t += 0.35
            elif tok[-1] in ",;:":
                t += 0.15
        total = t + 0.2
        n = int(total * self.RATE)
        samples = [0] * n
        for s, e, freq in spans:
            i0, i1 = int(s * self.RATE), int(e * self.RATE)
            for i in range(i0, min(i1, n)):
                x = (i - i0) / max(1, i1 - i0)
                env = math.sin(math.pi * x) ** 1.5
                tt = i / self.RATE
                v = math.sin(2 * math.pi * freq * tt) + 0.5 * math.sin(2 * math.pi * freq * 2 * tt)
                samples[i] = int(3500 * env * v)
        wav_path = out_path.with_suffix(".wav")
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.RATE)
            wf.writeframes(struct.pack(f"<{n}h", *samples))
        run_ffmpeg(["-i", wav_path, "-codec:a", "libmp3lame", "-b:a", "128k", out_path], "Mock-TTS-Konvertierung")
        wav_path.unlink(missing_ok=True)
        return RawSpeech(out_path, words)


PROVIDERS: Dict[str, Type[TTSProvider]] = {
    "edge": EdgeTTS, "elevenlabs": ElevenLabsTTS, "openai": OpenAITTS, "mock": MockTTS,
}


# ------------------------------------------------------------------ Timing-Logik
def map_tokens_to_times(tokens: List[str], source: Optional[List[WordTiming]], span_start: float,
                        span_end: float) -> List[WordTiming]:
    """Ordnet *unsere* Tokens Zeiten zu.

    * Mit Anbieter-Zeitstempeln: stueckweise lineare Abbildung ueber die Zeichenposition
      (robust, auch wenn Anbieter Woerter anders trennen, z.B. Zahlen).
    * Ohne: gleichmaessig verteilt, gewichtet nach Wortlaenge + Satzzeichen-Pausen.
    """
    def weight(tok: str) -> float:
        w = float(max(1, len(tok.strip(".,!?;:\"'()-"))))
        if tok[-1:] in ".!?":
            w += 5
        elif tok[-1:] in ",;:":
            w += 2
        return w

    weights = [weight(t) for t in tokens]
    total = sum(weights)
    bounds, acc = [], 0.0
    for w in weights:
        bounds.append((acc / total, (acc + w) / total))
        acc += w

    if source:
        sw = [float(max(1, len(s.text))) for s in source]
        stotal = sum(sw)
        cum, anchors = 0.0, []                     # (Zeichenanteil, Zeit)
        for s, w in zip(source, sw):
            anchors.append((cum / stotal, s.start))
            cum += w
            anchors.append((cum / stotal, s.end))

        def f(frac: float) -> float:
            if frac <= anchors[0][0]:
                return anchors[0][1]
            for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
                if frac <= x1:
                    return y0 if x1 == x0 else y0 + (y1 - y0) * (frac - x0) / (x1 - x0)
            return anchors[-1][1]

        out = [WordTiming(t, f(a), f(b)) for t, (a, b) in zip(tokens, bounds)]
    else:
        span = span_end - span_start
        out = [WordTiming(t, span_start + a * span, span_start + b * span) for t, (a, b) in zip(tokens, bounds)]

    # Monotonie sicherstellen
    last = 0.0
    for w in out:
        w.start = max(w.start, last)
        w.end = max(w.end, w.start + 0.05)
        last = w.end
    return out


# ------------------------------------------------------------------ Orchestrierung
class VoiceGenerator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def _provider_chain(self) -> List[str]:
        chain = [self.cfg.voice.provider, *self.cfg.voice.fallback_providers]
        return list(dict.fromkeys(chain))

    def generate(self, content: ContentPackage, audio_dir: Path) -> VoiceResult:
        audio_dir.mkdir(parents=True, exist_ok=True)
        text = " ".join(s.narration for s in content.scenes)
        tokens = tokenize_words(text)
        errors: List[str] = []
        for name in self._provider_chain():
            cls = PROVIDERS.get(name)
            if cls is None:
                errors.append(f"{name}: unbekannter Anbieter")
                continue
            provider = cls(self.cfg)
            for attempt in (1, 2):
                try:
                    log.info(f"Generiere Voice-over ({name})...")
                    raw = provider.synthesize(text, audio_dir / "raw_voice.mp3")
                    return self._finish(raw, tokens, audio_dir, name)
                except NotImplementedError as exc:
                    errors.append(f"{name}: {exc}")
                    break
                except PipelineError as exc:                      # Konfigurationsfehler -> kein Retry
                    errors.append(f"{name}: {exc}")
                    log.warning(f"TTS '{name}' nicht nutzbar: {exc}")
                    break
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
                    log.warning(f"TTS '{name}' Versuch {attempt}/2 fehlgeschlagen: {exc}")
        raise PipelineError("Voice-over konnte mit keinem Anbieter erzeugt werden:\n  " + "\n  ".join(errors))

    def _finish(self, raw: RawSpeech, tokens: List[str], audio_dir: Path, provider: str) -> VoiceResult:
        v = self.cfg.voice
        raw_dur = probe_duration(raw.path)
        pad_start, pad_end = float(v.pad_start), float(v.pad_end)

        speed = 1.0
        total = raw_dur + pad_start + pad_end
        if total > self.cfg.content.max_duration:
            speed = min(float(v.max_speedup), total / self.cfg.content.max_duration)
            log.warning(f"Voice-over {total:.1f}s ist laenger als {self.cfg.content.max_duration}s -> Tempo x{speed:.2f}")

        out = audio_dir / "voiceover.mp3"
        filters = []
        if speed > 1.001:
            filters.append(f"atempo={speed:.4f}")
        filters.append(f"adelay={int(pad_start * 1000)}:all=1")
        filters.append(f"apad=pad_dur={pad_end}")
        run_ffmpeg(["-i", raw.path, "-af", ",".join(filters), "-ar", "44100", "-ac", "2",
                    "-codec:a", "libmp3lame", "-b:a", "192k", out], "Voice-over-Nachbearbeitung")
        duration = probe_duration(out)

        scaled = None
        if raw.words:
            scaled = [WordTiming(w.text, w.start / speed + pad_start, w.end / speed + pad_start) for w in raw.words]
        speech_end = pad_start + raw_dur / speed
        words = map_tokens_to_times(tokens, scaled, pad_start, speech_end)
        source = "provider" if scaled else "estimated"
        log.info(f"Voice-over fertig: {duration:.1f}s, Wort-Timing: "
                 f"{'exakt (Anbieter)' if scaled else 'geschaetzt'}")
        return VoiceResult(audio_path=out, duration=duration, words=words, provider=provider, timing_source=source)


def assign_scene_times(content: ContentPackage, voice: VoiceResult) -> None:
    """Setzt scene.start/end anhand der Wort-Zeiten (Szene beginnt mit ihrem ersten Wort)."""
    idx = 0
    n_scenes = len(content.scenes)
    for i, scene in enumerate(content.scenes):
        count = len(tokenize_words(scene.narration))
        first = voice.words[idx]
        scene.start = 0.0 if i == 0 else first.start
        idx += count
        scene.end = voice.duration if i == n_scenes - 1 else voice.words[min(idx, len(voice.words) - 1)].start
    # Luecken/Ueberlappungen glaetten
    for a, b in zip(content.scenes, content.scenes[1:]):
        b.start = a.end = max(a.start + 0.3, min(a.end, b.start))
