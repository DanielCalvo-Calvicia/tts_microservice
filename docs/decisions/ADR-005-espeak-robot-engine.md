# ADR-005: An `espeak` engine with a robot effect as a machine-voice option

**Status:** Accepted (commit `543008f`, 2026-10-04). Not the default.
**Related:** [ADR-004](ADR-004-piper-default-with-droid-effect.md)

## Context

Piper sounds like a person with a metallic tint. A truly mechanical voice is wanted as an option, and espeak is a formant synthesizer: the sound is computed from rules, not cut from a recording.

## Decision

`TTS_ENGINE=espeak` runs `espeak-ng` (or `espeak`, same command line) as one subprocess per sentence. The text goes through **stdin** (`--stdin --stdout`), never the command line, so there is no quoting and a text starting with `-` is not an option. The WAV on stdout is parsed (it may have unknown sizes because it comes from a pipe) and passed through `robot_voice.py` (ring modulation at 55 Hz, sample-and-hold, bit crush; strength `TTS_ROBOT_EFFECT`, 0 off, 3 maximum). Voice, speed, pitch and the gap between words are settings (`TTS_ESPEAK_*`). A probe sentence at load proves it speaks and tells the sample rate; each call has a 30 s timeout. A program that is missing falls back as in [ADR-006](ADR-006-fallback-and-voice-at-deploy-time.md).

## Consequences

- Positive: a clearly robotic voice, fast and light; a subprocess keeps a crash out of the service.
- Negative: a process per sentence; needs a system package (`espeak-ng`); the deployment catalogue lists `espeak` packages for the pyttsx3 fallback, not `espeak-ng`, so a machine that wants this engine installs it by hand (see the deployment page).
