from dataclasses import dataclass

from domain.errors import InvalidAudioFormat


@dataclass(slots=True, frozen=True)
class AudioFormat:
    """The PCM (16-bit) format a client asks for: how fast and how many channels.

    Invariant: every field is strictly positive.
    """

    sample_rate: int = 22050
    channels: int = 1

    def __post_init__(self) -> None:
        if self.sample_rate <= 0 or self.channels <= 0:
            raise InvalidAudioFormat("sample_rate and channels must be positive")
