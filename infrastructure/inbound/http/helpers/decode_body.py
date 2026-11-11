from collections.abc import AsyncIterator

from fastapi import Request
from shared_logging import get_logger

from infrastructure.inbound.http.helpers.media_types import NDJSON

logger = get_logger(__name__)


def is_ndjson_request(request: Request) -> bool:
    return NDJSON in request.headers.get("content-type", "").lower()


async def request_body_chunks(request: Request) -> AsyncIterator[bytes]:
    async for chunk in request.stream():
        yield chunk


async def read_text_lines(request: Request) -> list[str]:
    """The non-empty lines of the request body, one text to speak each.

    The body is read up front: ``set_stream`` keeps speaking after the response has been sent,
    when the request can no longer be read.
    """
    body = (await request.body()).decode("utf-8")
    lines = [line.strip() for line in body.split("\n") if line.strip()]
    logger.info("Parsed request body", non_empty_lines=len(lines))
    return lines


async def as_stream(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        logger.info("Yielding text line", length=len(line))
        yield line
