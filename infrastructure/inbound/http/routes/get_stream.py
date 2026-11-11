from fastapi import status
from fastapi.responses import Response, StreamingResponse

from application.errors import AudioFormatMismatch
from application.ports.inbound.tts_inbound_port import TtsInboundPort
from infrastructure.inbound.http.helpers.media_types import NDJSON
from infrastructure.inbound.http.response.audio_events import audio_events_as_ndjson
from infrastructure.inbound.http.response.http_envelope import failure
from infrastructure.inbound.http.response.stream_headers import stream_headers

HEARTBEAT_SECONDS = 15.0


async def handle_get_stream(
    sample_rate: int | None, channels: int | None, inbound: TtsInboundPort
) -> Response:
    """GET /process/stream/get: the synthesized audio as TTS outbound contract events (NDJSON).

    The audio format was fixed by ``set``; ``sample_rate``/``channels`` repeated here must match (422 if not).
    """
    try:
        active = inbound.current_format()
        if active is not None:
            for name, given, actual in (
                ("sample_rate", sample_rate, active[0]),
                ("channels", channels, active[1]),
            ):
                if given is not None and given != actual:
                    raise AudioFormatMismatch(f"{name}={given} differs from the stream's {name}={actual}")
        result = await inbound.get_segment_stream()
    except Exception as error:
        return failure("get_stream", "Failed to get stream", error)
    return StreamingResponse(
        audio_events_as_ndjson(result.events, heartbeat_interval_seconds=HEARTBEAT_SECONDS),
        media_type=NDJSON,
        status_code=status.HTTP_200_OK,
        headers=stream_headers("get_stream", "success", "Decoupled stream retrieved successfully"),
    )
