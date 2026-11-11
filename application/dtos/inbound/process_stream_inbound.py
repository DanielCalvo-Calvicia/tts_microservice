from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProcessStreamInboundDTO:
    """Carries a stream of texts to speak, and the audio format wanted, into the application."""

    text_stream: AsyncIterator[str]
    sample_rate: int = 22050
    channels: int = 1
