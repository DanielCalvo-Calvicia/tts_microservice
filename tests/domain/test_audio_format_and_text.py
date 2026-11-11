import pytest

from domain.errors import EmptyText, InvalidAudioFormat
from domain.operations.text import is_speakable, require_speakable
from domain.value_objects.audio_format import AudioFormat


def test_defaults_are_22050_mono():
    fmt = AudioFormat()
    assert (fmt.sample_rate, fmt.channels) == (22050, 1)


@pytest.mark.parametrize("kwargs", [{"sample_rate": 0}, {"sample_rate": -1}, {"channels": 0}])
def test_non_positive_values_are_rejected(kwargs):
    with pytest.raises(InvalidAudioFormat):
        AudioFormat(**kwargs)


def test_invalid_format_is_still_a_value_error():
    with pytest.raises(ValueError):
        AudioFormat(channels=0)


@pytest.mark.parametrize("text", ["", " ", "\n\t  "])
def test_blank_text_is_not_speakable(text):
    assert is_speakable(text) is False
    with pytest.raises(EmptyText, match="No text provided"):
        require_speakable(text)


def test_text_with_content_is_speakable_and_returned_unchanged():
    assert is_speakable(" hi ") is True
    assert require_speakable(" hi ") == " hi "


def test_empty_text_is_still_a_value_error():
    assert issubclass(EmptyText, ValueError)
