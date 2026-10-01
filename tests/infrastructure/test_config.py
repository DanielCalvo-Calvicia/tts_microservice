import pytest

from infrastructure.config.server_config import ServerConfig
from infrastructure.config.tts_config import TtsConfig


def test_server_config_defaults():
    cfg = ServerConfig.from_env({})
    assert (cfg.service_name, cfg.host, cfg.port) == (
        "TTS Microservice",
        "127.0.0.1",
        8002,
    )


def test_server_config_overrides():
    cfg = ServerConfig.from_env(
        {
            "SERVICE_NAME": "X",
            "SERVICE_HOST": "0.0.0.0",
            "SERVICE_PORT": "9000",
        }
    )
    assert (cfg.service_name, cfg.host, cfg.port) == ("X", "0.0.0.0", 9000)


def test_tts_config_defaults_use_the_piper_droid_voice():
    cfg = TtsConfig.from_env({})
    assert (cfg.engine, cfg.piper_voice) == ("piper", "en_GB-alan-medium")
    assert (cfg.speech_rate, cfg.voice_name_preference) == (140, "Zira")
    assert (cfg.piper_speed, cfg.pitch_semitones, cfg.droid_effect) == (1.0, 2.0, 0.5)
    assert cfg.piper_model_dir.is_absolute() and cfg.piper_model_dir.name == "models"


def test_tts_config_overrides():
    cfg = TtsConfig.from_env({"TTS_SPEECH_RATE": "180", "TTS_VOICE_NAME": "David"})
    assert (cfg.speech_rate, cfg.voice_name_preference, cfg.engine) == (180, "David", "piper")


def test_tts_config_reads_the_piper_settings(tmp_path):
    cfg = TtsConfig.from_env(
        {
            "TTS_ENGINE": " PYTTSX3 ",
            "TTS_PIPER_VOICE": "en_GB-northern_english_male-medium",
            "TTS_PIPER_MODEL_DIR": str(tmp_path),
            "TTS_PIPER_SPEED": "1.2",
            "TTS_PITCH_SEMITONES": "-1.5",
            "TTS_DROID_EFFECT": "0",
        }
    )
    assert cfg.engine == "pyttsx3"
    assert cfg.piper_voice == "en_GB-northern_english_male-medium"
    assert cfg.piper_model_dir == tmp_path
    assert (cfg.piper_speed, cfg.pitch_semitones, cfg.droid_effect) == (1.2, -1.5, 0.0)


@pytest.mark.parametrize(
    "bad",
    [
        {"TTS_ENGINE": "openai"},
        {"TTS_PIPER_SPEED": "0"},
        {"TTS_DROID_EFFECT": "-1"},
        {"TTS_PITCH_SEMITONES": "high"},
    ],
)
def test_tts_config_rejects_values_that_would_break_synthesis(bad):
    with pytest.raises(ValueError):
        TtsConfig.from_env(bad)
