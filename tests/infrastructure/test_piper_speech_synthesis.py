"""PiperSpeechSynthesis against a fake engine: pitch, format and failure handling without a voice model."""

import asyncio
from collections.abc import AsyncIterator

import numpy as np
import pytest

from application.errors import SynthesisFailed
from domain.value_objects.audio_format import AudioFormat
from infrastructure.outbound.piper_speech.piper_speech_synthesis import PiperSpeechSynthesis

FORMAT = AudioFormat(sample_rate=24000, channels=1)


class FakeEngine:
    """Speaks every text as one second of a 200 Hz tone at 22.05 kHz and remembers how it was asked."""

    sample_rate = 22050

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, float]] = []
        self.fail_on = fail_on

    def synthesize(self, text: str, speed: float) -> np.ndarray:
        self.calls.append((text, speed))
        if text == self.fail_on:
            raise RuntimeError("model blew up")
        time = np.arange(22050) / 22050
        return (0.5 * np.sin(2 * np.pi * 200 * time)).astype(np.float32)


def _adapter(engine: FakeEngine, pitch: float = 0.0, effect: float = 0.0) -> PiperSpeechSynthesis:
    return PiperSpeechSynthesis(engine, speed=1.0, pitch_semitones=pitch, effect_strength=effect)


async def _texts(*items: str) -> AsyncIterator[str]:
    for item in items:
        yield item


def test_batch_returns_one_second_of_pcm16_in_the_requested_rate():
    audio = asyncio.run(_adapter(FakeEngine()).synthesize("hello", FORMAT))

    assert abs(len(audio) - 24000 * 2) <= 4


def test_stereo_is_the_mono_signal_duplicated():
    audio = asyncio.run(_adapter(FakeEngine()).synthesize("hello", AudioFormat(24000, 2)))
    samples = np.frombuffer(audio, dtype="<i2")

    assert len(samples) % 2 == 0
    assert np.array_equal(samples[0::2], samples[1::2])


def test_pitch_lift_asks_for_slower_speech_and_raises_the_tone():
    engine = FakeEngine()

    audio = asyncio.run(_adapter(engine, pitch=12).synthesize("hello", FORMAT))

    # One octave up: the fake's second of tone is read back twice as fast, so Piper is asked to talk
    # twice as slowly to keep the pace of the real voice.
    assert engine.calls == [("hello", pytest.approx(0.5))]
    samples = np.frombuffer(audio, dtype="<i2").astype(np.float32)
    peak = np.argmax(np.abs(np.fft.rfft(samples)))
    assert peak * FORMAT.sample_rate / len(samples) == pytest.approx(400, abs=3)


def test_the_effect_is_applied_when_enabled():
    plain = asyncio.run(_adapter(FakeEngine(), effect=0.0).synthesize("hi", FORMAT))
    droid = asyncio.run(_adapter(FakeEngine(), effect=1.0).synthesize("hi", FORMAT))

    assert plain != droid and len(plain) == len(droid)


def test_stream_yields_chunks_of_at_most_1024_frames_for_every_text_in_order():
    async def run() -> tuple[FakeEngine, list[bytes]]:
        engine = FakeEngine()
        chunks = [c async for c in _adapter(engine).synthesize_stream(_texts("a", "b"), FORMAT)]
        return engine, chunks

    engine, chunks = asyncio.run(run())

    assert [text for text, _ in engine.calls] == ["a", "b"]
    assert all(0 < len(chunk) <= 1024 * 2 for chunk in chunks)
    assert abs(sum(map(len, chunks)) - 2 * 24000 * 2) <= 8


def test_batch_raises_synthesis_failed_when_the_engine_breaks():
    with pytest.raises(SynthesisFailed, match="model blew up"):
        asyncio.run(_adapter(FakeEngine(fail_on="x")).synthesize("x", FORMAT))


def test_stream_ends_cleanly_after_a_failure():
    async def run() -> list[bytes]:
        adapter = _adapter(FakeEngine(fail_on="bad"))
        return [chunk async for chunk in adapter.synthesize_stream(_texts("bad", "good"), FORMAT)]

    assert asyncio.run(run()) == []


def test_segments_report_a_failed_text_and_go_on_with_the_next():
    async def run() -> list[str]:
        adapter = _adapter(FakeEngine(fail_on="bad"))
        return [
            type(event).__name__
            async for event in adapter.synthesize_segments(_texts("bad", "good"), FORMAT)
        ]

    kinds = asyncio.run(run())

    assert kinds[0] == "SegmentFailed"
    assert kinds[-1] == "SegmentCompleted" and "AudioChunk" in kinds


def test_is_available():
    assert asyncio.run(_adapter(FakeEngine()).is_available()) is True
