# ADR-001: Same layered layout as the other services

**Status:** Accepted (restructure of 2026-05/09, recorded 2026-11-05).
**Related:** workspace `CLAUDE.md` (conventions), [ADR-007](ADR-007-single-shared-stream.md)

## Context

The first version was a 410-line `fastapi_adapter.py` that acted as inbound adapter, port and engine driver at once, with copy-pasted DTO triples and three copies of the "synthesize to a temp WAV and read it back" loop. Bugs hid in it (empty batch audio, a batch call writing into the shared queue, a 400 turned into a 500).

## Decision

`main.py` → `main_flow/` → `composition_root/` → `application/` → `domain/` → `infrastructure/`, the layout of every OBLIVION service. Dependencies point inward only. Business rules (blank text, audio format, PCM conversion) live in `domain/`; the use cases and the shared stream live in `TtsService`; ports are `TtsSynthesisPort` (driving) and `SpeechSynthesisPort` (driven); engines are outbound adapters; only `composition_root` knows concrete classes. `tests/architecture/test_dependency_rules.py` parses imports and fails on a violation.

## Consequences

- Positive: engines are swappable without touching the service (Piper, espeak and pyttsx3 share one port); the stream logic is tested with a fake engine; the layout matches the other services.
- Negative: more files than the problem strictly needs for a small service.

> **Update 2026-11-11:** the application now owns three ports, not two: `TtsServicePort` (the service's own, what `TtsService` implements; it was called `TtsSynthesisPort` and sat in `ports/inbound/`), `TtsInboundPort` (new: what every inbound adapter offers, implemented by the HTTP handler) and `TtsOutboundPort` (what every engine offers; it was called `SpeechSynthesisPort`, file `tts_outbound_port.py`). The DTOs are in `application/dtos/inbound` and `application/dtos/outbound`. The inbound adapter folder follows `stt_microservice` and `dynamics_microservice` (`http_handler.py` wires, `routes/`, `response/`, `errors/`, `helpers/`); `helpers/` is the one place the `helpers` name is allowed. `tests/architecture/test_ports.py` and `test_dtos.py` check it. No behaviour changed.
