from contracts.api.microservices.common.health_check import HealthCheckResponse
from fastapi.responses import JSONResponse

from application.ports.inbound.tts_inbound_port import TtsInboundPort
from infrastructure.inbound.http.response.http_envelope import success


async def handle_health(inbound: TtsInboundPort) -> JSONResponse:
    """GET /health: liveness. 200 while the process answers HTTP."""
    return success("health_check", "Service is healthy", HealthCheckResponse(healthy=inbound.health()))
