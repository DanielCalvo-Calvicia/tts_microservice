from fastapi import FastAPI
from shared_logging import TracingMiddleware

from application.ports.inbound.tts_synthesis_port import TtsSynthesisPort
from application.ports.outbound.speech_synthesis_port import SpeechSynthesisPort
from application.services.tts_service import TtsService
from infrastructure.config.tts_config import TtsConfig
from infrastructure.inbound.http.http_handler import TtsHandler
from infrastructure.outbound.pyttsx3_speech.pyttsx3_speech_synthesis import (
    Pyttsx3SpeechSynthesis,
)
from infrastructure.outbound.pyttsx3_speech.pyttsx3_subprocess import Pyttsx3Subprocess


def new_speech_synthesis(cfg: TtsConfig) -> SpeechSynthesisPort:
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
