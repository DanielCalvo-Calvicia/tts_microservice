import asyncio
import base64
from collections.abc import AsyncIterator

import httpx
from contracts.stream.codec import EventSequencer, NdjsonDecoder, encode_ndjson
from contracts.stream.common.base import EventType
from contracts.stream.common.error import ErrorEvent, ErrorEventDTO
from contracts.stream.common.heartbeat import HeartbeatEvent
from contracts.stream.common.start_stream import StartStreamEvent
from contracts.stream.microservices.tts.inbound.completed import (
    TTSCompletedInboundEvent,
    TTSCompletedInboundEventDTO,
)
from contracts.stream.microservices.tts.inbound.partial import (
    PartialInboundEvent,
    PartialInboundEventDTO,
)
from contracts.stream.schemas import TTS_INPUT_ACK, TTS_OUTBOUND
from fastapi import FastAPI

from application.dtos.audio_batch_outbound import AudioBatchOutboundDTO
from application.dtos.audio_segment_outbound import (
    AudioChunk,
    AudioSegmentStreamOutboundDTO,
    SegmentCompleted,
    SegmentFailed,
    StreamFormat,
)
from application.dtos.audio_stream_outbound import AudioStreamOutboundDTO
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.ports.inbound.tts_synthesis_port import TtsSynthesisPort
from domain.errors import EmptyText
from infrastructure.inbound.http.http_handler import TtsHandler


async def _audio(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


class FakePort(TtsSynthesisPort):
    def __init__(self) -> None:
        self.stream_texts: list[str] = []
        self.set_texts: list[str] = []
        self.set_formats: list[tuple[int, int]] = []
        self.available = True

    async def process_stream(self, request: ProcessStreamInboundDTO) -> AudioStreamOutboundDTO:
        self.stream_texts = [text async for text in request.text_stream]
        return AudioStreamOutboundDTO(audio_stream=_audio(*[t.encode() for t in self.stream_texts]))

    async def set_stream(self, request: ProcessStreamInboundDTO) -> None:
        # Consumed after set_stream returned, like the real background task (whose failures are
        # logged there, not raised to the caller).
        async def later() -> None:
            try:
                self.set_texts = [text async for text in request.text_stream]
            except Exception:  # noqa: BLE001
                pass

        self.set_formats.append((request.sample_rate, request.channels))
        self._task = asyncio.create_task(later())

    async def get_stream(self) -> AudioStreamOutboundDTO:
        return AudioStreamOutboundDTO(audio_stream=_audio(b"pcm-1", b"pcm-2"))

    async def get_segment_stream(self) -> AudioSegmentStreamOutboundDTO:
        async def events():
            yield StreamFormat(24000, 1)
            yield AudioChunk(b"pcm-1")
            yield AudioChunk(b"pcm-2")
            yield SegmentCompleted(text="hello")
            yield SegmentFailed(message="no voice")
            yield AudioChunk(b"pcm-3")
            yield SegmentCompleted(text="again")

        return AudioSegmentStreamOutboundDTO(events=events())

    async def process_batch(self, request: ProcessBatchInboundDTO) -> AudioBatchOutboundDTO:
        if not request.text.strip():
            raise EmptyText("No text provided")
        return AudioBatchOutboundDTO(audio_data=request.text.encode())

    async def is_available(self) -> bool:
        return self.available


def _call(port: FakePort, method: str, path: str, **kwargs) -> httpx.Response:
    async def run() -> httpx.Response:
        app = FastAPI()
        app.include_router(TtsHandler(port).router)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def test_health():
    body = _call(FakePort(), "GET", "/health").json()
    assert body["status"] == "success" and body["action"] == "health_check"


def test_availability_is_wrapped_in_an_object():
    port = FakePort()
    assert _call(port, "GET", "/available").json()["data"] == {"is_available": True, "reason": None}
    port.available = False
    assert _call(port, "GET", "/available").json()["data"] == {"is_available": False, "reason": None}


def test_process_stream_speaks_each_non_empty_line_and_streams_audio():
    port = FakePort()

    response = _call(port, "POST", "/process/stream", content=b"one\r\n\n  two  \n")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["x-action"] == "process_stream"
    assert response.content == b"onetwo"
    assert port.stream_texts == ["one", "two"]


def test_set_stream_is_accepted_and_the_body_is_read_before_the_response():
    port = FakePort()

    response = _call(
        port, "POST", "/process/stream/set?sample_rate=16000&channels=2", content=b"hello\nworld"
    )

    assert response.status_code == 202
    body = response.json()
    assert (body["action"], body["status"], body["status_code"]) == ("set_stream", "accepted", 202)
    assert port.set_texts == ["hello", "world"]
    assert port.set_formats == [(16000, 2)]


def test_get_stream_speaks_the_tts_outbound_contract():
    response = _call(FakePort(), "GET", "/process/stream/get")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert response.headers["x-action"] == "get_stream"

    decoder = NdjsonDecoder(TTS_OUTBOUND)  # validates schema, sequence numbers and timestamps
    events = [*decoder.feed(response.content), *decoder.finish()]
    assert [e.type for e in events] == [
        EventType.START_STREAM,
        EventType.PARTIAL,
        EventType.PARTIAL,
        EventType.COMPLETED,
        EventType.ERROR,
        EventType.PARTIAL,
        EventType.COMPLETED,
    ]
    assert (events[0].payload.sample_rate, events[0].payload.channels) == (24000, 1)
    first_partial, second_partial, completed, error, third_partial, second_completed = events[1:]
    assert base64.b64decode(first_partial.payload.bytes_base64) == b"pcm-1"
    assert (first_partial.payload.chunk_index, second_partial.payload.chunk_index) == (0, 1)
    assert base64.b64decode(completed.payload.output_bytes_base64) == b"pcm-1pcm-2"
    assert (completed.payload.total_bytes, completed.payload.chunk_count) == (10, 2)
    assert (error.payload.code, error.payload.recoverable) == ("synthesis_failed", True)
    assert third_partial.payload.chunk_index == 0  # indexes restart with every spoken text
    assert base64.b64decode(second_completed.payload.output_bytes_base64) == b"pcm-3"


NDJSON = {"content-type": "application/x-ndjson"}


def _text_events(*items: tuple[str, str]) -> bytes:
    """Brain's text stream: stream_started, then ("partial"|"completed", text) events."""
    sequence = EventSequencer()
    events = [sequence.next(StartStreamEvent)]
    for kind, text in items:
        if kind == "partial":
            events.append(sequence.next(PartialInboundEvent, PartialInboundEventDTO(text=text)))
        else:
            events.append(
                sequence.next(
                    TTSCompletedInboundEvent,
                    TTSCompletedInboundEventDTO(reason="completed", output=text),
                )
            )
    return b"".join(encode_ndjson(e) for e in events)


def _ack(response: httpx.Response) -> list:
    return [*NdjsonDecoder(TTS_INPUT_ACK).feed(response.content)]


def test_set_stream_accepts_the_tts_inbound_contract_and_speaks_completed_texts():
    port = FakePort()
    body = _text_events(
        ("partial", "Hel"), ("partial", "lo"), ("completed", "Hello"), ("completed", "Again")
    )

    response = _call(
        port,
        "POST",
        "/process/stream/set?sample_rate=24000&channels=1",
        content=body,
        headers=NDJSON,
    )

    assert response.status_code == 202
    assert response.headers["content-type"].startswith("application/x-ndjson")
    ack = _ack(response)
    assert [e.type for e in ack] == [EventType.START_STREAM, EventType.INPUT_COMPLETED]
    assert ack[-1].payload.reason == "end_of_input"
    assert port.set_texts == ["Hello", "Again"]  # partials are not spoken twice
    assert port.set_formats == [(24000, 1)]


def test_set_stream_speaks_leftover_partials_and_ignores_heartbeats():
    port = FakePort()
    sequence = EventSequencer()
    body = b"".join(
        encode_ndjson(e)
        for e in (
            sequence.next(StartStreamEvent),
            sequence.next(HeartbeatEvent),
            sequence.next(PartialInboundEvent, PartialInboundEventDTO(text="no end")),
        )
    )

    _call(port, "POST", "/process/stream/set", content=body, headers=NDJSON)

    assert port.set_texts == ["no end"]


def test_set_stream_reports_contract_violations_as_an_error_event():
    bad = _call(
        FakePort(),
        "POST",
        "/process/stream/set",
        content=b'{"type":"partial","sequence":1}\n',
        headers=NDJSON,
    )

    assert bad.status_code == 202  # the upload was accepted; the failure is reported in-stream
    last = _ack(bad)[-1]
    assert last.type is EventType.ERROR and last.payload.code == "stream_failed"


def test_set_stream_reports_an_upstream_error_event_as_an_error_event():
    sequence = EventSequencer()
    body = b"".join(
        encode_ndjson(e)
        for e in (
            sequence.next(StartStreamEvent),
            sequence.next(
                ErrorEvent, ErrorEventDTO(code="stt_down", message="lost", recoverable=False)
            ),
        )
    )

    last = _ack(_call(FakePort(), "POST", "/process/stream/set", content=body, headers=NDJSON))[-1]

    assert last.type is EventType.ERROR and "stt_down: lost" in last.payload.message


def test_batch_returns_base64_audio_with_the_requested_format():
    response = _call(FakePort(), "POST", "/process/batch?text=hi&sample_rate=16000&channels=2")

    assert response.status_code == 200
    data = response.json()["data"]
    assert base64.b64decode(data["audio_data_base64"]) == b"hi"
    assert (data["sample_rate"], data["channels"]) == (16000, 2)


def test_batch_without_text_is_a_400():
    for path in ("/process/batch", "/process/batch?text=%20%20"):
        response = _call(FakePort(), "POST", path)
        assert response.status_code == 400
        assert response.json()["message"].startswith("Failed to process batch")
        assert "No text provided" in response.json()["message"]


def test_batch_failure_is_a_500_envelope():
    class Broken(FakePort):
        async def process_batch(self, request):
            raise RuntimeError("engine offline")

    response = _call(Broken(), "POST", "/process/batch?text=hi")

    assert response.status_code == 500
    assert response.json()["message"] == "Failed to process batch: engine offline"


def test_stream_failure_before_audio_is_a_500_envelope():
    class Broken(FakePort):
        async def process_stream(self, request):
            raise RuntimeError("engine offline")

    response = _call(Broken(), "POST", "/process/stream", content=b"hi")

    assert response.status_code == 500
    assert response.json()["action"] == "process_stream"


def test_get_with_a_format_that_differs_from_the_stream_is_a_422():
    class Formatted(FakePort):
        def current_format(self):
            return (24000, 1)

    mismatch = _call(Formatted(), "GET", "/process/stream/get?sample_rate=16000")
    same = _call(Formatted(), "GET", "/process/stream/get?sample_rate=24000&channels=1&keep_open_after_completed=true")

    assert mismatch.status_code == 422 and "sample_rate=16000" in mismatch.json()["message"]
    assert same.status_code == 200


def test_errors_map_to_natural_statuses():
    from application.errors import SynthesisFailed
    from domain.errors import InvalidAudioFormat
    from infrastructure.inbound.http.http_error_mapper import map_error

    assert map_error(EmptyText("x")) == 400
    assert map_error(InvalidAudioFormat("x")) == 422
    assert map_error(SynthesisFailed("x")) == 502
    assert map_error(RuntimeError("x")) == 500
