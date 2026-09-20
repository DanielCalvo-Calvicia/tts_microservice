"""Outbound adapter: speaks text by having a synthesizer write a WAV file, then reading it back.

Implements ``SpeechSynthesisPort``. The engine (``Pyttsx3Subprocess``) is a collaborator so the
file/PCM handling can be tested without a speech engine.
"""

import asyncio
import os
import tempfile
import wave
from collections.abc import AsyncIterator
from typing import Protocol

from shared_logging import get_logger

from application.errors import SynthesisFailed
from application.ports.outbound.speech_synthesis_port import SpeechSynthesisPort
from domain.operations.pcm import convert_pcm16
from domain.value_objects.audio_format import AudioFormat

logger = get_logger(__name__)

_FRAMES_PER_CHUNK = 1024
_BYTES_PER_SAMPLE = 2


class WavSynthesizer(Protocol):
    async def synthesize_to_file(self, text: str, file_path: str) -> None: ...

    async def is_working(self) -> bool: ...


class Pyttsx3SpeechSynthesis(SpeechSynthesisPort):
    def __init__(self, synthesizer: WavSynthesizer) -> None:
        self._synthesizer = synthesizer

    async def synthesize_stream(
        self, text_stream: AsyncIterator[str], audio_format: AudioFormat
    ) -> AsyncIterator[bytes]:
        total_bytes = 0
        try:
            async for text in text_stream:
                async for chunk in self._pcm_chunks(text, audio_format):
                    total_bytes += len(chunk)
                    yield chunk
        except Exception:
            logger.exception("Speech synthesis failed; ending the audio stream")
        logger.info("Speech stream completed", total_bytes=total_bytes)

    async def synthesize(self, text: str, audio_format: AudioFormat) -> bytes:
        return b"".join([chunk async for chunk in self._pcm_chunks(text, audio_format)])

    async def is_available(self) -> bool:
        return await self._synthesizer.is_working()

    async def _pcm_chunks(self, text: str, audio_format: AudioFormat) -> AsyncIterator[bytes]:
        """Speak ``text`` into a temporary WAV file and yield its PCM in the requested format.

        The engine writes its own native rate/channels; the audio is converted to
        ``audio_format`` here so callers get exactly the format they asked for.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            temp_path = temp_wav.name
        logger.info("Temporary WAV created", path=temp_path, text_length=len(text))
        try:
            await self._synthesizer.synthesize_to_file(text, temp_path)
            pcm = _read_pcm(temp_path, audio_format)
            step = _FRAMES_PER_CHUNK * audio_format.channels * _BYTES_PER_SAMPLE
            for start in range(0, len(pcm), step):
                yield pcm[start : start + step]
                await asyncio.sleep(0.001)  # yield control to prevent starvation
        finally:
            _remove(temp_path)


def _read_pcm(path: str, audio_format: AudioFormat) -> bytes:
    """The whole WAV at ``path`` as 16-bit PCM in ``audio_format``."""
    try:
        with wave.open(path, "rb") as wav_file:
            if wav_file.getsampwidth() != _BYTES_PER_SAMPLE:
                raise SynthesisFailed(
                    f"engine wrote {wav_file.getsampwidth() * 8}-bit audio; only 16-bit is supported"
                )
            native_rate, native_channels = wav_file.getframerate(), wav_file.getnchannels()
            pcm = wav_file.readframes(wav_file.getnframes())
    except wave.Error as error:
        raise SynthesisFailed(f"engine wrote an unreadable WAV file: {error}") from error
    return convert_pcm16(
        pcm,
        src_rate=native_rate,
        src_channels=native_channels,
        dst_rate=audio_format.sample_rate,
        dst_channels=audio_format.channels,
    )


def _remove(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        os.remove(path)
        logger.info("Temporary WAV removed", path=path)
    except OSError:
        logger.exception("Failed to remove temporary WAV", path=path)
