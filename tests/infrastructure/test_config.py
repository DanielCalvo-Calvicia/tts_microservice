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


def test_tts_config_reads_the_espeak_robot_settings():
    cfg = TtsConfig.from_env(
        {
            "TTS_ENGINE": "espeak",
            "TTS_ESPEAK_COMMAND": "espeak-ng",
            "TTS_ESPEAK_VOICE": "en+klatt3",
            "TTS_ESPEAK_SPEED": "120",
            "TTS_ESPEAK_PITCH": "10",
            "TTS_ESPEAK_WORD_GAP_MS": "50",
            "TTS_ROBOT_EFFECT": "2",
        }
    )
    assert cfg.engine == "espeak"
    assert (cfg.espeak_command, cfg.espeak_voice) == ("espeak-ng", "en+klatt3")
    assert (cfg.espeak_speed, cfg.espeak_pitch, cfg.espeak_word_gap_ms) == (120, 10, 50)
    assert cfg.robot_effect == 2.0


def test_tts_config_espeak_defaults():
    cfg = TtsConfig.from_env({})
    assert (cfg.espeak_command, cfg.espeak_voice) == ("", "en")
    assert (cfg.espeak_speed, cfg.espeak_pitch, cfg.robot_effect) == (150, 30, 1.0)


@pytest.mark.parametrize(
    "env",
    [
        {"TTS_ESPEAK_SPEED": "10"},
        {"TTS_ESPEAK_SPEED": "900"},
        {"TTS_ESPEAK_PITCH": "100"},
        {"TTS_ESPEAK_PITCH": "-1"},
        {"TTS_ESPEAK_WORD_GAP_MS": "-5"},
        {"TTS_ROBOT_EFFECT": "-0.1"},
    ],
)
def test_tts_config_rejects_out_of_range_espeak_settings(env):
    with pytest.raises(ValueError):
        TtsConfig.from_env(env)
