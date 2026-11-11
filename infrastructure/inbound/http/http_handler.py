"""HTTP inbound adapter: declares the endpoints and wires each one to its route. No request logic of its own."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, Response

from application.dtos.inbound.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.outbound.audio_batch_outbound import AudioBatchOutboundDTO
from application.dtos.outbound.audio_segment_outbound import AudioSegmentStreamOutboundDTO
from application.dtos.outbound.audio_stream_outbound import AudioStreamOutboundDTO
from application.ports.inbound.tts_inbound_port import TtsInboundPort
from application.ports.service.tts_service_port import TtsServicePort
from infrastructure.inbound.http.routes.available import handle_available
from infrastructure.inbound.http.routes.get_stream import handle_get_stream
from infrastructure.inbound.http.routes.health import handle_health
from infrastructure.inbound.http.routes.process_batch import handle_process_batch
from infrastructure.inbound.http.routes.process_stream import handle_process_stream
from infrastructure.inbound.http.routes.set_stream import handle_set_stream

_DEFAULTS = ProcessBatchInboundDTO(text="")  # the default audio format of every endpoint


class TtsHandler(TtsInboundPort):
    """The HTTP inbound adapter. It declares which endpoints exist and wires each to its function in ``routes/``;
    the request decoding, the answers and the error mapping live in ``helpers/``, ``response/`` and ``errors/``.
    Its operations are those of ``TtsInboundPort`` (DTOs, no HTTP types) and the routes call them."""

    def __init__(self, service: TtsServicePort) -> None:
        self._service = service
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self) -> None:
        inbound: TtsInboundPort = self
        add = self.router.add_api_route

        async def health() -> JSONResponse:
            return await handle_health(inbound)

        async def available() -> JSONResponse:
            return await handle_available(inbound)

        async def process_stream(
            request: Request,
            sample_rate: int = _DEFAULTS.sample_rate,
            channels: int = _DEFAULTS.channels,
        ) -> Response:
            return await handle_process_stream(request, sample_rate, channels, inbound)

        async def set_stream(
            request: Request,
            sample_rate: int = _DEFAULTS.sample_rate,
            channels: int = _DEFAULTS.channels,
        ) -> Response:
            return await handle_set_stream(request, sample_rate, channels, inbound)

        async def get_stream(
            sample_rate: int | None = None,
            channels: int | None = None,
            keep_open_after_completed: bool = True,  # accepted for compatibility: the stream always stays open
        ) -> Response:
            return await handle_get_stream(sample_rate, channels, inbound)

        async def process_batch(
            text: str = "",
            sample_rate: int = _DEFAULTS.sample_rate,
            channels: int = _DEFAULTS.channels,
        ) -> JSONResponse:
            return await handle_process_batch(text, sample_rate, channels, inbound)

        add("/health", health, methods=["GET"], tags=["Health"])
        add("/available", available, methods=["GET"])
        add("/process/stream", process_stream, methods=["POST"], response_model=None)
        add(
            "/process/stream/set",
            set_stream,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
            response_model=None,
        )
        add("/process/stream/get", get_stream, methods=["GET"], response_model=None)
        add("/process/batch", process_batch, methods=["POST"])

    # --- TtsInboundPort: the operations every inbound adapter offers --------------------------------

    def health(self) -> bool:
        return True

    async def is_available(self) -> bool:
        return await self._service.is_available()

    def fallback_reason(self) -> str | None:
        return self._service.fallback_reason()

    def current_format(self) -> tuple[int, int] | None:
        return self._service.current_format()

    async def process_stream(self, request: ProcessStreamInboundDTO) -> AudioStreamOutboundDTO:
        return await self._service.process_stream(request)

    async def set_stream(self, request: ProcessStreamInboundDTO) -> None:
        await self._service.set_stream(request)

    async def get_segment_stream(self) -> AudioSegmentStreamOutboundDTO:
        return await self._service.get_segment_stream()

    async def process_batch(self, request: ProcessBatchInboundDTO) -> AudioBatchOutboundDTO:
        return await self._service.process_batch(request)
