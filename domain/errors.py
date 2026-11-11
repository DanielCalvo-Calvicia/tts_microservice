"""Domain errors.

They also inherit from the matching builtin exception so that callers written
against the pre-refactor behaviour (``ValueError``) keep working.
"""


class DomainError(Exception):
    """Base class for every business-rule violation raised by the domain."""


class InvalidAudioFormat(DomainError, ValueError):
    """The requested audio format violates an invariant (e.g. non-positive sample rate)."""


class EmptyText(DomainError, ValueError):
    """There is nothing to say: the text is empty or only whitespace."""
