"""The only module that knows how espeak is driven: one process per sentence, WAV in, float samples out.

espeak (or espeak-ng, same command line) is a formant synthesizer: the sound is computed from rules, not cut from
a recording of a person, which is what makes it sound like a machine. It is run as a subprocess so the service
starts (on another engine) where it is not installed.
"""

import shutil
import struct
import subprocess

import numpy as np
from shared_logging import get_logger

from application.errors import SynthesisFailed

logger = get_logger(__name__)

COMMANDS = ("espeak-ng", "espeak")  # the first one installed wins when none is named
MIN_WORDS_PER_MINUTE = 80
MAX_WORDS_PER_MINUTE = 390
_TIMEOUT_SECONDS = 30
_UNKNOWN_SIZES = (0, 0x7FFFFFFF, 0xFFFFFFFF)  # a WAV written to a pipe cannot know its length


def find_command(name: str) -> str | None:
    """The path of the named espeak program, or of the first installed one when ``name`` is empty."""
    for candidate in (name,) if name else COMMANDS:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def parse_wav(blob: bytes) -> tuple[int, np.ndarray]:
    """(sample rate, mono float32 samples) of a PCM16 mono WAV. Raises ValueError."""
    if len(blob) < 12 or blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
        raise ValueError("espeak did not write a WAV file")
    rate = channels = bits = 0
    position = 12
    while position + 8 <= len(blob):
        chunk_id = blob[position : position + 4]
        (size,) = struct.unpack_from("<I", blob, position + 4)
        body = position + 8
        if chunk_id == b"fmt ":
            _, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", blob, body)
        elif chunk_id == b"data":
            if (channels, bits) != (1, 16) or rate <= 0:
                raise ValueError(f"expected mono 16-bit audio, got {channels} channel(s) of {bits} bits")
            end = len(blob) if size in _UNKNOWN_SIZES else min(len(blob), body + size)
            pcm = blob[body : end - ((end - body) % 2)]
            return rate, np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        position = body + size + (size % 2)
    raise ValueError("the WAV file has no audio")


class EspeakEngine:
    def __init__(
        self,
        command: str,
        sample_rate: int,
        *,
        voice: str,
        words_per_minute: int,
        pitch: int,
        word_gap_ms: int,
    ) -> None:
        self._command = command
        self._sample_rate = sample_rate
        self._voice = voice
        self._words_per_minute = words_per_minute
        self._pitch = pitch
        self._word_gap = max(0, round(word_gap_ms / 10))  # espeak counts the gap in units of 10 ms

    @classmethod
    def load(
        cls,
        command_name: str,
        *,
        voice: str,
        words_per_minute: int,
        pitch: int,
        word_gap_ms: int,
    ) -> "EspeakEngine":
        """Find espeak and prove it speaks (a probe sentence also tells the sample rate). Raises SynthesisFailed."""
        command = find_command(command_name)
        if command is None:
            wanted = command_name or " or ".join(COMMANDS)
            raise SynthesisFailed(
                f"{wanted} is not installed (Debian/Raspberry Pi OS: sudo apt install espeak-ng, or espeak)"
            )
        engine = cls(
            command,
            0,
            voice=voice,
            words_per_minute=words_per_minute,
            pitch=pitch,
            word_gap_ms=word_gap_ms,
        )
        try:
            rate, _ = engine._run("ready", words_per_minute)
        except SynthesisFailed:
            raise
        except Exception as error:
            raise SynthesisFailed(f"{command} could not speak a test sentence: {error}") from error
        engine._sample_rate = rate
        logger.info("espeak ready", command=command, voice=voice, sample_rate=rate)
        return engine

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def synthesize(self, text: str, speed: float) -> np.ndarray:
        """The speech as mono float32 samples at ``sample_rate``. ``speed`` > 1 talks faster."""
        rate = round(self._words_per_minute * speed)
        _, samples = self._run(text, min(MAX_WORDS_PER_MINUTE, max(MIN_WORDS_PER_MINUTE, rate)))
        return samples

    def _run(self, text: str, words_per_minute: int) -> tuple[int, np.ndarray]:
        arguments = [
            self._command,
            "--stdin",  # the text never touches the command line: no quoting, no "-" mistaken for an option
            "--stdout",
            "-v",
            self._voice,
            "-s",
            str(words_per_minute),
            "-p",
            str(self._pitch),
            "-g",
            str(self._word_gap),
        ]
        try:
            done = subprocess.run(  # noqa: S603 (the program is a resolved path, the text goes through stdin)
                arguments,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SynthesisFailed(f"{self._command} did not run: {error}") from error
        if done.returncode != 0:
            detail = done.stderr.decode("utf-8", errors="replace").strip()[:200]
            raise SynthesisFailed(f"{self._command} failed with code {done.returncode}: {detail}")
        try:
            return parse_wav(done.stdout)
        except ValueError as error:
            raise SynthesisFailed(f"{self._command} gave unusable audio: {error}") from error
