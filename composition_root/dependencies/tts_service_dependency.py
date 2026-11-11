from application.ports.outbound.tts_outbound_port import TtsOutboundPort
from application.ports.service.tts_service_port import TtsServicePort
from application.services.tts_service import TtsService


def new_tts_service(synthesis: TtsOutboundPort, name: str) -> TtsServicePort:
    return TtsService(synthesis=synthesis, name=name)
