from abc import ABC, abstractmethod

from application.dtos.inbound.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.outbound.audio_batch_outbound import AudioBatchOutboundDTO
from application.dtos.outbound.audio_segment_outbound import AudioSegmentStreamOutboundDTO
from application.dtos.outbound.audio_stream_outbound import AudioStreamOutboundDTO


class TtsInboundPort(ABC):
    """What every inbound adapter offers, whatever its transport (HTTP today; gRPC, a CLI, ... tomorrow).

    The same operations with DTOs and no transport types: an adapter decodes its own requests into these calls
    and encodes what they return. A new inbound adapter implements this port, so its functions are the same.
    """

    @abstractmethod
    def health(self) -> bool:
        """True while the adapter is serving."""

    @abstractmethod
    async def is_available(self) -> bool:
        """True if the speech engine behind the adapter works."""

    @abstractmethod
    def fallback_reason(self) -> str | None:
        """Why a fallback voice speaks instead of the configured engine, or None when the configured one speaks."""

    @abstractmethod
    def current_format(self) -> tuple[int, int] | None:
        """``(sample_rate, channels)`` the shared stream was set with, or None before any set."""

    @abstractmethod
    async def process_stream(self, request: ProcessStreamInboundDTO) -> AudioStreamOutboundDTO:
        """Speak each text of the stream; the returned audio stream yields PCM chunks."""

    @abstractmethod
    async def set_stream(self, request: ProcessStreamInboundDTO) -> None:
        """Start speaking the shared stream in the background and return at once."""

    @abstractmethod
    async def get_segment_stream(self) -> AudioSegmentStreamOutboundDTO:
        """The shared audio stream with the boundary of every spoken text. Waits if nothing was set yet."""

    @abstractmethod
    async def process_batch(self, request: ProcessBatchInboundDTO) -> AudioBatchOutboundDTO:
        """Speak a complete text and return all of its audio. Raises EmptyText for blank text."""
