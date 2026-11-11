# ADR-007: One shared audio stream; a new upload replaces the previous one

**Status:** Accepted (commit `c88c3a5`, 2026-09-20; moved into `TtsService` in the restructure).
**Related:** [ADR-002](ADR-002-contract-streams.md), [ADR-001](ADR-001-layered-architecture.md)

## Context

Brain uploads text on one connection and reads audio on another, and may open the reader before the writer. The robot has one mouth: there is one conversation at a time.

## Decision

`TtsService` owns one audio queue, one generator task and the stream's `AudioFormat`. `set` cancels the running generator, starts a fresh queue (so stale chunks are dropped and readers of the old queue see its end-of-stream sentinel), publishes the new format as the first item and starts a new generator. The very first queue is kept so a reader that connected before any `set` is already waiting on it. `/process/batch` and `/process/stream` never touch this queue. A generator failure becomes a recoverable `SegmentFailed` event followed by the sentinel.

## Consequences

- Positive: a barge-in (a new answer) cuts the old speech at once; engine-independent and tested with a fake engine.
- Negative: no concurrent conversations; two clients sharing the service would interrupt each other; the queue is unbounded (D-7).
