# Architecture decision records

One file per decision, newest knowledge wins. An ADR is history: do not rewrite its body when something changes, add a dated note (`> **Update 2026-11-05:** ...`) or write a new ADR that supersedes it. Dates of the decisions come from the git history of this repository; the reasons are reconstructed from the code, the commit messages and the project notes, since no decision was recorded when it was taken.

| ADR | Decision | Status |
|---|---|---|
| [ADR-001](ADR-001-layered-architecture.md) | Same layered layout as the other services, enforced by a test | Accepted |
| [ADR-002](ADR-002-contract-streams.md) | Text in and audio out as `contracts.stream` NDJSON events | Accepted |
| [ADR-003](ADR-003-audio-conversion-in-tts.md) | The service converts the audio to the requested format | Accepted |
| [ADR-004](ADR-004-piper-default-with-droid-effect.md) | Piper `en_GB-alan-medium` plus a numpy droid effect is the default voice | Accepted |
| [ADR-005](ADR-005-espeak-robot-engine.md) | An `espeak` engine with a robot effect as a machine-voice option | Accepted |
| [ADR-006](ADR-006-fallback-and-voice-at-deploy-time.md) | Fall back to pyttsx3; fetch the voice at deploy time, never at start | Accepted |
| [ADR-007](ADR-007-single-shared-stream.md) | One shared audio stream; a new upload replaces the previous one | Accepted |
| [ADR-008](ADR-008-fallback-reported-in-available-reason.md) | A fallback is reported in the `reason` of `/available`; `is_available` stays true | Accepted (built and seen in a real container) |

New decision: copy the format of an existing ADR (Status, Related, Context, Decision, Consequences), take the next number, add a row here, and update the documents listed in the table of `CLAUDE.md`.
