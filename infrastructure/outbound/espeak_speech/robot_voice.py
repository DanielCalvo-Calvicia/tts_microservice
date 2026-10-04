"""The "machine" colouring of a formant voice: ring modulation, sample-and-hold and bit crushing.

espeak is already synthetic; these three make it unmistakably electronic: a low carrier chops the voice into the
buzzing, metallic tone of a vocoder, the hold drops the effective sample rate (digital grit) and the crush removes
amplitude detail. Vectorised numpy; mono float32 samples in -1..1; knows nothing about espeak.
"""

import numpy as np

_CARRIER_HZ = 55.0  # low enough to buzz, high enough to stay clear of the pitch of the voice
_RING_MIX = 0.3  # share of ring-modulated sound at strength 1 (capped at _MAX_RING_MIX)
_MAX_RING_MIX = 0.9
_MAX_STRENGTH = 3.0
_PEAK = 0.9  # the loudest sample after the chain; the chain never gets louder than the input did


def robot_effect(samples: np.ndarray, rate: int, strength: float) -> np.ndarray:
    """Make the voice electronic. ``strength`` 0 returns the input unchanged, 1 is the usual setting, 3 the most."""
    if strength <= 0 or len(samples) == 0:
        return samples
    strength = min(strength, _MAX_STRENGTH)
    original_peak = float(np.max(np.abs(samples)))
    if original_peak == 0.0:
        return samples

    time = np.arange(len(samples), dtype=np.float32) / rate
    mix = min(_RING_MIX * strength, _MAX_RING_MIX)
    out = (1.0 - mix) * samples + mix * samples * np.sin(2.0 * np.pi * _CARRIER_HZ * time)

    hold = 1 + int(strength)  # 2 samples at strength 1, up to 4: each value is kept for `hold` samples
    out = np.repeat(out[::hold], hold)[: len(out)]

    bits = max(4, round(10 - 2 * strength))  # 8 bits at strength 1, 4 at the maximum
    levels = float(2 ** (bits - 1))
    out = np.round(out * levels) / levels

    peak = float(np.max(np.abs(out)))
    if peak > 0.0:
        out = out * (min(original_peak, _PEAK) / peak)
    return out.astype(np.float32)
