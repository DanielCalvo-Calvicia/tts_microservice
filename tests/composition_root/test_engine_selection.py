"""Which engine the service starts with, and that a missing Piper voice never takes the service down."""

import asyncio

import pytest
from shared_logging.testing import capture

from composition_root.dependencies import tts_dependencies as deps
from domain.value_objects.audio_format import AudioFormat
from infrastructure.config.tts_config import TtsConfig
from infrastructure.outbound.espeak_speech.espeak_speech_synthesis import EspeakSpeechSynthesis
from infrastructure.outbound.piper_speech.piper_speech_synthesis import PiperSpeechSynthesis
from infrastructure.outbound.pyttsx3_speech.pyttsx3_speech_synthesis import Pyttsx3SpeechSynthesis

ALAN = "en_GB-alan-medium"
PIPER_FALLBACK = "Piper unavailable; falling back to pyttsx3"
ESPEAK_FALLBACK = "espeak unavailable; falling back to pyttsx3"
SELECTION_LOGGER = "composition_root.dependencies.tts_dependencies"


def _fallback_records(logs):
    """Every record that says a fallback happened. The deployment documents, the failure drill and the Docker
    checks look for these lines, so they must keep being written (constant message, keyword field ``reason``)."""
    return [record for record in logs.records if "falling back" in record["message"]]


def _the_one_fallback_record(logs, message):
    records = _fallback_records(logs)
    assert [record["message"] for record in records] == [message]
    record = records[0]
    assert record["level"] == "ERROR"
    assert record["logger"] == SELECTION_LOGGER
    assert isinstance(record["reason"], str) and record["reason"].strip()
    return record


def test_piper_is_the_default_engine_when_its_voice_loads(tmp_path, monkeypatch):
    class FakeLoaded:
        sample_rate = 22050

        def synthesize(self, text, speed):
            raise AssertionError("not spoken in this test")

    loaded = []
    monkeypatch.setattr(
        deps.PiperEngine,
        "load",
        lambda model_dir, voice: loaded.append((model_dir, voice)) or FakeLoaded(),
    )

    with capture("tts") as logs:
        synthesis = deps.new_speech_synthesis(
            TtsConfig.from_env({"TTS_PIPER_MODEL_DIR": str(tmp_path), "TTS_PIPER_VOICE": "v"})
        )

    assert isinstance(synthesis, PiperSpeechSynthesis)
    assert loaded == [(tmp_path, "v")]
    assert synthesis.fallback_reason() is None  # the configured engine speaks: nothing to report
    assert _fallback_records(logs) == []  # and nothing is logged as a fallback


def test_a_missing_voice_falls_back_to_pyttsx3(tmp_path):
    with capture("tts") as logs:
        synthesis = deps.new_speech_synthesis(TtsConfig.from_env({"TTS_PIPER_MODEL_DIR": str(tmp_path)}))

    assert isinstance(synthesis, Pyttsx3SpeechSynthesis)
    reason = synthesis.fallback_reason()
    assert reason is not None and reason.startswith("fallback: pyttsx3 instead of piper (")
    assert ALAN in reason and "is not in" in reason
    record = _the_one_fallback_record(logs, PIPER_FALLBACK)
    assert ALAN in record["reason"] and "is not in" in record["reason"]
    assert str(tmp_path) in record["reason"]  # the log keeps the full text; only /available hides the path


def test_a_corrupt_voice_falls_back_to_pyttsx3(tmp_path):
    (tmp_path / f"{ALAN}.onnx").write_bytes(b"not a model")
    (tmp_path / f"{ALAN}.onnx.json").write_text("{}")

    with capture("tts") as logs:
        synthesis = deps.new_speech_synthesis(TtsConfig.from_env({"TTS_PIPER_MODEL_DIR": str(tmp_path)}))

    assert isinstance(synthesis, Pyttsx3SpeechSynthesis)
    reason = synthesis.fallback_reason()
    assert reason is not None and reason.startswith("fallback: pyttsx3 instead of piper (Piper could not load")
    record = _the_one_fallback_record(logs, PIPER_FALLBACK)
    assert record["reason"].startswith("Piper could not load")


def test_pyttsx3_can_be_chosen_explicitly(tmp_path):
    with capture("tts") as logs:
        synthesis = deps.new_speech_synthesis(
            TtsConfig.from_env({"TTS_ENGINE": "pyttsx3", "TTS_PIPER_MODEL_DIR": str(tmp_path)})
        )

    assert isinstance(synthesis, Pyttsx3SpeechSynthesis)
    assert synthesis.fallback_reason() is None  # it is the configured engine, not a fallback
    assert _fallback_records(logs) == []


def test_the_fallback_note_never_shows_a_folder_path(tmp_path):
    folder = tmp_path / "private_user_dir" / "models"
    folder.mkdir(parents=True)

    synthesis = deps.new_speech_synthesis(TtsConfig.from_env({"TTS_PIPER_MODEL_DIR": str(folder)}))

    reason = synthesis.fallback_reason()
    assert reason is not None
    assert "private_user_dir" not in reason and str(folder) not in reason and str(tmp_path) not in reason
    assert "models" in reason  # the folder is still named, by its last part
    assert "\n" not in reason


def test_the_fallback_note_replaces_the_home_directory_and_is_cut_short(tmp_path):
    home = deps.Path.home()
    error = RuntimeError(f"cannot read {home}/secret/file " + "x" * 500)

    reason = deps._fallback_reason("piper", error)

    assert str(home) not in reason and home.as_posix() not in reason
    assert "~/secret/file" in reason or "~\\secret/file" in reason
    assert reason.startswith("fallback: pyttsx3 instead of piper (") and reason.endswith(")")
    assert len(reason) <= len("fallback: pyttsx3 instead of piper ()") + deps._MAX_CAUSE


@pytest.mark.skipif(
    not (TtsConfig.from_env({}).piper_model_dir / f"{ALAN}.onnx").is_file(),
    reason=f"the Alan voice is not downloaded (python -m piper.download_voices {ALAN} --download-dir models)",
)
def test_the_real_alan_voice_speaks():
    with capture("tts") as logs:
        synthesis = deps.new_speech_synthesis(TtsConfig.from_env({}))
    assert isinstance(synthesis, PiperSpeechSynthesis)
    assert synthesis.fallback_reason() is None
    # what the deployment documents and the Docker checks look for: the voice loaded, and no fallback line
    loaded = logs.find("Piper voice loaded")
    assert len(loaded) == 1 and loaded[0]["voice"] == ALAN
    assert _fallback_records(logs) == []

    audio = asyncio.run(
        synthesis.synthesize("Good evening, sir. How may I be of service?", AudioFormat(24000, 1))
    )

    assert 24000 * 2 * 1.5 < len(audio) < 24000 * 2 * 8  # between 1.5 and 8 seconds of speech
    assert any(audio)


def test_espeak_is_chosen_when_it_loads(monkeypatch):
    class FakeLoaded:
        sample_rate = 22050

        def synthesize(self, text, speed):
            raise AssertionError("not spoken in this test")

    asked = []
    monkeypatch.setattr(
        deps.EspeakEngine, "load", lambda command, **options: asked.append((command, options)) or FakeLoaded()
    )

    with capture("tts") as logs:
        synthesis = deps.new_speech_synthesis(
            TtsConfig.from_env({"TTS_ENGINE": "espeak", "TTS_ESPEAK_VOICE": "en+m3", "TTS_ESPEAK_PITCH": "5"})
        )

    assert isinstance(synthesis, EspeakSpeechSynthesis)
    assert _fallback_records(logs) == []
    assert asked[0][0] == ""
    assert asked[0][1]["voice"] == "en+m3" and asked[0][1]["pitch"] == 5
    assert synthesis.fallback_reason() is None


def test_a_missing_espeak_falls_back_to_pyttsx3(monkeypatch):
    from infrastructure.outbound.espeak_speech import espeak_engine

    monkeypatch.setattr(espeak_engine.shutil, "which", lambda name: None)

    with capture("tts") as logs:
        synthesis = deps.new_speech_synthesis(TtsConfig.from_env({"TTS_ENGINE": "espeak"}))

    assert isinstance(synthesis, Pyttsx3SpeechSynthesis)
    reason = synthesis.fallback_reason()
    assert reason is not None and reason.startswith("fallback: pyttsx3 instead of espeak (")
    assert "is not installed" in reason
    record = _the_one_fallback_record(logs, ESPEAK_FALLBACK)
    assert "is not installed" in record["reason"]
