import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENGINES = ("piper", "pyttsx3")
SERVICE_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True, frozen=True)
class TtsConfig:
    speech_rate: int
    voice_name_preference: str
    engine: str = "piper"
    piper_voice: str = "en_GB-alan-medium"
    piper_model_dir: Path = SERVICE_ROOT / "models"
    piper_speed: float = 1.0
    pitch_semitones: float = 2.0
    droid_effect: float = 0.5

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "TtsConfig":
        engine = env.get("TTS_ENGINE", "piper").strip().lower()
        if engine not in ENGINES:
            raise ValueError(f"TTS_ENGINE must be one of {', '.join(ENGINES)}, not {engine!r}")
        model_dir = Path(env.get("TTS_PIPER_MODEL_DIR", "models"))
        speed = float(env.get("TTS_PIPER_SPEED", "1.0"))
        if speed <= 0:
            raise ValueError("TTS_PIPER_SPEED must be greater than 0")
        effect = float(env.get("TTS_DROID_EFFECT", "0.5"))
        if effect < 0:
            raise ValueError("TTS_DROID_EFFECT must be 0 (off) or more")
        return cls(
            speech_rate=int(env.get("TTS_SPEECH_RATE", "140")),
            voice_name_preference=env.get("TTS_VOICE_NAME", "Zira"),
            engine=engine,
            piper_voice=env.get("TTS_PIPER_VOICE", "en_GB-alan-medium"),
            # A relative folder is relative to the service, not to wherever it was started from.
            piper_model_dir=model_dir if model_dir.is_absolute() else SERVICE_ROOT / model_dir,
            piper_speed=speed,
            pitch_semitones=float(env.get("TTS_PITCH_SEMITONES", "2.0")),
            droid_effect=effect,
        )
