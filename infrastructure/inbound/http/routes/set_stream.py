from fastapi import Request, status
from fastapi.responses import Response

from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.ports.inbound.tts_inbound_port import TtsInboundPort
from infrastructure.inbound.http.helpers.decode_body import (
    as_stream,
    is_ndjson_request,
    read_text_lines,
    request_body_chunks,
)
from infrastructure.inbound.http.helpers.ndjson_text_input import texts_from_ndjson
from infrastructure.inbound.http.response.http_envelope import failure, success
from infrastructure.inbound.http.response.input_stream_response import InputStreamResponse, TrackedTexts
from infrastructure.inbound.http.response.stream_headers import stream_headers


async def handle_set_stream(
    request: Request, sample_rate: int, channels: int, inbound: TtsInboundPort
) -> Response:
    """POST /process/stream/set: accept the text to speak; the audio is read with ``/process/stream/get``.

    ``Content-Type: application/x-ndjson`` is the Brain protocol: a live stream of TTS inbound
    contract events, consumed as it arrives while the response (the ack stream) stays open. Any other
    body is a plain text (one utterance per line), read up front, for simple clients.
    """
    if is_ndjson_request(request):
        return await _set_event_stream(request, sample_rate, channels, inbound)
    try:
        lines = await read_text_lines(request)
        await inbound.set_stream(
            ProcessStreamInboundDTO(text_stream=as_stream(lines), sample_rate=sample_rate, channels=channels)
        )
    except Exception as error:
        return failure("set_stream", "Failed to set stream", error)
    return success(
        "set_stream",
        "Stream accepted. Background synthesis started.",
        code=status.HTTP_202_ACCEPTED,
        state="accepted",
    )


async def _set_event_stream(
    request: Request, sample_rate: int, channels: int, inbound: TtsInboundPort
) -> Response:
    tracked = TrackedTexts(texts_from_ndjson(request_body_chunks(request)))
    try:
        await inbound.set_stream(
            ProcessStreamInboundDTO(text_stream=tracked.stream(), sample_rate=sample_rate, channels=channels)
        )
    except Exception as error:
        return failure("set_stream", "Failed to set stream", error)
    return InputStreamResponse(
        tracked, headers=stream_headers("set_stream", "success", "Input stream connection established")
    )
