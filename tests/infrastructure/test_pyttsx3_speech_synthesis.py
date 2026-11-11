"""Pyttsx3SpeechSynthesis against a fake synthesizer that writes real WAV files."""

import asyncio
import os
import wave
from collections.abc import AsyncIterator

import pytest

from application.errors import SynthesisFailed
from domain.value_objects.audio_format import AudioFormat
from infrastructure.outbound.pyttsx3_speech.pyttsx3_speech_synthesis import (
    Pyttsx3SpeechSynthesis,
)
from infrastructure.outbound.pyttsx3_speech.pyttsx3_subprocess import Pyttsx3Subprocess

FORMAT = AudioFormat()


class FakeWavSynthesizer:
    """Speaks ``text`` as ``len(text)`` frames of a sample value derived from the text."""

    def __init__(self, working: bool = True, fail_on: str | None = None) -> None:
        self.paths: list[str] = []
        self.working = working
        self.fail_on = fail_on

    async def synthesize_to_file(self, text: str, file_path: str) -> None:
        self.paths.append(file_path)
        if text == self.fail_on:
            raise SynthesisFailed("no voice installed")
        with wave.open(file_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(bytes([ord(text[0]), 0]) * len(text) * 1000)

    async def is_working(self) -> bool:
        return self.working


async def _texts(*items: str) -> AsyncIterator[str]:
    for item in items:
        yield item


def test_batch_returns_all_of_the_pcm_not_just_the_last_chunk():
    async def run() -> None:
        synthesizer = FakeWavSynthesizer()
        audio = await Pyttsx3SpeechSynthesis(synthesizer).synthesize("ab", FORMAT)

        assert len(audio) == 2 * 1000 * 2  # 2000 frames of 16-bit mono
        assert audio == bytes([ord("a"), 0]) * 2000
        assert all(not os.path.exists(path) for path in synthesizer.paths)

    asyncio.run(run())


def test_stream_yields_chunks_of_1024_frames_for_every_text_in_order():
    async def run() -> None:
        synthesis = Pyttsx3SpeechSynthesis(FakeWavSynthesizer())

        # "aaa" is 3000 frames: chunks of 1024, 1024 and 952 frames
        chunks = [c async for c in synthesis.synthesize_stream(_texts("aaa", "bbb"), FORMAT)]

        assert [len(c) for c in chunks] == [2048, 2048, 1904, 2048, 2048, 1904]
        assert b"".join(chunks) == bytes([ord("a"), 0]) * 3000 + bytes([ord("b"), 0]) * 3000

    asyncio.run(run())


def test_a_synthesis_failure_ends_the_stream_and_keeps_earlier_audio():
    async def run() -> None:
        synthesizer = FakeWavSynthesizer(fail_on="bad")
        synthesis = Pyttsx3SpeechSynthesis(synthesizer)

        chunks = [c async for c in synthesis.synthesize_stream(_texts("a", "bad", "c"), FORMAT)]

        assert b"".join(chunks) == bytes([ord("a"), 0]) * 1000
        assert all(not os.path.exists(path) for path in synthesizer.paths)  # temp files cleaned

    asyncio.run(run())


def test_a_synthesis_failure_in_batch_raises_and_cleans_up():
    async def run() -> None:
        synthesizer = FakeWavSynthesizer(fail_on="bad")

        with pytest.raises(SynthesisFailed, match="no voice installed"):
            await Pyttsx3SpeechSynthesis(synthesizer).synthesize("bad", FORMAT)

        assert all(not os.path.exists(path) for path in synthesizer.paths)

    asyncio.run(run())


def test_availability_follows_the_synthesizer():
    async def run() -> None:
        assert await Pyttsx3SpeechSynthesis(FakeWavSynthesizer(working=True)).is_available()
        assert not await Pyttsx3SpeechSynthesis(FakeWavSynthesizer(working=False)).is_available()

    asyncio.run(run())


def test_the_subprocess_script_is_valid_python_whatever_the_text():
    subprocess = Pyttsx3Subprocess(speech_rate=150, voice_name_preference="Zira")
    tricky = 'it\'s "quoted"\nand multi-line \\ with a backslash'

    script = subprocess._script(tricky, "C:\\temp\\out.wav")

    compile(script, "<tts-script>", "exec")  # raises SyntaxError if the text broke the script
    assert "'rate', 150" in script
    assert "'Zira' in voice.name" in script
    assert repr(tricky) in script
