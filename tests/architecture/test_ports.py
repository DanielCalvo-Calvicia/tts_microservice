"""Fitness function: the service and every adapter implement a port, and the ports are the contract.

    inbound adapter (TtsHandler)        implements  TtsInboundPort
    service (TtsService)                implements  TtsServicePort
    outbound adapters (the 3 engines)   implement   TtsOutboundPort

A new inbound or outbound adapter implements the same port as the others, so its functions are the same.
"""

import ast
from pathlib import Path

import pytest

from application.ports.inbound.tts_inbound_port import TtsInboundPort
from application.ports.outbound.tts_outbound_port import TtsOutboundPort
from application.ports.service.tts_service_port import TtsServicePort
from application.services.tts_service import TtsService
from infrastructure.inbound.http.http_handler import TtsHandler
from infrastructure.outbound.espeak_speech.espeak_speech_synthesis import EspeakSpeechSynthesis
from infrastructure.outbound.piper_speech.piper_speech_synthesis import PiperSpeechSynthesis
from infrastructure.outbound.pyttsx3_speech.pyttsx3_speech_synthesis import Pyttsx3SpeechSynthesis

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("component", "port"),
    [
        (TtsService, TtsServicePort),
        (TtsHandler, TtsInboundPort),
        (PiperSpeechSynthesis, TtsOutboundPort),
        (EspeakSpeechSynthesis, TtsOutboundPort),
        (Pyttsx3SpeechSynthesis, TtsOutboundPort),
    ],
)
def test_each_component_implements_its_port(component, port):
    assert issubclass(component, port)
    assert not component.__abstractmethods__, "a port operation is not implemented"


@pytest.mark.parametrize(
    ("port", "operations"),
    [
        (
            TtsInboundPort,
            {
                "health",
                "is_available",
                "fallback_reason",
                "current_format",
                "process_stream",
                "set_stream",
                "get_segment_stream",
                "process_batch",
            },
        ),
        (
            TtsServicePort,
            {"process_stream", "set_stream", "get_stream", "get_segment_stream", "process_batch", "is_available"},
        ),
        (TtsOutboundPort, {"synthesize_stream", "synthesize", "is_available"}),
    ],
)
def test_the_port_is_the_contract(port, operations):
    assert port.__abstractmethods__ == operations


def _classes(package: str, suffix: str) -> list[tuple[str, ast.ClassDef]]:
    found = []
    for path in sorted((ROOT / "infrastructure" / package).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef) and node.name.endswith(suffix):
                found.append((f"{path.relative_to(ROOT)}:{node.name}", node))
    return found


def _base_names(node: ast.ClassDef) -> set[str]:
    return {base.id for base in node.bases if isinstance(base, ast.Name)}


def test_every_inbound_adapter_implements_the_inbound_port():
    adapters = _classes("inbound", "Handler")
    assert adapters, "no inbound adapter found"
    missing = [name for name, node in adapters if "TtsInboundPort" not in _base_names(node)]
    assert not missing, f"inbound adapters that do not implement TtsInboundPort: {missing}"


def test_every_outbound_adapter_implements_the_outbound_port():
    adapters = _classes("outbound", "SpeechSynthesis")
    assert adapters, "no outbound adapter found"
    missing = [name for name, node in adapters if "TtsOutboundPort" not in _base_names(node)]
    assert not missing, f"outbound adapters that do not implement TtsOutboundPort: {missing}"
