from pathlib import Path

from fastapi import FastAPI
from shared_logging import TracingMiddleware, get_logger

from application.errors import SynthesisFailed
from application.ports.inbound.tts_synthesis_port import TtsSynthesisPort
from application.ports.outbound.speech_synthesis_port import SpeechSynthesisPort
from application.services.tts_service import TtsService
from infrastructure.config.tts_config import TtsConfig
from infrastructure.inbound.http.http_handler import TtsHandler
from infrastructure.outbound.espeak_speech.espeak_engine import EspeakEngine
from infrastructure.outbound.espeak_speech.espeak_speech_synthesis import EspeakSpeechSynthesis
from infrastructure.outbound.piper_speech.piper_engine import PiperEngine
from infrastructure.outbound.piper_speech.piper_speech_synthesis import PiperSpeechSynthesis
from infrastructure.outbound.pyttsx3_speech.pyttsx3_speech_synthesis import (
    Pyttsx3SpeechSynthesis,
)
from infrastructure.outbound.pyttsx3_speech.pyttsx3_subprocess import Pyttsx3Subprocess

logger = get_logger(__name__)

_MAX_CAUSE = 200


def new_speech_synthesis(cfg: TtsConfig) -> SpeechSynthesisPort:
    """The configured engine. A Piper voice or an espeak that cannot be loaded falls back to pyttsx3, loudly.

    Brain's startup preflight waits for this service and exits when it is not ready, so a machine whose voice
    download failed must still speak (with the old voice) instead of taking the whole robot down.
    """
    fallback_reason: str | None = None
    if cfg.engine == "espeak":
        try:
            return EspeakSpeechSynthesis(
                EspeakEngine.load(
                    cfg.espeak_command,
                    voice=cfg.espeak_voice,
                    words_per_minute=cfg.espeak_speed,
                    pitch=cfg.espeak_pitch,
                    word_gap_ms=cfg.espeak_word_gap_ms,
                ),
                speed=1.0,
                effect_strength=cfg.robot_effect,
            )
        except SynthesisFailed as error:
            logger.error("espeak unavailable; falling back to pyttsx3", reason=str(error))
            fallback_reason = _fallback_reason("espeak", error)
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
            fallback_reason = _fallback_reason("piper", error, cfg.piper_model_dir)
    return _new_pyttsx3(cfg, fallback_reason)


def _fallback_reason(engine: str, error: Exception, *folders: Path) -> str:
    """The note ``GET /available`` carries while pyttsx3 speaks instead of ``engine`` (ADR-008).

    Built from the failure, but safe to show to any caller: one line, no folder path (a folder is named
    by its last part, the home directory is ``~``), at most ``_MAX_CAUSE`` characters. The log keeps the
    full text.
    """
    cause = " ".join(str(error).split())
    for folder in folders:
        name = folder.name or "."
        cause = cause.replace(str(folder), name).replace(folder.as_posix(), name)
    home = Path.home()
    cause = cause.replace(str(home), "~").replace(home.as_posix(), "~")
    return f"fallback: pyttsx3 instead of {engine} ({cause[:_MAX_CAUSE]})"


def _new_pyttsx3(cfg: TtsConfig, fallback_reason: str | None = None) -> SpeechSynthesisPort:
    return Pyttsx3SpeechSynthesis(
        Pyttsx3Subprocess(
            speech_rate=cfg.speech_rate, voice_name_preference=cfg.voice_name_preference
        ),
        fallback_reason=fallback_reason,
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
