from fastapi import FastAPI
from shared_logging import TracingMiddleware, get_logger

from application.errors import SynthesisFailed
from application.ports.inbound.tts_synthesis_port import TtsSynthesisPort
from application.ports.outbound.speech_synthesis_port import SpeechSynthesisPort
from application.services.tts_service import TtsService
from infrastructure.config.tts_config import TtsConfig
from infrastructure.inbound.http.http_handler import TtsHandler
from infrastructure.outbound.piper_speech.piper_engine import PiperEngine
from infrastructure.outbound.piper_speech.piper_speech_synthesis import PiperSpeechSynthesis
from infrastructure.outbound.pyttsx3_speech.pyttsx3_speech_synthesis import (
    Pyttsx3SpeechSynthesis,
)
from infrastructure.outbound.pyttsx3_speech.pyttsx3_subprocess import Pyttsx3Subprocess

logger = get_logger(__name__)


def new_speech_synthesis(cfg: TtsConfig) -> SpeechSynthesisPort:
    """The configured engine. A Piper voice that cannot be loaded falls back to pyttsx3, loudly.

    Brain's startup preflight waits for this service and exits when it is not ready, so a machine whose voice
    download failed must still speak (with the old voice) instead of taking the whole robot down.
    """
    if cfg.engine == "piper":
        try:
            return PiperSpeechSynthesis(
                PiperEngine.load(cfg.piper_model_dir, cfg.piper_voice),
                speed=cfg.piper_speed,
                pitch_semitones=cfg.pitch_semitones,
                effect_strength=cfg.droid_effect,
            )
        except SynthesisFailed as error:
            logger.error("Piper unavailable; falling back to pyttsx3", reason=str(error))
    return _new_pyttsx3(cfg)


def _new_pyttsx3(cfg: TtsConfig) -> SpeechSynthesisPort:
    return Pyttsx3SpeechSynthesis(
        Pyttsx3Subprocess(
            speech_rate=cfg.speech_rate, voice_name_preference=cfg.voice_name_preference
        )
    )


def new_tts_service(synthesis: SpeechSynthesisPort, name: str) -> TtsSynthesisPort:
    return TtsService(synthesis=synthesis, name=name)


def new_http_app(port: TtsSynthesisPort, name: str) -> FastAPI:
    app = FastAPI(
        title=name,
        description=f"HTTP adapter exposing {name}",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.include_router(TtsHandler(port).router)
    app.add_middleware(TracingMiddleware)
    return app
