from contracts.api.microservices.common.availability import AvailabilityResponse
from fastapi.responses import JSONResponse

from application.ports.inbound.tts_inbound_port import TtsInboundPort
from infrastructure.inbound.http.response.http_envelope import failure, success


async def handle_available(inbound: TtsInboundPort) -> JSONResponse:
    """GET /available: whether the speech engine works, and a ``reason`` while a fallback voice speaks (ADR-008)."""
    try:
        available = await inbound.is_available()
    except Exception as error:
        return failure("check_availability", "Failed to check availability", error)
    return success(
        "check_availability",
        "Availability checked successfully",
        AvailabilityResponse(is_available=available, reason=inbound.fallback_reason()),
    )
