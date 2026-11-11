from fastapi import Request, status
from fastapi.responses import Response, StreamingResponse

from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.ports.inbound.tts_inbound_port import TtsInboundPort
from infrastructure.inbound.http.helpers.decode_body import as_stream, read_text_lines
from infrastructure.inbound.http.helpers.media_types import WAV
from infrastructure.inbound.http.response.counted_audio import counted_audio
from infrastructure.inbound.http.response.http_envelope import failure
from infrastructure.inbound.http.response.stream_headers import stream_headers


async def handle_process_stream(
    request: Request, sample_rate: int, channels: int, inbound: TtsInboundPort
) -> Response:
    """POST /process/stream?sample_rate=&channels=: one text per line in the body, headerless PCM16 back."""
    try:
        lines = await read_text_lines(request)
        result = await inbound.process_stream(
            ProcessStreamInboundDTO(text_stream=as_stream(lines), sample_rate=sample_rate, channels=channels)
        )
    except Exception as error:
        return failure("process_stream", "Failed to process stream", error)
    return StreamingResponse(
        counted_audio(result.audio_stream, "/process/stream"),
        media_type=WAV,
        status_code=status.HTTP_200_OK,
        headers=stream_headers("process_stream", "success", "Stream processed successfully"),
    )
