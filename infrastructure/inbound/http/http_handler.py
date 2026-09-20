"""HTTP inbound adapter: decode -> call the inbound port -> encode. No business rules."""

import base64
import time
from collections.abc import AsyncIterator

from contracts.api.microservices.common.availability import AvailabilityResponse
from contracts.api.microservices.common.health_check import HealthCheckResponse
from contracts.api.microservices.tts.process_batch import ProcessBatchResponse
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from shared_logging import get_logger

from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.errors import AudioFormatMismatch
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.ports.inbound.tts_synthesis_port import TtsSynthesisPort
from infrastructure.inbound.http.audio_events import NDJSON_MEDIA_TYPE, audio_events_as_ndjson
from infrastructure.inbound.http.http_envelope import failure, success
from infrastructure.inbound.http.input_stream_response import InputStreamResponse, TrackedTexts
from infrastructure.inbound.http.ndjson_text_input import texts_from_ndjson

logger = get_logger(__name__)

_DEFAULTS = ProcessBatchInboundDTO(text="")
_AUDIO_MEDIA_TYPE = "audio/wav"
_GET_HEARTBEAT_SECONDS = 15.0


def _stream_headers(action: str, message: str) -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Action": action,
        "X-Status": "success",
        "X-Message": message,
        "X-Timestamp": str(time.time()),
    }


def _is_ndjson_request(request: Request) -> bool:
    return NDJSON_MEDIA_TYPE in request.headers.get("content-type", "").lower()


async def _request_body_chunks(request: Request) -> AsyncIterator[bytes]:
    async for chunk in request.stream():
        yield chunk


async def _read_text_lines(request: Request) -> list[str]:
    """The non-empty lines of the request body, one text to speak each.

    The body is read up front: ``set_stream`` keeps speaking after the response has been sent,
    when the request can no longer be read.
    """
    body = (await request.body()).decode("utf-8")
    lines = [line.strip() for line in body.split("\n") if line.strip()]
    logger.info("Parsed request body", non_empty_lines=len(lines))
    return lines


async def _as_stream(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        logger.info("Yielding text line", length=len(line))
        yield line


async def _counted(audio_stream: AsyncIterator[bytes], label: str) -> AsyncIterator[bytes]:
    chunk_count = 0
    total_bytes = 0
    async for chunk in audio_stream:
        chunk_count += 1
        total_bytes += len(chunk)
        yield chunk
    logger.info(
        "Audio stream completed",
        label=label,
        chunk_count=chunk_count,
        total_bytes=total_bytes,
    )


class TtsHandler:
    def __init__(self, port: TtsSynthesisPort) -> None:
        self._port = port
        self.router = APIRouter()
        add = self.router.add_api_route
        add("/health", self.handle_health, methods=["GET"], tags=["Health"])
        add("/available", self.handle_available, methods=["GET"])
        add("/process/stream", self.handle_process_stream, methods=["POST"], response_model=None)
        add(
            "/process/stream/set",
            self.handle_set_stream,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
            response_model=None,
        )
        add("/process/stream/get", self.handle_get_stream, methods=["GET"], response_model=None)
        add("/process/batch", self.handle_process_batch, methods=["POST"])

    async def handle_health(self) -> JSONResponse:
        return success("health_check", "Service is healthy", HealthCheckResponse(healthy=True))

    async def handle_available(self) -> JSONResponse:
        try:
            available = await self._port.is_available()
        except Exception as error:
            return failure("check_availability", "Failed to check availability", error)
        return success(
            "check_availability",
            "Availability checked successfully",
            AvailabilityResponse(is_available=available),
        )

    async def handle_process_stream(
        self,
        request: Request,
        sample_rate: int = _DEFAULTS.sample_rate,
        channels: int = _DEFAULTS.channels,
    ) -> Response:
        try:
            lines = await _read_text_lines(request)
            result = await self._port.process_stream(
                ProcessStreamInboundDTO(
                    text_stream=_as_stream(lines), sample_rate=sample_rate, channels=channels
                )
            )
        except Exception as error:
            return failure("process_stream", "Failed to process stream", error)
        return StreamingResponse(
            _counted(result.audio_stream, "/process/stream"),
            media_type=_AUDIO_MEDIA_TYPE,
            status_code=status.HTTP_200_OK,
            headers=_stream_headers("process_stream", "Stream processed successfully"),
        )

    async def handle_set_stream(
        self,
        request: Request,
        sample_rate: int = _DEFAULTS.sample_rate,
        channels: int = _DEFAULTS.channels,
    ) -> Response:
        """Accept the text to speak.

        ``Content-Type: application/x-ndjson`` is the Brain protocol: a live stream of TTS inbound
        contract events, consumed as it arrives while the response stays open. Any other body is a
        plain text (one utterance per line), read up front, for simple clients.
        """
        if _is_ndjson_request(request):
            return await self._set_event_stream(request, sample_rate, channels)
        try:
            lines = await _read_text_lines(request)
            await self._port.set_stream(
                ProcessStreamInboundDTO(
                    text_stream=_as_stream(lines), sample_rate=sample_rate, channels=channels
                )
            )
        except Exception as error:
            return failure("set_stream", "Failed to set stream", error)
        return success(
            "set_stream",
            "Stream accepted. Background synthesis started.",
            code=status.HTTP_202_ACCEPTED,
            state="accepted",
        )

    async def _set_event_stream(self, request: Request, sample_rate: int, channels: int) -> Response:
        tracked = TrackedTexts(texts_from_ndjson(_request_body_chunks(request)))
        try:
            await self._port.set_stream(
                ProcessStreamInboundDTO(
                    text_stream=tracked, sample_rate=sample_rate, channels=channels
                )
            )
        except Exception as error:
            return failure("set_stream", "Failed to set stream", error)
        return InputStreamResponse(
            tracked, headers=_stream_headers("set_stream", "Input stream connection established")
        )

    async def handle_get_stream(
        self,
        sample_rate: int | None = None,
        channels: int | None = None,
        keep_open_after_completed: bool = True,  # accepted for compatibility: the stream always stays open
    ) -> Response:
        """The synthesized audio as TTS outbound contract events (``application/x-ndjson``).

        The audio format was fixed by ``set``; ``sample_rate``/``channels`` repeated here must match.
        """
        try:
            active = self._port.current_format()
            if active is not None:
                for name, given, actual in (
                    ("sample_rate", sample_rate, active[0]),
                    ("channels", channels, active[1]),
                ):
                    if given is not None and given != actual:
                        raise AudioFormatMismatch(f"{name}={given} differs from the stream's {name}={actual}")
            result = await self._port.get_segment_stream()
        except Exception as error:
            return failure("get_stream", "Failed to get stream", error)
        return StreamingResponse(
            audio_events_as_ndjson(
                result.events, heartbeat_interval_seconds=_GET_HEARTBEAT_SECONDS
            ),
            media_type=NDJSON_MEDIA_TYPE,
            status_code=status.HTTP_200_OK,
            headers=_stream_headers("get_stream", "Decoupled stream retrieved successfully"),
        )

    async def handle_process_batch(
        self,
        text: str = "",
        sample_rate: int = _DEFAULTS.sample_rate,
        channels: int = _DEFAULTS.channels,
    ) -> JSONResponse:
        try:
            result = await self._port.process_batch(
                ProcessBatchInboundDTO(text=text, sample_rate=sample_rate, channels=channels)
            )
        except Exception as error:
            return failure("process_batch", "Failed to process batch", error)
        return success(
            "process_batch",
            "Text synthesized successfully",
            ProcessBatchResponse(
                audio_data_base64=base64.b64encode(result.audio_data).decode("utf-8"),
                sample_rate=sample_rate,
                channels=channels,
            ),
        )
