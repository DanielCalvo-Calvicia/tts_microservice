import os
from dataclasses import dataclass

from application.ports.adapter_outbound_port import AdapterOutboundPort
from application.ports.service_port import ServicePort
from application.ports.adapter_inbound_port import AdapterInboundPort

from application.dtos.adapter_outbound_dtos import InitOutboundAdapterDto
from application.dtos.adapter_inbound_dtos import InitInboundAdapterDto

from infrastructure.outbound.tts.pyttsx3_adapter import PyTTSx3Adapter
from application.services.service import TTSService
from infrastructure.inbound.http.fastapi_adapter import FastApiAdapter

from fastapi import FastAPI
from contextlib import asynccontextmanager
from infrastructure.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class TTSDependency:
    adapter_outbound: AdapterOutboundPort
    service: ServicePort
    adapter_inbound: AdapterInboundPort


def generate_tts_dependency() -> TTSDependency:
    logger.info("Generating TTS dependency graph")

    # Build outbound adapter config
    speech_rate = int(os.getenv("TTS_SPEECH_RATE", "140"))
    voice_name = os.getenv("TTS_VOICE_NAME", "Zira")
    logger.info(
        "Resolved outbound TTS config speech_rate=%s voice_name_preference=%s",
        speech_rate,
        voice_name,
    )
    
    outbound_config = InitOutboundAdapterDto(
        speech_rate=speech_rate,
        voice_name_preference=voice_name
    )
    logger.info("Creating PyTTSx3Adapter")
    adapter_outbound = PyTTSx3Adapter(outbound_config)

    # Wire the core domain service
    logger.info("Creating TTSService")
    service = TTSService(name="tts_service", outbound_port=adapter_outbound)

    adapter_inbound = None

    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        logger.info("FastAPI lifespan startup started")
        if adapter_inbound:
            logger.info("Starting inbound adapter autoload")
            adapter_inbound.start_autoload()
        yield
        logger.info("FastAPI lifespan shutdown started")
        if adapter_inbound:
            logger.info("Stopping inbound adapter autoload")
            await adapter_inbound.stop_autoload()
        logger.info("FastAPI lifespan shutdown finished")

    logger.info("Creating FastAPI application")
    app = FastAPI(
        title="TTS Microservice",
        description="Text-to-Speech synthesis service",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=app_lifespan,
    )
    
    inbound_config = InitInboundAdapterDto()
    logger.info("Creating FastApiAdapter and registering routes")
    adapter_inbound = FastApiAdapter(service_port=service, app=app, config=inbound_config)

    dependency = TTSDependency(
        adapter_outbound=adapter_outbound,
        service=service,
        adapter_inbound=adapter_inbound,
    )
    logger.info("TTS dependency graph generated")
    return dependency
