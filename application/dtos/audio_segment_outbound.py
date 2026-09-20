from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AudioChunk:
    """A piece of the PCM audio of the text being spoken."""

    data: bytes


@dataclass(slots=True, frozen=True)
class SegmentCompleted:
    """All the audio of one text has been delivered."""

    text: str


@dataclass(slots=True, frozen=True)
class SegmentFailed:
    """One text could not be spoken; the following texts are still spoken."""

    message: str


@dataclass(slots=True, frozen=True)
class StreamFormat:
    """First item of every audio stream: the PCM16 format its chunks are in."""

    sample_rate: int
    channels: int


AudioSegmentEvent = StreamFormat | AudioChunk | SegmentCompleted | SegmentFailed


@dataclass(slots=True, frozen=True)
class AudioSegmentStreamOutboundDTO:
    """The shared audio stream with segment boundaries, handed back to an inbound adapter."""

    events: AsyncIterator[AudioSegmentEvent]
