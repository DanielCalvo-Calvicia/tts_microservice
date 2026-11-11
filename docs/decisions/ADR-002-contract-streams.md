# ADR-002: Text in and audio out as `contracts.stream` NDJSON events

**Status:** Accepted (commit `c88c3a5`, 2026-09-20).
**Related:** [ADR-007](ADR-007-single-shared-stream.md), workspace `contracts/contracts/stream/README.md`

## Context

Brain streams the AI agent's answer to the voice as it is generated and plays audio as soon as it exists. The wire format between services is owned by `contracts` and must not be hand-written.

## Decision

`POST /process/stream/set` takes `Content-Type: application/x-ndjson` bodies of `TTS_INBOUND` events and answers `202` with a response that stays open as the ack stream (`UPLOAD_ACK`: `stream_started`, `input_completed`, or a recoverable `error`). `GET /process/stream/get` returns `TTS_OUTBOUND` events (`stream_started`, `partial`, `completed`, `error`, `heartbeat` every 15 s). Encoding and decoding go through `contracts.stream.codec`. The `completed` inbound event carries the whole text and is what gets spoken (a `partial` only builds it, so speaking both would say it twice). Plain text bodies and the single-request routes stay for simple clients and manual tests.

The response of `set` has to stay open: once an ASGI response completes, the server stops delivering the request body.

## Consequences

- Positive: Brain can start `get` before `set`; a failed text is a recoverable event, not a broken stream; the heartbeat keeps idle connections alive.
- Negative: `POST /process/stream` still carries headerless PCM labelled `audio/wav` (D-3); `keep_open_after_completed` is accepted and ignored. A new event or field goes into `contracts` first, then here, and the bundled wheel must be refreshed.
