"""The only module that knows how Piper is driven: loads one voice and turns text into float samples.

Piper is imported here, lazily, so the service still starts (on the pyttsx3 engine) where it is not installed.
"""

import threading
from pathlib import Path

import numpy as np
from shared_logging import get_logger

from application.errors import SynthesisFailed

logger = get_logger(__name__)


class PiperEngine:
    def __init__(self, voice: object, voice_name: str) -> None:
        self._voice = voice
        self._voice_name = voice_name
        self._lock = threading.Lock()  # one ONNX session: a sentence at a time

    @classmethod
    def load(cls, model_dir: Path, voice_name: str) -> "PiperEngine":
        """Load ``<model_dir>/<voice_name>.onnx`` (and its ``.onnx.json``). Raises SynthesisFailed."""
        model = model_dir / f"{voice_name}.onnx"
        if not model.is_file() or not (model_dir / f"{voice_name}.onnx.json").is_file():
            raise SynthesisFailed(
                f"Piper voice {voice_name!r} is not in {model_dir} "
                "(fetch it with: python scripts/fetch_voice.py from the service folder, or deploy again)"
            )
        try:
            from piper import PiperVoice  # noqa: PLC0415 (lazy on purpose, see the module docstring)

            voice = PiperVoice.load(model)
        except Exception as error:  # a missing package, a corrupt model, an unusable runtime
            raise SynthesisFailed(f"Piper could not load {model}: {error}") from error
        logger.info("Piper voice loaded", voice=voice_name, sample_rate=voice.config.sample_rate)  # type: ignore[attr-defined]
        return cls(voice, voice_name)

    @property
    def sample_rate(self) -> int:
        return int(self._voice.config.sample_rate)  # type: ignore[attr-defined]

    def synthesize(self, text: str, speed: float) -> np.ndarray:
        """The speech as mono float32 samples at ``sample_rate``. ``speed`` > 1 talks faster."""
        from piper import SynthesisConfig  # noqa: PLC0415

        base = float(self._voice.config.length_scale or 1.0)  # type: ignore[attr-defined]
        config = SynthesisConfig(length_scale=base / speed)
        with self._lock:
            chunks = [
                chunk.audio_float_array
                for chunk in self._voice.synthesize(text, syn_config=config)  # type: ignore[attr-defined]
            ]
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32)
