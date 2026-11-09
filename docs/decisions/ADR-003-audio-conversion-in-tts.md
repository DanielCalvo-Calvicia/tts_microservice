# ADR-003: The service converts the audio to the requested format

**Status:** Accepted (commit `c88c3a5`, 2026-09-20).
**Related:** workspace `CLAUDE.md` (Audio: PCM16 mono, "never convert between services")

## Context

Each engine speaks at its own native rate (Piper 22050 Hz, espeak 22050 Hz, pyttsx3 whatever SAPI gives). Brain and Speaker rely on getting exactly the format Brain asked for. An earlier version echoed `sample_rate` and `channels` without applying them.

## Decision

The producer of the audio converts it. `sample_rate` and `channels` are validated by the `AudioFormat` value object (both greater than 0), and every engine's output passes `domain.operations.pcm.convert_pcm16` (linear interpolation resampling, mono duplicated to all channels, multichannel averaged to mono) before it leaves the service. No other service converts audio. A `get` call that repeats the format must match the one the `set` fixed (`422`).

## Consequences

- Positive: callers can trust the stream header; the conversion is one tested function.
- Negative: linear interpolation is good enough for speech, not for music; resampling happens once on the CPU of the machine that runs tts.
