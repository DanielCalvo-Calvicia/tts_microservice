"""The droid effect chain and the resampling it relies on: pure numpy, no voice model."""

import numpy as np
import pytest

from infrastructure.outbound.piper_speech import droid_voice

RATE = 24000


def _speechlike(seconds: float = 0.5) -> np.ndarray:
    time = np.arange(int(RATE * seconds)) / RATE
    wave = 0.4 * np.sin(2 * np.pi * 180 * time) + 0.2 * np.sin(2 * np.pi * 900 * time)
    return wave.astype(np.float32)


def _tone_hz(samples: np.ndarray, rate: int) -> float:
    return float(np.argmax(np.abs(np.fft.rfft(samples))) * rate / len(samples))


def test_zero_strength_returns_the_voice_untouched():
    samples = _speechlike()

    assert droid_voice.droid_effect(samples, RATE, 0.0) is samples


def test_effect_changes_the_sound_but_keeps_length_and_never_gets_louder_or_clips():
    samples = _speechlike()

    out = droid_voice.droid_effect(samples, RATE, 1.0)

    assert out.shape == samples.shape and out.dtype == np.float32
    assert not np.allclose(out, samples)
    assert np.max(np.abs(out)) <= np.max(np.abs(samples)) + 1e-6
    assert np.max(np.abs(out)) <= 0.9 + 1e-6


def test_effect_adds_brightness():
    samples = _speechlike()

    def high_band_share(signal: np.ndarray) -> float:
        spectrum = np.abs(np.fft.rfft(signal))
        frequencies = np.fft.rfftfreq(len(signal), 1 / RATE)
        return float(np.sum(spectrum[frequencies > 2500] ** 2) / np.sum(spectrum**2))

    assert high_band_share(droid_voice.droid_effect(samples, RATE, 1.0)) > high_band_share(samples)


def test_effect_keeps_silence_silent_and_survives_empty_and_very_short_input():
    assert not np.any(droid_voice.droid_effect(np.zeros(500, dtype=np.float32), RATE, 1.0))
    assert droid_voice.droid_effect(np.zeros(0, dtype=np.float32), RATE, 1.0).size == 0
    assert droid_voice.droid_effect(np.array([0.5], dtype=np.float32), RATE, 1.0).shape == (1,)


def test_stronger_effect_moves_further_from_the_original():
    samples = _speechlike()

    light = np.linalg.norm(droid_voice.droid_effect(samples, RATE, 0.3) - samples)
    heavy = np.linalg.norm(droid_voice.droid_effect(samples, RATE, 1.5) - samples)

    assert heavy > light


def test_resample_scales_the_length_and_keeps_the_tone():
    time = np.arange(22050) / 22050
    tone = np.sin(2 * np.pi * 440 * time).astype(np.float32)

    out = droid_voice.resample(tone, 22050, RATE)

    assert abs(len(out) - RATE) <= 1
    assert _tone_hz(out, RATE) == pytest.approx(440, abs=2)


def test_pitch_lift_is_reading_the_samples_back_faster():
    ratio = droid_voice.semitones_to_ratio(12)
    time = np.arange(22050) / 22050
    tone = np.sin(2 * np.pi * 440 * time).astype(np.float32)

    out = droid_voice.resample(tone, 22050 * ratio, RATE)

    assert ratio == pytest.approx(2.0)
    assert _tone_hz(out, RATE) == pytest.approx(880, abs=4)


def test_resample_down_removes_what_the_new_rate_cannot_carry():
    time = np.arange(48000) / 48000
    tone = np.sin(2 * np.pi * 11000 * time).astype(np.float32)  # above the 8 kHz limit of 16 kHz

    out = droid_voice.resample(tone, 48000, 16000)

    assert np.max(np.abs(out[200:-200])) < 0.05  # the first and last samples are the filter's edge


def test_to_pcm16_clips_and_is_little_endian():
    pcm = droid_voice.to_pcm16(np.array([0.0, 1.0, -1.0, 2.0, -2.0], dtype=np.float32))

    assert np.frombuffer(pcm, dtype="<i2").tolist() == [0, 32767, -32767, 32767, -32767]
