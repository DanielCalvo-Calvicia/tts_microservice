from dataclasses import dataclass

from fastapi import FastAPI

from application.ports.inbound.tts_synthesis_port import TtsSynthesisPort
from composition_root.dependencies import tts_dependencies as deps
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.tts_config import TtsConfig


@dataclass(slots=True, frozen=True)
class HttpContainer:
    app: FastAPI
    tts: TtsSynthesisPort


def new_http_container(server_cfg: ServerConfig, tts_cfg: TtsConfig) -> HttpContainer:
    synthesis = deps.new_speech_synthesis(tts_cfg)
    service = deps.new_tts_service(synthesis, server_cfg.service_name)
    app = deps.new_http_app(service, server_cfg.service_name)
    return HttpContainer(app=app, tts=service)
