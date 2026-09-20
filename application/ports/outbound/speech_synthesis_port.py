from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from application.dtos.audio_segment_outbound import (
    AudioChunk,
    AudioSegmentEvent,
    SegmentCompleted,
    SegmentFailed,
)
from application.errors import SynthesisFailed
from domain.value_objects.audio_format import AudioFormat

_FRAMES_PER_CHUNK = 1024
_BYTES_PER_SAMPLE = 2


class SpeechSynthesisPort(ABC):
    """What the application needs from a text-to-speech engine."""

    @abstractmethod
    def synthesize_stream(
        self, text_stream: AsyncIterator[str], audio_format: AudioFormat
    ) -> AsyncIterator[bytes]:
        """Speak each text of ``text_stream`` and yield the PCM chunks as they are produced.

        The texts are consumed as the returned iterator is consumed. A synthesis failure ends
        the audio stream (it is logged, not raised).
        """

    @abstractmethod
    async def synthesize(self, text: str, audio_format: AudioFormat) -> bytes:
        """Speak one text and return all of its PCM. Raises SynthesisFailed on failure."""

    @abstractmethod
    async def is_available(self) -> bool:
        """True if the engine can be started."""

    async def synthesize_segments(
        self, text_stream: AsyncIterator[str], audio_format: AudioFormat
    ) -> AsyncIterator[AudioSegmentEvent]:
        """Speak each text as one segment: its audio chunks, then ``SegmentCompleted``.

        A text that cannot be spoken yields ``SegmentFailed`` and the stream goes on with the next
        text, so one bad sentence does not silence the conversation.
        """
        chunk_bytes = _FRAMES_PER_CHUNK * audio_format.channels * _BYTES_PER_SAMPLE
        async for text in text_stream:
            try:
                audio = await self.synthesize(text, audio_format)
            except SynthesisFailed as error:
                yield SegmentFailed(message=str(error))
                continue
            for start in range(0, len(audio), chunk_bytes):
                yield AudioChunk(audio[start : start + chunk_bytes])
            yield SegmentCompleted(text=text)
