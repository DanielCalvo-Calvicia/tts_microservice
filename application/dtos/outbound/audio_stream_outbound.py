from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AudioStreamOutboundDTO:
    """A live stream of PCM chunks handed back to an inbound adapter."""

    audio_stream: AsyncIterator[bytes]
