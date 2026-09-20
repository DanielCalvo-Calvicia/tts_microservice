from domain.errors import EmptyText


def is_speakable(text: str) -> bool:
    """True if ``text`` has anything to say (not empty, not only whitespace)."""
    return bool(text.strip())


def require_speakable(text: str) -> str:
    """Return ``text`` unchanged, or raise EmptyText if there is nothing to say."""
    if not is_speakable(text):
        raise EmptyText("No text provided")
    return text
