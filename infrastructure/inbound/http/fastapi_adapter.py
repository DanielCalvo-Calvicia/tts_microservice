import time
from typing import AsyncIterator, Any

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.requests import ClientDisconnect

from application.ports.adapter_inbound_port import AdapterInboundPort
from application.ports.service_port import ServicePort

from application.dtos.adapter_inbound_dtos import (
    ProcessStreamRequestDto,
    ProcessStreamResponseDto,
    ProcessBatchRequestDto,
    ProcessBatchResponseDto,
    TTSAvailabilityRequestDto,
    TTSAvailabilityResponseDto,
    InitInboundAdapterDto,
    SetStreamRequestDto,
    GetStreamRequestDto,
    GetStreamResponseDto,
)

from application.dtos.mapper.adapter_inbound_to_service import (
    map_inbound_to_service_stream_request,
    map_inbound_to_service_batch_request,
    map_inbound_to_service_availability_request,
    map_inbound_to_service_set_stream_request,
    map_inbound_to_service_get_stream_request,
)

from application.dtos.mapper.service_to_adapter_inbound import (
    map_service_to_inbound_stream_response,
    map_service_to_inbound_batch_response,
    map_service_to_inbound_availability_response,
    map_service_to_inbound_get_stream_response,
)
from infrastructure.logger import get_logger


logger = get_logger(__name__)


def _client_disconnect_response(action: str) -> JSONResponse:
    return JSONResponse(
        status_code=499,
        content={
            "action": action,
            "status": "client_disconnected",
            "status_code": 499,
            "message": "Client disconnected before the request could be completed.",
            "timestamp": time.time(),
            "data": None,
        },
    )


class FastApiAdapter(AdapterInboundPort):
    def __init__(self, service_port: ServicePort, app: FastAPI, config: InitInboundAdapterDto):
        self.service_port = service_port
        self.app = app
        logger.info("FastApiAdapter initialized service_port=%s", type(service_port).__name__)
        self.register_routes(self.app)

    def register_routes(self, app: FastAPI):
        logger.info("Registering FastAPI routes")

        @app.get("/health", tags=["Health"])
        async def health_check():
            logger.info("HTTP GET /health received")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "action": "health_check",
                    "status": "success",
                    "status_code": status.HTTP_200_OK,
                    "message": "Service is healthy",
                    "timestamp": time.time(),
                    "data": None
                }
            )

        @app.get("/available", status_code=status.HTTP_200_OK)
        async def handle_check_availability():
            logger.info("HTTP GET /available received")
            try:
                request_dto = TTSAvailabilityRequestDto()
                response = await self.is_available(request_dto)
                logger.info("HTTP GET /available succeeded is_available=%s", response.is_available)
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "action": "check_availability",
                        "status": "success",
                        "status_code": status.HTTP_200_OK,
                        "message": "Availability checked successfully",
                        "timestamp": time.time(),
                        "data": {"is_available": response.is_available}
                    }
                )
            except Exception as e:
                logger.exception("HTTP GET /available failed")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "check_availability",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to check availability: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )

        @app.post("/process/stream", status_code=status.HTTP_200_OK)
        async def handle_process_stream(
            request: Request,
            sample_rate: int = 22050,
            channels: int = 1,
        ):
            logger.info(
                "HTTP POST /process/stream received sample_rate=%s channels=%s",
                sample_rate,
                channels,
            )
            try:
                body_bytes = await request.body()
                body_str = body_bytes.decode("utf-8")
                lines = [line.strip() for line in body_str.split("\n") if line.strip()]
                logger.info(
                    "HTTP POST /process/stream parsed body_bytes=%s non_empty_lines=%s",
                    len(body_bytes),
                    len(lines),
                )

                async def text_stream_generator() -> AsyncIterator[str]:
                    for line in lines:
                        logger.info("HTTP /process/stream yielding text line length=%s", len(line))
                        yield line

                request_dto = ProcessStreamRequestDto(
                    text_stream=text_stream_generator(),
                    sample_rate=sample_rate,
                    channels=channels,
                )

                response = await self.process_stream(request_dto)

                async def audio_chunk_generator() -> AsyncIterator[bytes]:
                    chunk_count = 0
                    total_bytes = 0
                    async for chunk in response.audio_stream:
                        chunk_count += 1
                        total_bytes += len(chunk)
                        logger.info(
                            "HTTP /process/stream yielding audio chunk chunk_count=%s chunk_bytes=%s total_bytes=%s",
                            chunk_count,
                            len(chunk),
                            total_bytes,
                        )
                        yield chunk
                    logger.info(
                        "HTTP /process/stream audio stream completed chunk_count=%s total_bytes=%s",
                        chunk_count,
                        total_bytes,
                    )

                return StreamingResponse(
                    audio_chunk_generator(),
                    media_type="audio/wav",
                    status_code=status.HTTP_200_OK,
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Action": "process_stream",
                        "X-Status": "success",
                        "X-Message": "Stream processed successfully",
                        "X-Timestamp": str(time.time()),
                    }
                )
            except ClientDisconnect:
                logger.warning("HTTP POST /process/stream client disconnected while reading request body")
                return _client_disconnect_response("process_stream")
            except Exception as e:
                logger.exception("HTTP POST /process/stream failed")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "process_stream",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to process stream: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )

        # ──────────────────────────────────────────────
        # DECOUPLED STREAM (Single Flow)
        # ──────────────────────────────────────────────

        @app.post("/process/stream/set", status_code=status.HTTP_202_ACCEPTED)
        async def handle_set_stream(
            request: Request,
            sample_rate: int = 22050,
            channels: int = 1,
        ):
            logger.info(
                "HTTP POST /process/stream/set received sample_rate=%s channels=%s",
                sample_rate,
                channels,
            )
            try:
                body_bytes = await request.body()
                body_str = body_bytes.decode("utf-8")
                lines = [line.strip() for line in body_str.split("\n") if line.strip()]
                logger.info(
                    "HTTP POST /process/stream/set parsed body_bytes=%s non_empty_lines=%s",
                    len(body_bytes),
                    len(lines),
                )

                async def text_stream_generator() -> AsyncIterator[str]:
                    for line in lines:
                        logger.info("HTTP /process/stream/set yielding text line length=%s", len(line))
                        yield line

                request_dto = SetStreamRequestDto(
                    text_stream=text_stream_generator(),
                    sample_rate=sample_rate,
                    channels=channels,
                )

                await self.set_stream(request_dto)
                logger.info("HTTP POST /process/stream/set accepted background synthesis")

                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={
                        "action": "set_stream",
                        "status": "accepted",
                        "status_code": status.HTTP_202_ACCEPTED,
                        "message": "Stream accepted. Background synthesis started.",
                        "timestamp": time.time(),
                        "data": None,
                    }
                )
            except ClientDisconnect:
                logger.warning("HTTP POST /process/stream/set client disconnected while reading request body")
                return _client_disconnect_response("set_stream")
            except Exception as e:
                logger.exception("HTTP POST /process/stream/set failed")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "set_stream",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to set stream: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e),
                    }
                )

        @app.get("/process/stream/get", status_code=status.HTTP_200_OK)
        async def handle_get_stream():
            logger.info("HTTP GET /process/stream/get received")
            try:
                request_dto = GetStreamRequestDto()
                response = await self.get_stream(request_dto)

                async def audio_chunk_generator() -> AsyncIterator[bytes]:
                    chunk_count = 0
                    total_bytes = 0
                    async for chunk in response.audio_stream:
                        chunk_count += 1
                        total_bytes += len(chunk)
                        logger.info(
                            "HTTP /process/stream/get yielding audio chunk chunk_count=%s chunk_bytes=%s total_bytes=%s",
                            chunk_count,
                            len(chunk),
                            total_bytes,
                        )
                        yield chunk
                    logger.info(
                        "HTTP /process/stream/get audio stream completed chunk_count=%s total_bytes=%s",
                        chunk_count,
                        total_bytes,
                    )

                return StreamingResponse(
                    audio_chunk_generator(),
                    media_type="audio/wav",
                    status_code=status.HTTP_200_OK,
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Action": "get_stream",
                        "X-Status": "success",
                        "X-Message": "Decoupled stream retrieved successfully",
                        "X-Timestamp": str(time.time()),
                    }
                )
            except Exception as e:
                logger.exception("HTTP GET /process/stream/get failed")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "get_stream",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to get stream: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e),
                    }
                )

        @app.post("/process/batch", status_code=status.HTTP_200_OK)
        async def handle_process_batch(
            text: str = "",
            sample_rate: int = 22050,
            channels: int = 1,
        ):
            logger.info(
                "HTTP POST /process/batch received text_length=%s sample_rate=%s channels=%s",
                len(text),
                sample_rate,
                channels,
            )
            try:
                if not text or text.strip() == "":
                    logger.warning("HTTP POST /process/batch rejected empty text")
                    raise HTTPException(status_code=400, detail="No text provided")

                request_dto = ProcessBatchRequestDto(
                    text=text,
                    sample_rate=sample_rate,
                    channels=channels,
                )

                response = await self.process_batch(request_dto)

                # Return raw audio as standard attachment, or hex, or in data envelope.
                # In standard envelope, we can encode audio as base64 for easy transport,
                # or return raw binary with headers. Let's return StreamingResponse/audio/wav
                # directly for batch too, but standard response envelope can hold Base64.
                # To match STT format of response envelope:
                import base64
                encoded_audio = base64.b64encode(response.audio_data).decode("utf-8")
                logger.info(
                    "HTTP POST /process/batch succeeded audio_bytes=%s encoded_length=%s",
                    len(response.audio_data),
                    len(encoded_audio),
                )

                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "action": "process_batch",
                        "status": "success",
                        "status_code": status.HTTP_200_OK,
                        "message": "Text synthesized successfully",
                        "timestamp": time.time(),
                        "data": {
                            "audio_data_base64": encoded_audio,
                            "sample_rate": sample_rate,
                            "channels": channels
                        }
                    }
                )
            except Exception as e:
                logger.exception("HTTP POST /process/batch failed")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "process_batch",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to process batch: {str(e)}\n" + e.__str__(),
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )
        logger.info("FastAPI routes registered")

    def start_autoload(self) -> None:
        logger.info("FastApiAdapter.start_autoload called; no autoload task configured")

    async def stop_autoload(self) -> None:
        logger.info("FastApiAdapter.stop_autoload called; no autoload task configured")

    @property
    def get_app(self) -> Any:
        logger.info("FastApiAdapter.get_app accessed")
        return self.app

    async def process_stream(self, request: ProcessStreamRequestDto) -> ProcessStreamResponseDto:
        logger.info("FastApiAdapter.process_stream mapping inbound request to service request")
        service_request_dto = map_inbound_to_service_stream_request(request)
        service_response_dto = await self.service_port.process_stream(service_request_dto)
        adapter_response_dto = map_service_to_inbound_stream_response(service_response_dto)
        logger.info("FastApiAdapter.process_stream completed")
        return adapter_response_dto

    async def process_batch(self, request: ProcessBatchRequestDto) -> ProcessBatchResponseDto:
        logger.info("FastApiAdapter.process_batch mapping inbound request to service request")
        service_request_dto = map_inbound_to_service_batch_request(request)
        service_response_dto = await self.service_port.process_batch(service_request_dto)
        adapter_response_dto = map_service_to_inbound_batch_response(service_response_dto)
        logger.info("FastApiAdapter.process_batch completed")
        return adapter_response_dto

    async def set_stream(self, request: SetStreamRequestDto) -> None:
        logger.info("FastApiAdapter.set_stream mapping inbound request to service request")
        service_request_dto = map_inbound_to_service_set_stream_request(request)
        await self.service_port.set_stream(service_request_dto)
        logger.info("FastApiAdapter.set_stream completed")

    async def get_stream(self, request: GetStreamRequestDto) -> GetStreamResponseDto:
        logger.info("FastApiAdapter.get_stream mapping inbound request to service request")
        service_request_dto = map_inbound_to_service_get_stream_request(request)
        service_response_dto = await self.service_port.get_stream(service_request_dto)
        adapter_response_dto = map_service_to_inbound_get_stream_response(service_response_dto)
        logger.info("FastApiAdapter.get_stream completed")
        return adapter_response_dto

    async def is_available(self, request: TTSAvailabilityRequestDto) -> TTSAvailabilityResponseDto:
        logger.info("FastApiAdapter.is_available mapping inbound request to service request")
        service_request_dto = map_inbound_to_service_availability_request(request)
        service_response_dto = await self.service_port.is_available(service_request_dto)
        adapter_response_dto = map_service_to_inbound_availability_response(service_response_dto)
        logger.info("FastApiAdapter.is_available completed is_available=%s", adapter_response_dto.is_available)
        return adapter_response_dto
