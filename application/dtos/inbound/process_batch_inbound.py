from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProcessBatchInboundDTO:
    """A complete text to synthesize in one go."""

    text: str
    sample_rate: int = 22050
    channels: int = 1
