class ApplicationError(Exception):
    """Base class for failures of a use case that are not business-rule violations."""


class SynthesisFailed(ApplicationError, RuntimeError):
    """The speech engine could not produce audio for a piece of text."""


class AudioFormatMismatch(ApplicationError, ValueError):
    """A request names an audio format that differs from the one the stream was set with."""
