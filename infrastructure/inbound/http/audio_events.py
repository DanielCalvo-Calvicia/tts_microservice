"""Frames synthesized audio as the TTS outbound stream contract (NDJSON events)."""

import asyncio
import base64
from collections.abc import AsyncIterator
from contextlib import suppress

from contracts.stream.codec import EventSequencer, encode_ndjson
from contracts.stream.common.error import ErrorEvent, ErrorEventDTO
from contracts.stream.common.heartbeat import HeartbeatEvent
from contracts.stream.microservices.tts.outbound.completed import (
    CompletedOutboundEvent,
    CompletedOutboundEventDTO,
)
from contracts.stream.microservices.tts.outbound.stream_started import (
    TTSStreamStartedOutboundEvent,
    TTSStreamStartedOutboundEventDTO,
)
from contracts.stream.microservices.tts.outbound.partial import (
    PartialOutboundEvent,
    PartialOutboundEventDTO,
)
from shared_logging import get_logger

from application.dtos.audio_segment_outbound import (
    AudioChunk,
    AudioSegmentEvent,
    SegmentCompleted,
    SegmentFailed,
    StreamFormat,
)

logger = get_logger(__name__)

NDJSON_MEDIA_TYPE = "application/x-ndjson"


async def audio_events_as_ndjson(
    events: AsyncIterator[AudioSegmentEvent], *, heartbeat_interval_seconds: float | None = None
) -> AsyncIterator[bytes]:
    """``stream_started``, then per spoken text: ``partial`` per audio chunk and one ``completed``.

    A text that fails is reported as a recoverable ``error`` event and the stream carries on. When
    nothing arrives for ``heartbeat_interval_seconds`` a ``heartbeat`` keeps the connection alive.
    """
    sequence = EventSequencer()
    started = False  # stream_started goes out with the format, which is the first item

    iterator = events.__aiter__()
    pending: asyncio.Future[AudioSegmentEvent] | None = None
    segment: list[bytes] = []
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(iterator.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=heartbeat_interval_seconds)
            if not done:
                if started:
                    yield encode_ndjson(sequence.next(HeartbeatEvent))
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                pending = None
                break
            pending = None

            if isinstance(event, StreamFormat):
                started = True
                yield encode_ndjson(
                    sequence.next(
                        TTSStreamStartedOutboundEvent,
                        TTSStreamStartedOutboundEventDTO(
                            sample_rate=event.sample_rate, channels=event.channels
                        ),
                    )
                )
            elif isinstance(event, AudioChunk):
                yield encode_ndjson(
                    sequence.next(
                        PartialOutboundEvent,
                        PartialOutboundEventDTO(
                            bytes_base64=base64.b64encode(event.data).decode("ascii"),
                            byte_count=len(event.data),
                            chunk_index=len(segment),
                        ),
                    )
                )
                segment.append(event.data)
            elif isinstance(event, SegmentCompleted):
                audio = b"".join(segment)
                yield encode_ndjson(
                    sequence.next(
                        CompletedOutboundEvent,
                        CompletedOutboundEventDTO(
                            reason="completed",
                            output_bytes_base64=base64.b64encode(audio).decode("ascii"),
                            total_bytes=len(audio),
                            chunk_count=len(segment),
                        ),
                    )
                )
                segment = []
            elif isinstance(event, SegmentFailed):
                segment = []
                yield encode_ndjson(
                    sequence.next(
                        ErrorEvent,
                        ErrorEventDTO(code="synthesis_failed", message=event.message, recoverable=True),
                    )
                )
    except Exception as error:
        logger.exception("TTS audio stream failed")
        yield encode_ndjson(
            sequence.next(
                ErrorEvent, ErrorEventDTO(code="stream_failed", message=str(error), recoverable=False)
            )
        )
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending
