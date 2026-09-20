import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TtsConfig:
    speech_rate: int
    voice_name_preference: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "TtsConfig":
        return cls(
            speech_rate=int(env.get("TTS_SPEECH_RATE", "140")),
            voice_name_preference=env.get("TTS_VOICE_NAME", "Zira"),
        )
