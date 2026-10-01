"""Which engine the service starts with, and that a missing Piper voice never takes the service down."""

import asyncio

import pytest

from composition_root.dependencies import tts_dependencies as deps
from domain.value_objects.audio_format import AudioFormat
from infrastructure.config.tts_config import TtsConfig
from infrastructure.outbound.piper_speech.piper_speech_synthesis import PiperSpeechSynthesis
from infrastructure.outbound.pyttsx3_speech.pyttsx3_speech_synthesis import Pyttsx3SpeechSynthesis

ALAN = "en_GB-alan-medium"


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

    synthesis = deps.new_speech_synthesis(
        TtsConfig.from_env({"TTS_PIPER_MODEL_DIR": str(tmp_path), "TTS_PIPER_VOICE": "v"})
    )

    assert isinstance(synthesis, PiperSpeechSynthesis)
    assert loaded == [(tmp_path, "v")]


def test_a_missing_voice_falls_back_to_pyttsx3(tmp_path):
    synthesis = deps.new_speech_synthesis(TtsConfig.from_env({"TTS_PIPER_MODEL_DIR": str(tmp_path)}))

    assert isinstance(synthesis, Pyttsx3SpeechSynthesis)


def test_a_corrupt_voice_falls_back_to_pyttsx3(tmp_path):
    (tmp_path / f"{ALAN}.onnx").write_bytes(b"not a model")
    (tmp_path / f"{ALAN}.onnx.json").write_text("{}")

    synthesis = deps.new_speech_synthesis(TtsConfig.from_env({"TTS_PIPER_MODEL_DIR": str(tmp_path)}))

    assert isinstance(synthesis, Pyttsx3SpeechSynthesis)


def test_pyttsx3_can_be_chosen_explicitly(tmp_path):
    synthesis = deps.new_speech_synthesis(
        TtsConfig.from_env({"TTS_ENGINE": "pyttsx3", "TTS_PIPER_MODEL_DIR": str(tmp_path)})
    )

    assert isinstance(synthesis, Pyttsx3SpeechSynthesis)


@pytest.mark.skipif(
    not (TtsConfig.from_env({}).piper_model_dir / f"{ALAN}.onnx").is_file(),
    reason=f"the Alan voice is not downloaded (python -m piper.download_voices {ALAN} --download-dir models)",
)
def test_the_real_alan_voice_speaks():
    synthesis = deps.new_speech_synthesis(TtsConfig.from_env({}))
    assert isinstance(synthesis, PiperSpeechSynthesis)

    audio = asyncio.run(
        synthesis.synthesize("Good evening, sir. How may I be of service?", AudioFormat(24000, 1))
    )

    assert 24000 * 2 * 1.5 < len(audio) < 24000 * 2 * 8  # between 1.5 and 8 seconds of speech
    assert any(audio)
