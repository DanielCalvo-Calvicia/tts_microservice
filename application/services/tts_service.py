import asyncio
from collections.abc import AsyncIterator

from shared_logging import get_logger

from application.dtos.audio_batch_outbound import AudioBatchOutboundDTO
from application.dtos.audio_segment_outbound import (
    AudioChunk,
    AudioSegmentEvent,
    AudioSegmentStreamOutboundDTO,
    SegmentFailed,
    StreamFormat,
)
from application.dtos.audio_stream_outbound import AudioStreamOutboundDTO
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.ports.inbound.tts_synthesis_port import TtsSynthesisPort
from application.ports.outbound.speech_synthesis_port import SpeechSynthesisPort
from domain.operations.text import is_speakable, require_speakable
from domain.value_objects.audio_format import AudioFormat

logger = get_logger(__name__)

_AudioQueue = asyncio.Queue[AudioSegmentEvent | None]


class TtsService(TtsSynthesisPort):
    """Orchestrates the text-to-speech use cases. Business rules live in the domain."""

    def __init__(self, synthesis: SpeechSynthesisPort, name: str = "tts_service") -> None:
        self.name = name
        self._synthesis = synthesis
        # get_stream may be called before set_stream: it then waits on this empty queue.
        self._audio_queue: _AudioQueue = asyncio.Queue()
        self._generator_task: asyncio.Task[None] | None = None
        self._format: AudioFormat | None = None
        logger.info(
            "TtsService initialized",
            name=name,
            engine=type(synthesis).__name__,
        )

    async def process_stream(self, request: ProcessStreamInboundDTO) -> AudioStreamOutboundDTO:
        audio_format = AudioFormat(sample_rate=request.sample_rate, channels=request.channels)
        audio = self._synthesis.synthesize_stream(_speakable(request.text_stream), audio_format)
        return AudioStreamOutboundDTO(audio_stream=audio)

    async def set_stream(self, request: ProcessStreamInboundDTO) -> None:
        audio_format = AudioFormat(sample_rate=request.sample_rate, channels=request.channels)
        if self._generator_task is not None and not self._generator_task.done():
            logger.info("Cancelling the previous shared stream generator")
            self._generator_task.cancel()
            try:
                await self._generator_task
            except asyncio.CancelledError:
                logger.info("Previous shared stream generator cancelled")

        # A fresh queue discards stale chunks; readers of the old one see its end-of-stream. The very
        # first queue is kept: a reader that connected before any ``set`` is already waiting on it.
        first_set = self._format is None
        queue: _AudioQueue = self._audio_queue if first_set else asyncio.Queue()
        self._audio_queue = queue
        self._format = audio_format
        queue.put_nowait(StreamFormat(audio_format.sample_rate, audio_format.channels))
        self._generator_task = asyncio.create_task(
            self._generate_into_queue(request.text_stream, audio_format, queue)
        )

    def current_format(self) -> tuple[int, int] | None:
        if self._format is None:
            return None
        return self._format.sample_rate, self._format.channels

    async def get_stream(self) -> AudioStreamOutboundDTO:
        return AudioStreamOutboundDTO(audio_stream=_audio_only(_drain(self._audio_queue)))

    async def get_segment_stream(self) -> AudioSegmentStreamOutboundDTO:
        return AudioSegmentStreamOutboundDTO(events=_drain(self._audio_queue))

    async def process_batch(self, request: ProcessBatchInboundDTO) -> AudioBatchOutboundDTO:
        text = require_speakable(request.text)
        audio_format = AudioFormat(sample_rate=request.sample_rate, channels=request.channels)
        audio = await self._synthesis.synthesize(text, audio_format)
        logger.info("Batch synthesis finished", audio_bytes=len(audio))
        return AudioBatchOutboundDTO(audio_data=audio)

    async def is_available(self) -> bool:
        return await self._synthesis.is_available()

    async def _generate_into_queue(
        self, text_stream: AsyncIterator[str], audio_format: AudioFormat, queue: _AudioQueue
    ) -> None:
        chunk_count = 0
        total_bytes = 0
        try:
            async for event in self._synthesis.synthesize_segments(
                _speakable(text_stream), audio_format
            ):
                await queue.put(event)
                if isinstance(event, AudioChunk):
                    chunk_count += 1
                    total_bytes += len(event.data)
            logger.info(
                "Shared stream generation completed",
                chunk_count=chunk_count,
                total_bytes=total_bytes,
            )
        except asyncio.CancelledError:
            logger.info("Shared stream generation cancelled")
        except Exception as error:
            logger.exception("Shared stream generation failed")
            await queue.put(SegmentFailed(message=f"speech generation failed: {error}"))
        finally:
            await queue.put(None)  # end-of-stream sentinel


async def _speakable(text_stream: AsyncIterator[str]) -> AsyncIterator[str]:
    async for text in text_stream:
        if is_speakable(text):
            yield text
        else:
            logger.info("Skipped blank text item")


async def _drain(queue: _AudioQueue) -> AsyncIterator[AudioSegmentEvent]:
    while True:
        event = await queue.get()
        if event is None:
            logger.info("Audio stream reached end-of-stream sentinel")
            return
        yield event


async def _audio_only(events: AsyncIterator[AudioSegmentEvent]) -> AsyncIterator[bytes]:
    async for event in events:
        if isinstance(event, AudioChunk):
            yield event.data
