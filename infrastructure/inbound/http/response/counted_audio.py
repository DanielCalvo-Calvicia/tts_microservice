from collections.abc import AsyncIterator

from shared_logging import get_logger

logger = get_logger(__name__)


async def counted_audio(audio_stream: AsyncIterator[bytes], label: str) -> AsyncIterator[bytes]:
    """Passes the PCM chunks through and logs how many went out when the stream ends."""
    chunk_count = 0
    total_bytes = 0
    async for chunk in audio_stream:
        chunk_count += 1
        total_bytes += len(chunk)
        yield chunk
    logger.info(
        "Audio stream completed",
        label=label,
        chunk_count=chunk_count,
        total_bytes=total_bytes,
    )
