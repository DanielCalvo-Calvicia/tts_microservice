"""The "droid" colouring of a voice: a pitch lift (by resampling) and a light metallic effect chain.

Everything is vectorised numpy so a Raspberry Pi renders a sentence faster than it takes to say it.
The functions work on mono float32 samples in -1..1 and know nothing about Piper.
"""

import numpy as np

_SHELF_CUTOFF_HZ = 2500.0
_SHELF_GAIN = 0.9  # presence boost above the cutoff at strength 1
_COMB_DELAYS_SECONDS = (0.0045, 0.0097)  # the short echoes that make the sound "tin"
_COMB_GAINS = (0.38, 0.2)  # at strength 1
_RING_HZ = 140.0
_RING_MIX = 0.12  # at strength 1
_PEAK = 0.9  # the loudest sample after the chain; the chain never gets louder than the input did


def semitones_to_ratio(semitones: float) -> float:
    return float(2.0 ** (semitones / 12.0))


def resample(samples: np.ndarray, src_rate: float, dst_rate: int) -> np.ndarray:
    """Linear resampling to ``dst_rate``. A band limit is applied first when the rate goes down."""
    if len(samples) == 0 or src_rate == dst_rate:
        return samples
    if dst_rate < src_rate:
        samples = _lowpass(samples, cutoff_hz=0.45 * dst_rate, rate=src_rate)
    total = max(1, round(len(samples) * dst_rate / src_rate))
    positions = np.arange(total) * (src_rate / dst_rate)
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)


def droid_effect(samples: np.ndarray, rate: int, strength: float) -> np.ndarray:
    """Make the voice clean, bright and slightly metallic. ``strength`` 0 returns the input unchanged."""
    if strength <= 0 or len(samples) == 0:
        return samples
    strength = min(strength, 2.0)
    original_peak = float(np.max(np.abs(samples)))
    if original_peak == 0.0:
        return samples

    bright = samples + _SHELF_GAIN * strength * (
        samples - _lowpass(samples, cutoff_hz=_SHELF_CUTOFF_HZ, rate=rate)
    )
    out = bright.copy()
    for delay_seconds, gain in zip(_COMB_DELAYS_SECONDS, _COMB_GAINS, strict=True):
        delay = max(1, round(delay_seconds * rate))
        if delay < len(bright):
            out[delay:] += gain * strength * bright[:-delay]
    time = np.arange(len(out), dtype=np.float32) / rate
    mix = min(_RING_MIX * strength, 0.5)
    out = (1.0 - mix) * out + mix * out * np.sin(2.0 * np.pi * _RING_HZ * time)

    peak = float(np.max(np.abs(out)))
    target = min(original_peak, _PEAK)
    if peak > 0.0:
        out = out * (target / peak)
    return out.astype(np.float32)


def to_pcm16(samples: np.ndarray) -> bytes:
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def _lowpass(samples: np.ndarray, cutoff_hz: float, rate: float, taps: int = 63) -> np.ndarray:
    """Windowed-sinc low-pass; the output has the same length and no delay."""
    centre = (taps - 1) / 2
    n = np.arange(taps) - centre
    kernel = np.sinc(2.0 * cutoff_hz / rate * n) * np.hamming(taps)
    kernel /= kernel.sum()
    # "same" would return the longer of the two when the sound is shorter than the filter
    padded = np.pad(samples, taps // 2)
    return np.convolve(padded, kernel, mode="valid").astype(np.float32)
