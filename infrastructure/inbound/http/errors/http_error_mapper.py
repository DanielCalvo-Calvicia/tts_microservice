from fastapi import status

from application.errors import AudioFormatMismatch, SynthesisFailed
from domain.errors import EmptyText, InvalidAudioFormat


def map_error(error: Exception) -> int:
    """Translate an application/domain error into an HTTP status code.

    400  no text to speak
    422  the requested audio format is invalid or contradicts the stream's
    502  the speech engine failed
    500  anything else
    """
    if isinstance(error, EmptyText):
        return status.HTTP_400_BAD_REQUEST
    if isinstance(error, (InvalidAudioFormat, AudioFormatMismatch)):
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    if isinstance(error, SynthesisFailed):
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_500_INTERNAL_SERVER_ERROR
