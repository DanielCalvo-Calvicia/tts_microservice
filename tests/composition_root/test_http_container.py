from fastapi.testclient import TestClient

from composition_root.containers import http_container
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.tts_config import TtsConfig


def test_container_wires_an_app_that_answers_health():
    container = http_container.new_http_container(ServerConfig.from_env({}), TtsConfig.from_env({}))

    body = TestClient(container.app).get("/health").json()

    assert body["status"] == "success" and body["action"] == "health_check"


def test_container_uses_the_configured_voice_and_rate():
    container = http_container.new_http_container(
        ServerConfig.from_env({}),
        TtsConfig.from_env({"TTS_SPEECH_RATE": "180", "TTS_VOICE_NAME": "David"}),
    )

    synthesizer = container.tts._synthesis._synthesizer  # type: ignore[attr-defined]

    assert synthesizer._speech_rate == 180
    assert synthesizer._voice_name_preference == "David"
