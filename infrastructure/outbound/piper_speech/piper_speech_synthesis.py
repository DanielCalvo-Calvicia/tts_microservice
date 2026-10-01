"""Outbound adapter: speaks text with a Piper neural voice and gives it a droid colour.

Implements ``SpeechSynthesisPort``. The engine (``PiperEngine``) is a collaborator so the pitch, effect and
format handling can be tested without a voice model.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Protocol

import numpy as np
from shared_logging import get_logger

from application.errors import SynthesisFailed
from application.ports.outbound.speech_synthesis_port import SpeechSynthesisPort
from domain.operations.pcm import convert_pcm16
from domain.value_objects.audio_format import AudioFormat
from infrastructure.outbound.piper_speech import droid_voice

logger = get_logger(__name__)

_FRAMES_PER_CHUNK = 1024
_BYTES_PER_SAMPLE = 2


class FloatSynthesizer(Protocol):
    @property
    def sample_rate(self) -> int: ...

    def synthesize(self, text: str, speed: float) -> np.ndarray: ...


class PiperSpeechSynthesis(SpeechSynthesisPort):
    def __init__(
        self,
        engine: FloatSynthesizer,
        *,
        speed: float,
        pitch_semitones: float,
        effect_strength: float,
    ) -> None:
        self._engine = engine
        self._speed = speed
        self._pitch_ratio = droid_voice.semitones_to_ratio(pitch_semitones)
        self._effect_strength = effect_strength

    async def synthesize_stream(
        self, text_stream: AsyncIterator[str], audio_format: AudioFormat
    ) -> AsyncIterator[bytes]:
        total_bytes = 0
        try:
            async for text in text_stream:
                pcm = await self.synthesize(text, audio_format)
                step = _FRAMES_PER_CHUNK * audio_format.channels * _BYTES_PER_SAMPLE
                for start in range(0, len(pcm), step):
                    total_bytes += len(pcm[start : start + step])
                    yield pcm[start : start + step]
                    await asyncio.sleep(0.001)  # yield control to prevent starvation
        except Exception:
            logger.exception("Speech synthesis failed; ending the audio stream")
        logger.info("Speech stream completed", total_bytes=total_bytes)

    async def synthesize(self, text: str, audio_format: AudioFormat) -> bytes:
        try:
            return await asyncio.to_thread(self._render, text, audio_format)
        except SynthesisFailed:
            raise
        except Exception as error:
            raise SynthesisFailed(f"Piper synthesis failed: {error}") from error

    async def is_available(self) -> bool:
        return True  # the voice is loaded (or the engine was not chosen) before the service starts

    def _render(self, text: str, audio_format: AudioFormat) -> bytes:
        # Piper talks slower by the pitch ratio; reading its samples back faster lifts the pitch and
        # restores the speed, so the pitch lift is just the resampling to the requested rate.
        samples = self._engine.synthesize(text, speed=self._speed / self._pitch_ratio)
        effective_rate = self._engine.sample_rate * self._pitch_ratio
        samples = droid_voice.resample(samples, effective_rate, audio_format.sample_rate)
        samples = droid_voice.droid_effect(
            samples, audio_format.sample_rate, self._effect_strength
        )
        return convert_pcm16(
            droid_voice.to_pcm16(samples),
            src_rate=audio_format.sample_rate,
            src_channels=1,
            dst_rate=audio_format.sample_rate,
            dst_channels=audio_format.channels,
        )
