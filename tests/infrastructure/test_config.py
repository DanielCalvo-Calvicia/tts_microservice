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


def test_tts_config_defaults():
    assert TtsConfig.from_env({}) == TtsConfig(140, "Zira")


def test_tts_config_overrides():
    cfg = TtsConfig.from_env({"TTS_SPEECH_RATE": "180", "TTS_VOICE_NAME": "David"})
    assert cfg == TtsConfig(180, "David")
