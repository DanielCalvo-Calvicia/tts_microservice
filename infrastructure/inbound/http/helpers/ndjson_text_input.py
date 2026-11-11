"""Decodes the NDJSON request body of ``POST /process/stream/set`` (the TTS inbound contract)."""

from collections.abc import AsyncIterator
from typing import Any

from contracts.stream.codec import NdjsonDecoder
from contracts.stream.common.base import BaseEvent, EventType
from contracts.stream.schemas import TTS_INBOUND
from shared_logging import get_logger

logger = get_logger(__name__)


class UpstreamStreamError(RuntimeError):
    """The sender reported an ``error`` event on the text stream."""


async def texts_from_ndjson(chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
    """One text to speak per ``completed`` event.

    ``partial`` events carry pieces of the text being built; the ``completed`` event that closes
    them carries the whole text, so it is what gets spoken (speaking both would say it twice). Text
    left in partials when the stream ends without a ``completed`` is spoken as a last utterance.
    """
    decoder = NdjsonDecoder(TTS_INBOUND)
    pending: list[str] = []

    def text_of(event: BaseEvent[Any]) -> str | None:
        if event.type is EventType.PARTIAL:
            pending.append(event.payload.text)
        elif event.type is EventType.COMPLETED:
            text = event.payload.output or "".join(pending)
            pending.clear()
            return text
        elif event.type is EventType.ERROR:
            raise UpstreamStreamError(f"{event.payload.code}: {event.payload.message}")
        return None

    async for chunk in chunks:
        for event in decoder.feed(chunk):
            if (text := text_of(event)) is not None:
                yield text
    for event in decoder.finish():
        if (text := text_of(event)) is not None:
            yield text
    if pending:
        logger.info("Text stream ended without a completed event; speaking the leftover partials")
        yield "".join(pending)
