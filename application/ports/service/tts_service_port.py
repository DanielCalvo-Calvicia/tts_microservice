from abc import ABC, abstractmethod

from application.dtos.inbound.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.outbound.audio_batch_outbound import AudioBatchOutboundDTO
from application.dtos.outbound.audio_segment_outbound import AudioSegmentStreamOutboundDTO
from application.dtos.outbound.audio_stream_outbound import AudioStreamOutboundDTO


class TtsServicePort(ABC):
    """The service's own port: the text-to-speech use cases. ``TtsService`` implements it; the inbound adapters
    call it (through the inbound port); nothing else in the application knows the concrete service."""

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

    def fallback_reason(self) -> str | None:
        """Why a fallback voice speaks instead of the configured engine, or None when the configured
        engine speaks. A note for callers of ``/available``; it does not change ``is_available``."""
        return None
