# ADR-004: Piper `en_GB-alan-medium` plus a droid effect is the default voice

**Status:** Accepted (commit `6a2f3d2`, 2026-10-01). The effect values are **not judged by ear** yet (D-2). *Note 2026-11-06 (T-01.1.5): the maintainer listened to the four samples of `scripts/render_samples.py` and kept the defaults (pitch 2.0, strength 0.5); the `espeak` robot values are still not judged.*
**Related:** [ADR-005](ADR-005-espeak-robot-engine.md), [ADR-006](ADR-006-fallback-and-voice-at-deploy-time.md)

## Context

The old engine, pyttsx3 (Windows SAPI5 or espeak), sounded dated and depends on what the machine has installed. The robot needs a recognisable, pleasant, local voice that also runs on a Raspberry Pi, with no cloud service and no key.

## Decision

`TTS_ENGINE=piper` is the default: a local neural voice (`en_GB-alan-medium`, ONNX, in process, one session behind a lock, run in a thread). The output goes through `droid_voice.py`, all numpy so a Pi renders a sentence faster than it takes to say it: a pitch lift by resampling (`TTS_PITCH_SEMITONES`, the pace is kept by slowing Piper by the same ratio), a high-shelf brightness boost, two short comb echoes, light ring modulation, and a peak limit so the chain never gets louder than the input. `TTS_DROID_EFFECT` scales it (0 off, 0.5 default, up to 2). Piper's `length_scale` is divided by `TTS_PIPER_SPEED` and the pitch ratio.

## Consequences

- Positive: a consistent voice on every machine; no network at run time; every knob is an environment variable.
- Negative: a 60 MB model outside git ([ADR-006](ADR-006-fallback-and-voice-at-deploy-time.md)); `piper-tts` and onnxruntime on arm64 are unverified (D-4); the effect values were tuned by tests and on paper. `scripts/render_samples.py` writes comparison WAVs for the listening check.
