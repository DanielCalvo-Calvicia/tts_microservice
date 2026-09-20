import array
import math

import pytest

from domain.errors import InvalidAudioFormat
from domain.operations.pcm import convert_pcm16


def _pcm(*samples: int) -> bytes:
    return array.array("h", samples).tobytes()


def _samples(pcm: bytes) -> list[int]:
    out = array.array("h")
    out.frombytes(pcm)
    return list(out)


def test_same_format_is_returned_untouched():
    pcm = _pcm(1, 2, 3)
    assert convert_pcm16(pcm, src_rate=24000, src_channels=1, dst_rate=24000, dst_channels=1) is pcm


def test_resampling_scales_the_duration_by_the_rate_ratio():
    one_second = _pcm(*([1000] * 22050))
    out = convert_pcm16(one_second, src_rate=22050, src_channels=1, dst_rate=24000, dst_channels=1)
    assert len(out) // 2 == 24000
    assert set(_samples(out)) == {1000}  # a constant signal stays constant


def test_resampling_keeps_the_pitch_of_a_tone():
    rate_in, rate_out, frequency = 22050, 16000, 440
    tone = _pcm(*[round(10000 * math.sin(2 * math.pi * frequency * n / rate_in)) for n in range(rate_in)])

    out = _samples(convert_pcm16(tone, src_rate=rate_in, src_channels=1, dst_rate=rate_out, dst_channels=1))

    crossings = sum(1 for a, b in zip(out, out[1:], strict=False) if a < 0 <= b)
    assert abs(crossings - frequency) <= 2  # ~440 cycles in the second, whatever the rate


def test_mono_is_duplicated_to_stereo_and_stereo_is_averaged_to_mono():
    stereo = convert_pcm16(_pcm(10, 20), src_rate=8000, src_channels=1, dst_rate=8000, dst_channels=2)
    assert _samples(stereo) == [10, 10, 20, 20]
    mono = convert_pcm16(_pcm(10, 30, 20, 40), src_rate=8000, src_channels=2, dst_rate=8000, dst_channels=1)
    assert _samples(mono) == [20, 30]


def test_empty_audio_and_invalid_input():
    assert convert_pcm16(b"", src_rate=8000, src_channels=1, dst_rate=16000, dst_channels=1) == b""
    with pytest.raises(InvalidAudioFormat):
        convert_pcm16(b"\x00", src_rate=8000, src_channels=1, dst_rate=16000, dst_channels=1)
    with pytest.raises(InvalidAudioFormat):
        convert_pcm16(_pcm(1), src_rate=0, src_channels=1, dst_rate=16000, dst_channels=1)
