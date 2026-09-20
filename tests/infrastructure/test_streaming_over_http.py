"""The TTS stream contract over a real socket: audio must flow while the text is still arriving.

ASGI test transports buffer whole bodies, so they cannot prove streaming. These tests run the real
application under uvicorn and talk to it with a real HTTP client.
"""

import asyncio
import base64
import socket
import threading
import time
import wave
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import uvicorn
from contracts.stream.codec import (
    EventSequencer,
    encode_ndjson,
    iter_events,
)
from contracts.stream.common.base import EventType
from contracts.stream.common.start_stream import StartStreamEvent
from contracts.stream.microservices.tts.inbound.completed import (
    TTSCompletedInboundEvent,
    TTSCompletedInboundEventDTO,
)
from contracts.stream.schemas import TTS_OUTBOUND
from fastapi import FastAPI

from application.services.tts_service import TtsService
from infrastructure.inbound.http.http_handler import TtsHandler
from infrastructure.outbound.pyttsx3_speech.pyttsx3_speech_synthesis import (
    Pyttsx3SpeechSynthesis,
)

NATIVE_RATE = 22050


class FakeWavSynthesizer:
    """Speaks ``text`` as 0.1 s of a 22.05 kHz mono tone per character."""

    async def synthesize_to_file(self, text: str, file_path: str) -> None:
        with wave.open(file_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(NATIVE_RATE)
            wav_file.writeframes(b"\x10\x00" * (NATIVE_RATE // 10) * len(text))

    async def is_working(self) -> bool:
        return True


@pytest.fixture
def server() -> Iterator[str]:
    app = FastAPI()
    app.include_router(TtsHandler(TtsService(Pyttsx3SpeechSynthesis(FakeWavSynthesizer()))).router)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    uvicorn_server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, lifespan="off")
    )
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not uvicorn_server.started:
        assert time.monotonic() < deadline, "server did not start"
        time.sleep(0.01)
    yield f"http://127.0.0.1:{port}"
    uvicorn_server.should_exit = True
    thread.join(timeout=10)


async def _text_upload(gate: asyncio.Event, texts: list[str]) -> AsyncIterator[bytes]:
    """Brain's upload: stream_started + first text at once, the second only after ``gate``."""
    sequence = EventSequencer()
    yield encode_ndjson(sequence.next(StartStreamEvent))
    for index, text in enumerate(texts):
        if index == 1:
            await gate.wait()
        yield encode_ndjson(
            sequence.next(
                TTSCompletedInboundEvent, TTSCompletedInboundEventDTO(reason="completed", output=text)
            )
        )


async def _audio_events(response: httpx.Response):
    async for event in iter_events(response.aiter_bytes(), TTS_OUTBOUND):
        yield event


def test_audio_of_the_first_text_arrives_before_the_second_text_is_sent(server: str) -> None:
    async def run() -> None:
        gate = asyncio.Event()
        async with httpx.AsyncClient(base_url=server, timeout=10) as client:
            upload = asyncio.create_task(
                client.post(
                    "/process/stream/set",
                    params={"sample_rate": 24000, "channels": 1},
                    content=_text_upload(gate, ["hi", "there"]),
                    headers={"content-type": "application/x-ndjson"},
                )
            )
            await asyncio.sleep(0.2)
            async with client.stream("GET", "/process/stream/get") as response:
                assert response.headers["content-type"].startswith("application/x-ndjson")
                events = _audio_events(response)
                seen = []
                async for event in events:
                    seen.append(event)
                    if event.type is EventType.COMPLETED:
                        break
                # the first text is fully spoken while the sender still holds back the second
                assert not upload.done()
                first_audio = base64.b64decode(seen[-1].payload.output_bytes_base64)
                # 2 characters * 0.1 s at the REQUESTED 24 kHz (not the engine's 22.05 kHz), 16-bit
                assert len(first_audio) == round(2 * NATIVE_RATE / 10 * 24000 / NATIVE_RATE) * 2

                gate.set()
                async for event in events:
                    seen.append(event)
            ack = await upload

        assert ack.status_code == 202
        assert [e.type for e in seen if e.type is not EventType.PARTIAL] == [
            EventType.START_STREAM,
            EventType.COMPLETED,
            EventType.COMPLETED,
        ]
        assert [e.sequence for e in seen] == list(range(1, len(seen) + 1))

    asyncio.run(run())
