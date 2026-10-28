"""Schnelle Unit-Tests (kein Netzwerk). Voller Testlauf: RUN_SLOW=1 pytest."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import load_config  # noqa: E402
from src.models import ContentPackage, Scene, VoiceResult  # noqa: E402
from src.schema import ValidationError, validate_caption, validate_script  # noqa: E402
from src.subtitle_generator import SubtitleGenerator  # noqa: E402
from src.utils import extract_json, load_json, tokenize_words  # noqa: E402
from src.voice_generator import MockTTS, map_tokens_to_times  # noqa: E402


@pytest.fixture()
def cfg():
    return load_config(test_mode=True)


def test_extract_json_handles_fences_and_noise():
    assert extract_json('Hier:\n```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}
    assert extract_json('Text vor {"a": "}"} Text danach') == {"a": "}"}
    with pytest.raises(ValueError):
        extract_json("kein json")


def test_sample_script_is_valid(cfg):
    data = validate_script(load_json(ROOT / "data/samples/script.json"), cfg)
    assert data["scenes"][0]["role"] == "hook"
    assert 20 <= data["duration"] <= 45


def test_script_validation_reports_errors(cfg):
    data = load_json(ROOT / "data/samples/script.json")
    data["scenes"] = data["scenes"][:3]
    with pytest.raises(ValidationError) as exc:
        validate_script(data, cfg)
    assert any("Szenen" in e for e in exc.value.errors)


def test_caption_validation_normalizes_hashtags(cfg):
    out = validate_caption({"caption": "x", "hashtags": ["wissen", "#fakten", "#Fakten", "mystery"]}, cfg)
    assert out["hashtags"] == ["#wissen", "#fakten", "#mystery"]


def test_timing_mapping_is_monotonic_and_complete():
    tokens = ["Hallo", "Welt,", "das", "ist", "ein", "Test."]
    words = map_tokens_to_times(tokens, None, 0.5, 4.5)
    assert len(words) == len(tokens)
    assert words[0].start == pytest.approx(0.5)
    assert words[-1].end == pytest.approx(4.5, abs=0.1)
    assert all(a.end <= b.start + 1e-6 for a, b in zip(words, words[1:]))


def test_subtitles_ass(cfg, tmp_path):
    scenes = [Scene(0, "hook", "Dieses Tier hat 3 Herzen.", "p", "q", emphasis=["Tier"], start=0, end=2),
              Scene(1, "cta", "Folge mir jetzt.", "p", "q", start=2, end=3.5)]
    pkg = ContentPackage("t", "t", "h", [], " ".join(s.narration for s in scenes), 3.5, scenes, "c", ["#a"], "cta")
    words = map_tokens_to_times(tokenize_words(pkg.script), None, 0.2, 3.3)
    voice = VoiceResult(tmp_path / "v.mp3", 3.5, words, "mock", "estimated")
    path = SubtitleGenerator(cfg).generate(pkg, voice, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in text and "PlayResY: 1920" in text
    assert text.count("Dialogue:") >= len(words)
    assert "3" in text and "TIER" in text


@pytest.mark.skipif(not os.environ.get("RUN_SLOW"), reason="vollstaendiger Render dauert einige Minuten")
def test_full_pipeline_in_test_mode(tmp_path):
    from main import main
    assert main(["--test"]) == 0
