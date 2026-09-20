"""Response of ``POST /process/stream/set``: an acknowledgement that lives as long as the upload."""

import asyncio
from collections.abc import AsyncIterator

from contracts.stream.codec import EventSequencer, encode_ndjson
from contracts.stream.common.error import ErrorEvent, ErrorEventDTO
from contracts.stream.common.start_stream import StartStreamEvent
from contracts.stream.common.input_completed import InputCompletedEvent, InputCompletedEventDTO
from fastapi import status
from fastapi.responses import Response
from starlette.types import Receive, Scope, Send

NDJSON_MEDIA_TYPE = "application/x-ndjson"


class TrackedTexts:
    """Wraps the text stream so the response can tell when the sender has finished uploading."""

    def __init__(self, source: AsyncIterator[str]) -> None:
        self._source = source
        self._finished = asyncio.Event()
        self.error: Exception | None = None

    def __aiter__(self) -> AsyncIterator[str]:
        return self._iterate()

    async def wait_finished(self) -> None:
        await self._finished.wait()

    async def _iterate(self) -> AsyncIterator[str]:
        try:
            async for text in self._source:
                yield text
        except Exception as error:
            self.error = error
            raise
        finally:
            self._finished.set()


class InputStreamResponse(Response):
    """Acknowledges an upload at once, keeps the request readable while it lasts, then reports.

    The response starts with ``stream_started`` (HTTP 202), stays open while the request body is
    consumed in the background and ends with ``completed`` (``end_of_input``) or ``error``. It has
    to stay open: once a response completes the ASGI server stops delivering the request body.
    """

    def __init__(self, tracked: TrackedTexts, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(
            content=b"",
            status_code=status.HTTP_202_ACCEPTED,
            headers=headers,
            media_type=NDJSON_MEDIA_TYPE,
        )
        self._tracked = tracked
        self.raw_headers = [(n, v) for n, v in self.raw_headers if n.lower() != b"content-length"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        events = EventSequencer()
        await send(
            {"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers}
        )
        await send(
            {
                "type": "http.response.body",
                "body": encode_ndjson(events.next(StartStreamEvent)),
                "more_body": True,
            }
        )
        await self._tracked.wait_finished()
        if self._tracked.error is None:
            final = events.next(InputCompletedEvent, InputCompletedEventDTO())
        else:
            final = events.next(
                ErrorEvent,
                ErrorEventDTO(
                    code="stream_failed", message=str(self._tracked.error), recoverable=True
                ),
            )
        await send({"type": "http.response.body", "body": encode_ndjson(final), "more_body": False})
