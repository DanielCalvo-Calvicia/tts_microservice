from fastapi import FastAPI
from shared_logging import TracingMiddleware

from application.ports.service.tts_service_port import TtsServicePort
from infrastructure.inbound.http.http_handler import TtsHandler


def new_http_app(service: TtsServicePort, name: str) -> FastAPI:
    app = FastAPI(
        title=name,
        description=f"HTTP adapter exposing {name}",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.include_router(TtsHandler(service).router)
    app.add_middleware(TracingMiddleware)
    return app
