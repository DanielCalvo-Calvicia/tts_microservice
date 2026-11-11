# ADR-006: Fall back to pyttsx3; fetch the voice at deploy time, never at start

**Status:** Accepted (commit `6a2f3d2`, 2026-10-01).
**Related:** [ADR-004](ADR-004-piper-default-with-droid-effect.md), [ADR-005](ADR-005-espeak-robot-engine.md), [deployment](../deployment/deployment.md)

## Context

Brain's start-up preflight waits 60 s for this service and exits if it is not ready. The Piper voice is about 60 MB, not in git (`models/` is ignored) and not in pip, and a machine can lack the network, the disk space, `onnxruntime`, or `espeak-ng`.

## Decision

1. `new_speech_synthesis` in `composition_root/dependencies/tts_dependencies.py` tries the chosen engine and, on `SynthesisFailed`, logs an **error** with the reason and uses pyttsx3. The service always starts, and the robot always speaks.
2. The voice is never downloaded when the service starts. `scripts/fetch_voice.py` does it, run by the deployment tool's `prepare` step after the `.env` is written (deploy, update, rollback). It downloads to a temporary folder inside the model folder, loads the voice once, and only then moves the files into place, config last, so an interrupted download leaves nothing half-installed. A failure only warns.

## Consequences

- Positive: a failed download cannot take the robot down; re-running the script repairs it.
- Negative: the fallback is **silent to the caller** (`/available` is `true`); only the log line says the old voice is in use (D-6). The deployment page asks for a log check after each deploy.

> **Update 2026-11-06:** the silent fallback was reproduced on a real deploy (T-01.1.4) and [ADR-008](ADR-008-fallback-reported-in-available-reason.md) decides how it is reported: in the `reason` of `/available`, with `is_available` still `true`. The rules above (start on the fallback, never download at start) are unchanged.
>
> **Update 2026-11-06 (T-03.2):** the premise "the robot always speaks" was found not to hold in the Docker image (Debian bookworm, apt `espeak espeak-data libespeak1`): the service starts on the fallback but pyttsx3 cannot initialise there (`SetVoiceByName failed ... gmw/en`), so `/available` answers `is_available: false` and `/process/batch` answers 502. With `espeak-ng` packages both voices worked in a test. The decision stands, its evidence on that platform did not. **Fixed the same day:** the catalogue's `apt` list for tts is now `espeak-ng libespeak-ng1`; in a rebuilt image, with a missing voice, the service stays available, reports the fallback in `reason` and speaks with pyttsx3 (debt D-11, T-03.2).

> **Update 2026-11-11:** `tts_dependencies.py` was split; `new_speech_synthesis` is now in `composition_root/dependencies/speech_synthesis_dependency.py`. Same behaviour.
