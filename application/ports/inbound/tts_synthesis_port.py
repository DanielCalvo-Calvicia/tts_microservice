from abc import ABC, abstractmethod

from application.dtos.audio_batch_outbound import AudioBatchOutboundDTO
from application.dtos.audio_segment_outbound import AudioSegmentStreamOutboundDTO
from application.dtos.audio_stream_outbound import AudioStreamOutboundDTO
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO


class TtsSynthesisPort(ABC):
    """What the outside world may ask of the application."""

    @abstractmethod
    async def process_stream(self, request: ProcessStreamInboundDTO) -> AudioStreamOutboundDTO:
        """Speak each text of the stream; the returned audio stream yields PCM chunks."""

    @abstractmethod
    async def set_stream(self, request: ProcessStreamInboundDTO) -> None:
        """Start speaking the stream in the background and return at once.

        A new call replaces the previous one. Read the audio with ``get_stream``.
        """

    @abstractmethod
    async def get_stream(self) -> AudioStreamOutboundDTO:
        """The shared audio stream; it waits if ``set_stream`` has not produced audio yet."""

    def current_format(self) -> tuple[int, int] | None:
        """``(sample_rate, channels)`` the shared stream was set with, or None before any set."""
        return None

    @abstractmethod
    async def get_segment_stream(self) -> AudioSegmentStreamOutboundDTO:
        """Like ``get_stream`` but keeps the boundary of every spoken text, and reports texts
        that failed, so the adapter can frame each segment as its own completed unit."""

    @abstractmethod
    async def process_batch(self, request: ProcessBatchInboundDTO) -> AudioBatchOutboundDTO:
        """Speak a complete text and return all of its audio. Raises EmptyText for blank text."""

    @abstractmethod
    async def is_available(self) -> bool:
        """True if the speech engine works."""
