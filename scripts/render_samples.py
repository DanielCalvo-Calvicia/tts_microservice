r"""Renders listening samples of the droid voice into models/samples/ (git-ignored). Manual script, not a test.

    windows\Scripts\python.exe scripts\render_samples.py
"""

import asyncio
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from infrastructure.outbound.piper_speech.piper_engine import PiperEngine  # noqa: E402
from infrastructure.outbound.piper_speech.piper_speech_synthesis import PiperSpeechSynthesis  # noqa: E402
from domain.value_objects.audio_format import AudioFormat  # noqa: E402

TEXT = (
    "Good evening, sir. I am fluent in over six million forms of communication. "
    "Oh dear, I do hope the arm movements will not be too much trouble."
)
OUT = ROOT / "models" / "samples"
FORMAT = AudioFormat(sample_rate=24000, channels=1)
VARIANTS = {
    "1_plain_alan": dict(pitch_semitones=0.0, effect_strength=0.0),
    "2_pitch_only": dict(pitch_semitones=2.0, effect_strength=0.0),
    "3_default_droid": dict(pitch_semitones=2.0, effect_strength=0.5),
    "4_strong_droid": dict(pitch_semitones=3.0, effect_strength=1.0),
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    engine = PiperEngine.load(ROOT / "models", "en_GB-alan-medium")
    asyncio.run(_warm(engine))
    for name, options in VARIANTS.items():
        synthesis = PiperSpeechSynthesis(engine, speed=1.0, **options)
        start = time.perf_counter()
        pcm = asyncio.run(synthesis.synthesize(TEXT, FORMAT))
        took = time.perf_counter() - start
        seconds = len(pcm) / 2 / FORMAT.sample_rate
        with wave.open(str(OUT / f"{name}.wav"), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(FORMAT.sample_rate)
            wav.writeframes(pcm)
        print(f"{name}: {seconds:.1f}s of audio rendered in {took:.2f}s (x{seconds / took:.1f} real time)")


async def _warm(engine: PiperEngine) -> None:
    engine.synthesize("warm up", speed=1.0)


if __name__ == "__main__":
    main()
