"""Conversion between 16-bit little-endian PCM formats.

The synthesizer speaks in its own native format; the caller asked for a specific one and every
downstream service (Brain, Speaker) relies on receiving exactly that, so the conversion belongs to
the service that produces the audio.
"""

from array import array
from sys import byteorder

from domain.errors import InvalidAudioFormat

BYTES_PER_SAMPLE = 2


def convert_pcm16(
    pcm: bytes, *, src_rate: int, src_channels: int, dst_rate: int, dst_channels: int
) -> bytes:
    """Return ``pcm`` (interleaved int16) resampled to ``dst_rate`` and remixed to ``dst_channels``.

    Resampling is linear interpolation, which is plenty for speech. Channel changes duplicate a
    mono signal to every output channel and average all input channels down to mono first.
    """
    if min(src_rate, src_channels, dst_rate, dst_channels) <= 0:
        raise InvalidAudioFormat("sample rates and channel counts must be positive")
    if len(pcm) % (BYTES_PER_SAMPLE * src_channels):
        raise InvalidAudioFormat("PCM data is not a whole number of frames")
    if (src_rate, src_channels) == (dst_rate, dst_channels):
        return pcm

    samples = array("h")
    samples.frombytes(pcm)
    if byteorder == "big":
        samples.byteswap()

    channels = [samples[c::src_channels] for c in range(src_channels)]
    if src_channels != dst_channels:
        mono = channels[0] if src_channels == 1 else _average(channels)
        channels = [mono] * dst_channels
    if src_rate != dst_rate:
        channels = [_resample(channel, src_rate, dst_rate) for channel in channels]

    out = array("h", bytes(len(channels[0]) * dst_channels * BYTES_PER_SAMPLE))
    for index, channel in enumerate(channels):
        out[index::dst_channels] = channel
    if byteorder == "big":
        out.byteswap()
    return out.tobytes()


def _average(channels: list[array]) -> array:
    count = len(channels)
    return array("h", (sum(frame) // count for frame in zip(*channels, strict=True)))


def _resample(samples: array, src_rate: int, dst_rate: int) -> array:
    if not samples:
        return samples
    last = len(samples) - 1
    total = max(1, round(len(samples) * dst_rate / src_rate))
    step = src_rate / dst_rate
    out = array("h")
    for index in range(total):
        position = index * step
        left = min(int(position), last)
        fraction = position - left
        right = min(left + 1, last)
        out.append(round(samples[left] * (1 - fraction) + samples[right] * fraction))
    return out
