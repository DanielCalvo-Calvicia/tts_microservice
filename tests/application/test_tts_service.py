import asyncio
from collections.abc import AsyncIterator

import pytest

from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.ports.outbound.speech_synthesis_port import SpeechSynthesisPort
from application.services.tts_service import TtsService
from application.dtos.audio_segment_outbound import (
    AudioChunk,
    SegmentCompleted,
    SegmentFailed,
    StreamFormat,
)
from application.errors import SynthesisFailed
from domain.errors import EmptyText, InvalidAudioFormat
from domain.value_objects.audio_format import AudioFormat


class FakeSynthesis(SpeechSynthesisPort):
    """Speaks a text as its UTF-8 bytes, one chunk per text."""

    def __init__(
        self, available: bool = True, fail_on: str | None = None, unspeakable: tuple[str, ...] = ()
    ) -> None:
        self.unspeakable = unspeakable
        self.formats: list[AudioFormat] = []
        self.spoken: list[str] = []
        self.available = available
        self.fail_on = fail_on

    async def synthesize_stream(
        self, text_stream: AsyncIterator[str], audio_format: AudioFormat
    ) -> AsyncIterator[bytes]:
        self.formats.append(audio_format)
        async for text in text_stream:
            if text == self.fail_on:
                raise RuntimeError("engine crashed")
            self.spoken.append(text)
            yield text.encode()

    async def synthesize(self, text: str, audio_format: AudioFormat) -> bytes:
        self.formats.append(audio_format)
        if text == self.fail_on:
            raise RuntimeError("engine crashed")
        if text in self.unspeakable:
            raise SynthesisFailed("no voice for this text")
        self.spoken.append(text)
        return text.encode()

    async def is_available(self) -> bool:
        return self.available


async def _texts(*items: str) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _collect_events(stream) -> list:
    return [event async for event in stream]


async def _collect(stream: AsyncIterator[bytes]) -> list[bytes]:
    return [chunk async for chunk in stream]


def test_process_stream_skips_blank_texts_and_passes_the_format():
    async def run() -> None:
        engine = FakeSynthesis()
        service = TtsService(engine)

        result = await service.process_stream(
            ProcessStreamInboundDTO(
                text_stream=_texts("one", " ", "", "two"), sample_rate=16000, channels=2
            )
        )

        assert await _collect(result.audio_stream) == [b"one", b"two"]
        assert engine.formats == [AudioFormat(sample_rate=16000, channels=2)]

    asyncio.run(run())


def test_invalid_format_is_rejected_before_reaching_the_engine():
    async def run() -> None:
        engine = FakeSynthesis()
        service = TtsService(engine)

        with pytest.raises(InvalidAudioFormat):
            await service.process_stream(ProcessStreamInboundDTO(_texts("x"), sample_rate=0))
        with pytest.raises(InvalidAudioFormat):
            await service.set_stream(ProcessStreamInboundDTO(_texts("x"), channels=0))
        with pytest.raises(InvalidAudioFormat):
            await service.process_batch(ProcessBatchInboundDTO(text="x", sample_rate=0))
        assert engine.formats == []

    asyncio.run(run())


def test_batch_returns_the_engine_audio():
    async def run() -> None:
        engine = FakeSynthesis()
        result = await TtsService(engine).process_batch(ProcessBatchInboundDTO(text="hello"))
        assert result.audio_data == b"hello"
        assert engine.formats == [AudioFormat()]

    asyncio.run(run())


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_batch_rejects_blank_text(text):
    async def run() -> None:
        engine = FakeSynthesis()
        with pytest.raises(EmptyText, match="No text provided"):
            await TtsService(engine).process_batch(ProcessBatchInboundDTO(text=text))
        assert engine.spoken == []

    asyncio.run(run())


def test_availability_comes_from_the_engine():
    async def run() -> None:
        assert await TtsService(FakeSynthesis(available=True)).is_available() is True
        assert await TtsService(FakeSynthesis(available=False)).is_available() is False

    asyncio.run(run())


def test_set_stream_returns_at_once_and_get_stream_delivers_the_audio():
    async def run() -> None:
        service = TtsService(FakeSynthesis())

        await service.set_stream(ProcessStreamInboundDTO(_texts("a", " ", "b")))
        result = await service.get_stream()

        assert await asyncio.wait_for(_collect(result.audio_stream), timeout=2) == [b"a", b"b"]

    asyncio.run(run())


def test_a_reader_that_connected_before_the_first_set_gets_its_audio():
    async def run() -> None:
        service = TtsService(FakeSynthesis())
        reader = asyncio.create_task(_collect((await service.get_stream()).audio_stream))
        await asyncio.sleep(0.05)
        assert not reader.done()  # long-poll: nothing to send yet

        await service.set_stream(ProcessStreamInboundDTO(_texts("late")))

        # Brain opens `set` and `get` concurrently, so `get` may win the race: it must not be lost.
        assert await asyncio.wait_for(reader, timeout=2) == [b"late"]
        assert service.current_format() == (22050, 1)

    asyncio.run(run())


def test_a_new_set_stream_replaces_the_previous_one_and_ends_its_readers():
    async def run() -> None:
        service = TtsService(FakeSynthesis())
        gate = asyncio.Event()

        async def endless() -> AsyncIterator[str]:
            yield "first"
            await gate.wait()

        await service.set_stream(ProcessStreamInboundDTO(endless()))
        old_reader = await service.get_stream()
        assert await old_reader.audio_stream.__anext__() == b"first"

        await service.set_stream(ProcessStreamInboundDTO(_texts("second")))

        # The old reader is told the old stream has ended; the new reader gets the new audio.
        assert await asyncio.wait_for(_collect(old_reader.audio_stream), timeout=2) == []
        new_reader = await service.get_stream()
        assert await asyncio.wait_for(_collect(new_reader.audio_stream), timeout=2) == [b"second"]

    asyncio.run(run())


def test_an_engine_crash_ends_the_shared_stream_instead_of_hanging_it():
    async def run() -> None:
        service = TtsService(FakeSynthesis(fail_on="boom"))

        await service.set_stream(ProcessStreamInboundDTO(_texts("fine", "boom", "never")))
        result = await service.get_stream()

        assert await asyncio.wait_for(_collect(result.audio_stream), timeout=2) == [b"fine"]

    asyncio.run(run())


def test_segment_stream_marks_where_each_text_ends():
    async def run() -> None:
        service = TtsService(FakeSynthesis())

        await service.set_stream(ProcessStreamInboundDTO(_texts("one", " ", "two")))
        result = await service.get_segment_stream()
        events = await asyncio.wait_for(_collect_events(result.events), timeout=2)

        assert events == [
            StreamFormat(22050, 1),
            AudioChunk(b"one"),
            SegmentCompleted(text="one"),
            AudioChunk(b"two"),
            SegmentCompleted(text="two"),
        ]

    asyncio.run(run())


def test_a_text_that_cannot_be_spoken_is_reported_and_the_next_text_is_still_spoken():
    async def run() -> None:
        service = TtsService(FakeSynthesis(unspeakable=("bad",)))

        await service.set_stream(ProcessStreamInboundDTO(_texts("ok", "bad", "again")))
        events = await asyncio.wait_for(
            _collect_events((await service.get_segment_stream()).events), timeout=2
        )

        assert events == [
            StreamFormat(22050, 1),
            AudioChunk(b"ok"),
            SegmentCompleted(text="ok"),
            SegmentFailed(message="no voice for this text"),
            AudioChunk(b"again"),
            SegmentCompleted(text="again"),
        ]

    asyncio.run(run())


def test_an_engine_crash_is_reported_as_a_failure_before_the_stream_ends():
    async def run() -> None:
        service = TtsService(FakeSynthesis(fail_on="boom"))

        await service.set_stream(ProcessStreamInboundDTO(_texts("fine", "boom", "never")))
        events = await asyncio.wait_for(
            _collect_events((await service.get_segment_stream()).events), timeout=2
        )

        assert events[:3] == [StreamFormat(22050, 1), AudioChunk(b"fine"), SegmentCompleted(text="fine")]
        assert isinstance(events[3], SegmentFailed) and "engine crashed" in events[3].message
        assert len(events) == 4

    asyncio.run(run())
