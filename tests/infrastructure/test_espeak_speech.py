"""The espeak engine against a fake process, the robot effect, and the adapter: no espeak install needed."""

import asyncio
import struct
import subprocess
from collections.abc import AsyncIterator

import numpy as np
import pytest

from application.errors import SynthesisFailed
from domain.value_objects.audio_format import AudioFormat
from infrastructure.outbound.espeak_speech import espeak_engine
from infrastructure.outbound.espeak_speech.espeak_engine import EspeakEngine, parse_wav
from infrastructure.outbound.espeak_speech.espeak_speech_synthesis import EspeakSpeechSynthesis
from infrastructure.outbound.espeak_speech.robot_voice import robot_effect

FORMAT = AudioFormat(sample_rate=24000, channels=1)
RATE = 22050


def _wav(samples: np.ndarray, rate: int = RATE, *, declared_size: int | None = None, channels: int = 1) -> bytes:
    """A WAV as espeak writes it to a pipe when ``declared_size`` is 0xFFFFFFFF (length unknown)."""
    pcm = (samples * 32767).astype("<i2").tobytes()
    size = len(pcm) if declared_size is None else declared_size
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * 2 * channels, 2 * channels, 16)
    return header + b"data" + struct.pack("<I", size) + pcm


def _tone(seconds: float = 1.0, hertz: float = 200.0, rate: int = RATE) -> np.ndarray:
    time = np.arange(int(seconds * rate)) / rate
    return (0.5 * np.sin(2 * np.pi * hertz * time)).astype(np.float32)


class FakeProcess:
    """Stands in for subprocess.run: records the call and answers with a tone, or with what it is told."""

    def __init__(self, stdout: bytes | None = None, returncode: int = 0, error: Exception | None = None) -> None:
        self.stdout = _wav(_tone()) if stdout is None else stdout
        self.returncode = returncode
        self.error = error
        self.calls: list[tuple[list[str], bytes]] = []

    def __call__(self, arguments, *, input, **_):  # noqa: A002 (the name subprocess.run uses)
        self.calls.append((arguments, input))
        if self.error:
            raise self.error
        return subprocess.CompletedProcess(arguments, self.returncode, self.stdout, b"boom")


def _engine(monkeypatch, process: FakeProcess, **overrides) -> EspeakEngine:
    monkeypatch.setattr(espeak_engine.subprocess, "run", process)
    monkeypatch.setattr(espeak_engine.shutil, "which", lambda name: f"/usr/bin/{name}")
    options = dict(voice="en", words_per_minute=150, pitch=30, word_gap_ms=20) | overrides
    return EspeakEngine.load("espeak", **options)


# --- WAV parsing ---------------------------------------------------------------------------------------------


def test_parse_wav_reads_rate_and_samples():
    rate, samples = parse_wav(_wav(_tone(0.1)))

    assert rate == RATE
    assert len(samples) == int(0.1 * RATE)
    assert abs(float(np.max(samples)) - 0.5) < 0.01


@pytest.mark.parametrize("declared", [0, 0x7FFFFFFF, 0xFFFFFFFF])
def test_parse_wav_accepts_the_unknown_length_espeak_writes_to_a_pipe(declared):
    _, samples = parse_wav(_wav(_tone(0.1), declared_size=declared))

    assert len(samples) == int(0.1 * RATE)


def test_parse_wav_rejects_what_is_not_a_wav():
    with pytest.raises(ValueError, match="WAV"):
        parse_wav(b"not audio at all")


def test_parse_wav_rejects_stereo():
    with pytest.raises(ValueError, match="mono"):
        parse_wav(_wav(_tone(0.1), channels=2))


# --- the engine ------------------------------------------------------------------------------------------------


def test_load_probes_espeak_and_learns_the_sample_rate(monkeypatch):
    process = FakeProcess(_wav(_tone(0.1, rate=16000), rate=16000))

    engine = _engine(monkeypatch, process)

    assert engine.sample_rate == 16000
    assert len(process.calls) == 1


def test_load_without_espeak_installed_raises_synthesis_failed(monkeypatch):
    monkeypatch.setattr(espeak_engine.shutil, "which", lambda name: None)

    with pytest.raises(SynthesisFailed, match="not installed"):
        EspeakEngine.load("", voice="en", words_per_minute=150, pitch=30, word_gap_ms=0)


def test_an_empty_command_name_tries_espeak_ng_then_espeak(monkeypatch):
    asked: list[str] = []

    def which(name):
        asked.append(name)
        return "/usr/bin/espeak" if name == "espeak" else None

    monkeypatch.setattr(espeak_engine.shutil, "which", which)
    monkeypatch.setattr(espeak_engine.subprocess, "run", FakeProcess())

    EspeakEngine.load("", voice="en", words_per_minute=150, pitch=30, word_gap_ms=0)

    assert asked == ["espeak-ng", "espeak"]


def test_text_goes_through_stdin_and_never_onto_the_command_line(monkeypatch):
    process = FakeProcess()
    engine = _engine(monkeypatch, process)

    engine.synthesize("-rm -rf; héllo", speed=1.0)

    arguments, text = process.calls[-1]
    assert text == "-rm -rf; héllo".encode()
    assert "--stdin" in arguments and "--stdout" in arguments
    assert not any("rm" in argument for argument in arguments)


def test_voice_pitch_gap_and_speed_reach_the_command_line(monkeypatch):
    process = FakeProcess()
    engine = _engine(monkeypatch, process, voice="en+klatt3", pitch=12, word_gap_ms=40, words_per_minute=100)

    engine.synthesize("hello", speed=2.0)

    arguments, _ = process.calls[-1]
    assert arguments[arguments.index("-v") + 1] == "en+klatt3"
    assert arguments[arguments.index("-p") + 1] == "12"
    assert arguments[arguments.index("-g") + 1] == "4"  # espeak counts the gap in 10 ms units
    assert arguments[arguments.index("-s") + 1] == "200"


@pytest.mark.parametrize(("speed", "expected"), [(0.1, "80"), (100.0, "390")])
def test_speed_is_kept_within_what_espeak_accepts(monkeypatch, speed, expected):
    process = FakeProcess()
    engine = _engine(monkeypatch, process)

    engine.synthesize("hello", speed=speed)

    arguments, _ = process.calls[-1]
    assert arguments[arguments.index("-s") + 1] == expected


def test_a_failing_process_raises_synthesis_failed(monkeypatch):
    engine = _engine(monkeypatch, FakeProcess())
    monkeypatch.setattr(espeak_engine.subprocess, "run", FakeProcess(returncode=1))

    with pytest.raises(SynthesisFailed, match="code 1"):
        engine.synthesize("hello", speed=1.0)


def test_a_timeout_raises_synthesis_failed(monkeypatch):
    engine = _engine(monkeypatch, FakeProcess())
    monkeypatch.setattr(
        espeak_engine.subprocess, "run", FakeProcess(error=subprocess.TimeoutExpired("espeak", 30))
    )

    with pytest.raises(SynthesisFailed, match="did not run"):
        engine.synthesize("hello", speed=1.0)


# --- the robot effect ------------------------------------------------------------------------------------------


def test_effect_strength_zero_returns_the_input_unchanged():
    samples = _tone()

    assert robot_effect(samples, RATE, 0.0) is samples


def test_effect_changes_the_sound_but_never_makes_it_louder():
    samples = _tone()

    out = robot_effect(samples, RATE, 1.0)

    assert out.shape == samples.shape
    assert not np.allclose(out, samples)
    assert float(np.max(np.abs(out))) <= float(np.max(np.abs(samples))) + 1e-6


def test_effect_crushes_the_amplitude_to_few_levels():
    out = robot_effect(_tone(), RATE, 1.0)

    assert len(np.unique(np.round(out / np.max(np.abs(out)), 4))) < 300


def test_a_stronger_effect_is_further_from_the_original():
    samples = _tone()

    light = robot_effect(samples, RATE, 0.5)
    strong = robot_effect(samples, RATE, 2.0)

    assert np.mean(np.abs(strong - samples)) > np.mean(np.abs(light - samples))


def test_effect_survives_silence_and_empty_input():
    assert np.all(robot_effect(np.zeros(100, dtype=np.float32), RATE, 1.0) == 0)
    assert len(robot_effect(np.zeros(0, dtype=np.float32), RATE, 1.0)) == 0


# --- the adapter -----------------------------------------------------------------------------------------------


class FakeSynth:
    sample_rate = RATE

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, float]] = []
        self.fail = fail

    def synthesize(self, text: str, speed: float) -> np.ndarray:
        self.calls.append((text, speed))
        if self.fail:
            raise RuntimeError("engine blew up")
        return _tone()


def _adapter(synth: FakeSynth, effect: float = 0.0) -> EspeakSpeechSynthesis:
    return EspeakSpeechSynthesis(synth, speed=1.0, effect_strength=effect)


async def _texts(*items: str) -> AsyncIterator[str]:
    for item in items:
        yield item


def test_batch_returns_one_second_of_pcm16_at_the_requested_rate():
    audio = asyncio.run(_adapter(FakeSynth()).synthesize("hello", FORMAT))

    assert abs(len(audio) - 24000 * 2) <= 4


def test_stereo_is_the_mono_signal_duplicated():
    audio = asyncio.run(_adapter(FakeSynth()).synthesize("hello", AudioFormat(24000, 2)))
    samples = np.frombuffer(audio, dtype="<i2")

    assert np.array_equal(samples[0::2], samples[1::2])


def test_the_robot_effect_is_applied_when_set():
    plain = asyncio.run(_adapter(FakeSynth(), effect=0.0).synthesize("hi", FORMAT))
    robot = asyncio.run(_adapter(FakeSynth(), effect=1.0).synthesize("hi", FORMAT))

    assert plain != robot
    assert len(plain) == len(robot)


def test_engine_errors_become_synthesis_failed():
    with pytest.raises(SynthesisFailed, match="espeak synthesis failed"):
        asyncio.run(_adapter(FakeSynth(fail=True)).synthesize("hello", FORMAT))


def test_stream_speaks_every_text_and_yields_chunks():
    synth = FakeSynth()

    async def collect() -> list[bytes]:
        return [c async for c in _adapter(synth).synthesize_stream(_texts("one", "two"), FORMAT)]

    chunks = asyncio.run(collect())

    assert [call[0] for call in synth.calls] == ["one", "two"]
    assert len(chunks) > 2
    assert sum(len(c) for c in chunks) >= 2 * 24000 * 2 - 8


def test_a_failing_sentence_ends_the_stream_instead_of_raising():
    async def collect() -> list[bytes]:
        return [c async for c in _adapter(FakeSynth(fail=True)).synthesize_stream(_texts("x"), FORMAT)]

    assert asyncio.run(collect()) == []
