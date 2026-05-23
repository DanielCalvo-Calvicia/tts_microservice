from dataclasses import dataclass
from typing import AsyncIterator


# ──────────────────────────────────────────────
# STREAM (Real-time)
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class ProcessStreamRequestDto:
    """Service-layer request for streaming text to speech."""
    text_stream: AsyncIterator[str]
    sample_rate: int = 22050
    channels: int = 1


@dataclass(slots=True, frozen=True)
class ProcessStreamResponseDto:
    """Service-layer response containing a real-time synthesized audio stream."""
    audio_stream: AsyncIterator[bytes]


# ──────────────────────────────────────────────
# DECOUPLED STREAM (Single Flow)
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class SetStreamRequestDto:
    """Service-layer request to set the input text stream for background synthesis."""
    text_stream: AsyncIterator[str]
    sample_rate: int = 22050
    channels: int = 1


@dataclass(slots=True, frozen=True)
class GetStreamRequestDto:
    """Service-layer request to retrieve the active synthesized audio stream."""
    pass


@dataclass(slots=True, frozen=True)
class GetStreamResponseDto:
    """Service-layer response containing the active synthesized audio stream."""
    audio_stream: AsyncIterator[bytes]



# ──────────────────────────────────────────────
# BATCH (Non real-time)
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class ProcessBatchRequestDto:
    """Service-layer request to synthesize a complete text string."""
    text: str
    sample_rate: int = 22050
    channels: int = 1


@dataclass(slots=True, frozen=True)
class ProcessBatchResponseDto:
    """Service-layer response containing the full synthesized audio buffer."""
    audio_data: bytes


# ──────────────────────────────────────────────
# AVAILABILITY
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class TTSAvailabilityRequestDto:
    pass


@dataclass(slots=True, frozen=True)
class TTSAvailabilityResponseDto:
    is_available: bool
