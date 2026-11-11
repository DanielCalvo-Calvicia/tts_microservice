import base64

from contracts.api.microservices.tts.process_batch import ProcessBatchResponse
from fastapi.responses import JSONResponse

from application.dtos.inbound.process_batch_inbound import ProcessBatchInboundDTO
from application.ports.inbound.tts_inbound_port import TtsInboundPort
from infrastructure.inbound.http.response.http_envelope import failure, success


async def handle_process_batch(
    text: str, sample_rate: int, channels: int, inbound: TtsInboundPort
) -> JSONResponse:
    """POST /process/batch?text=: one text in, all of its audio back as base64. 400 on blank text."""
    try:
        result = await inbound.process_batch(
            ProcessBatchInboundDTO(text=text, sample_rate=sample_rate, channels=channels)
        )
    except Exception as error:
        return failure("process_batch", "Failed to process batch", error)
    return success(
        "process_batch",
        "Text synthesized successfully",
        ProcessBatchResponse(
            audio_data_base64=base64.b64encode(result.audio_data).decode("utf-8"),
            sample_rate=sample_rate,
            channels=channels,
        ),
    )
