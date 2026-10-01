r"""Makes sure the configured Piper voice is on disk. Run by the deployment tool after it writes the .env.

    windows\Scripts\python.exe scripts\fetch_voice.py              # the voice the .env / environment asks for
    windows\Scripts\python.exe scripts\fetch_voice.py --voice en_GB-alan-medium

It reads the same settings as the service (TTS_ENGINE, TTS_PIPER_VOICE, TTS_PIPER_MODEL_DIR), does nothing when
the engine is not piper or the voice is already usable, and otherwise downloads it into a temporary folder,
loads it once to prove it is intact, and only then moves it into place, so an interrupted download never leaves
a half voice behind. Exit code 0 = the voice is ready (or not needed), 1 = it could not be fetched.
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from infrastructure.config.tts_config import TtsConfig  # noqa: E402


def voice_is_usable(model_dir: Path, voice: str) -> bool:
    from piper import PiperVoice  # noqa: PLC0415

    model = model_dir / f"{voice}.onnx"
    if not model.is_file() or not (model_dir / f"{voice}.onnx.json").is_file():
        return False
    try:
        PiperVoice.load(model)
    except Exception:
        return False
    return True


def fetch(model_dir: Path, voice: str) -> None:
    from piper.download_voices import download_voice  # noqa: PLC0415

    model_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=model_dir, prefix=".fetch-") as scratch:
        scratch_dir = Path(scratch)
        download_voice(voice, scratch_dir)
        if not voice_is_usable(scratch_dir, voice):
            raise RuntimeError(f"the downloaded voice {voice} does not load")
        for suffix in (".onnx", ".onnx.json"):  # the config last: a model without it is "not there"
            os.replace(scratch_dir / f"{voice}{suffix}", model_dir / f"{voice}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--voice", help="voice name; default TTS_PIPER_VOICE")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")  # like the service: a real environment variable wins over the file
    cfg = TtsConfig.from_env()
    voice = args.voice or cfg.piper_voice
    if cfg.engine != "piper" and not args.voice:
        print(f"TTS_ENGINE is {cfg.engine}: no Piper voice needed")
        return 0
    if voice_is_usable(cfg.piper_model_dir, voice):
        print(f"Piper voice {voice} is ready in {cfg.piper_model_dir}")
        return 0
    print(f"Fetching Piper voice {voice} into {cfg.piper_model_dir} (about 60 MB)")
    try:
        fetch(cfg.piper_model_dir, voice)
    except Exception as error:  # no network, a mistyped voice name, a full disk
        print(f"Could not fetch Piper voice {voice}: {error}", file=sys.stderr)
        print("The service will start with the pyttsx3 voice until it is there.", file=sys.stderr)
        return 1
    print(f"Piper voice {voice} is ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
