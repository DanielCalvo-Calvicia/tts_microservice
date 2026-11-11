from dataclasses import dataclass

from fastapi import FastAPI

from application.ports.service.tts_service_port import TtsServicePort
from composition_root.dependencies.http_app_dependency import new_http_app
from composition_root.dependencies.speech_synthesis_dependency import new_speech_synthesis
from composition_root.dependencies.tts_service_dependency import new_tts_service
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.tts_config import TtsConfig


@dataclass(slots=True, frozen=True)
class HttpContainer:
    app: FastAPI
    tts: TtsServicePort


def new_http_container(server_cfg: ServerConfig, tts_cfg: TtsConfig) -> HttpContainer:
    synthesis = new_speech_synthesis(tts_cfg)
    service = new_tts_service(synthesis, server_cfg.service_name)
    app = new_http_app(service, server_cfg.service_name)
    return HttpContainer(app=app, tts=service)
