from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AudioBatchOutboundDTO:
    """The complete synthesized PCM buffer."""

    audio_data: bytes
