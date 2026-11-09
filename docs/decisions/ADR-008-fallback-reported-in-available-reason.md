# ADR-008: A fallback is reported in the `reason` of `/available`

**Status:** Accepted (decided by the maintainer on 2026-11-06, task T-01.2.1). Built in the service on 2026-11-06 (task T-01.2.2); the deployment tool shows it since 2026-11-06 (task T-02.2), seen against a real fallback in a container (T-03.2).
**Related:** [ADR-006](ADR-006-fallback-and-voice-at-deploy-time.md), [ADR-004](ADR-004-piper-default-with-droid-effect.md), [ADR-005](ADR-005-espeak-robot-engine.md), [deployment audit](../deployment_audit/tts.md), [T-01.2.1](../tasks/T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.1_engine-report-decision.md)

## Context

[ADR-006](ADR-006-fallback-and-voice-at-deploy-time.md) lets the service start and speak with pyttsx3 when the chosen engine cannot load (the Piper voice is missing or corrupt, `espeak` is not installed). The cost, debt D-6, is that nothing a tool can read says so: `/available` answers `is_available: true` and `reason: null` on Piper and on the fallback alike, the deployment tool prints `healthy and available` after a failed voice fetch, and Brain's preflight sees a healthy service. The failure drill of T-01.1.4 (2026-11-06) reproduced this end to end.

`AvailabilityResponse` (`contracts.api.microservices.common`, shared by all services) already has an optional `reason`. Brain reads it only when `is_available` is false (`brain_microservice/infrastructure/outbound/http/http_client.py`, `check_health`); when it is true Brain ignores it. A fallback must never turn `is_available` into false, or Brain's preflight would exit and take the robot down.

## Options considered

- **A.** Use the existing `reason`; no `contracts` change. **Chosen.**
- B. Add `engine` / `fallback` fields to `AvailabilityResponse` in `contracts` (a version bump re-bundled in every service). Not chosen: it would show the engine on every answer, but costs a cross-repository change for a problem the existing field solves.
- C. No API change; checks scrape the log. Not chosen: fragile (the log is appended across restarts, as the drill showed).

## Decision

1. `GET /available` keeps `is_available: true` on the fallback and sets `reason` to a short note that names the engine that speaks and why the chosen one does not (for example `fallback: pyttsx3 (Piper voice en_GB-alan-medium is not in models)`). `reason` stays empty when the chosen engine is the one speaking. As built (T-01.2.2): `fallback: pyttsx3 instead of <piper|espeak> (<cause>)`, where the cause is the failure text on one line, cut to 200 characters, with the folder path removed (see `docs/api/api.md`). The composition root builds it and hands it to the pyttsx3 adapter; `SpeechSynthesisPort.fallback_reason()` and `TtsSynthesisPort.fallback_reason()` carry it to the HTTP handler (default `None`, so the Piper and espeak adapters did not change).
2. `GET /health` stays exactly as it is: liveness only, touches no engine.
3. The deployment tool treats a non-empty `reason` on an available service as a **warning**: it shows it in `status` and in the line `deploy`, `start` and `update` print for the service (`healthy and available, warning: <reason>`), and `deploy` still succeeds, so a machine that was offline during the deploy comes up (T-02.2, built). The Docker build is made strict separately, where the voice is required (T-02.1).
4. The healthy engine name stays in the log (`TtsService initialized`, `engine="PiperSpeechSynthesis"`), not in the answer.

## Consequences

- Positive: the silent case becomes visible to the deployment tool and to anyone calling `/available`, with no `contracts` change and no risk for Brain's preflight.
- Negative: Brain itself will not show the reason (it ignores `reason` when available); a change there would be a separate task in `brain_microservice`. A healthy service does not name its engine in the answer; only the log does. Consumers that print `reason` only on failure will not print it either.
- Debt D-6 closes when T-01.2.2 and T-02.2 are built and verified, not when this decision is recorded. They were, on 2026-11-06 (T-03.2, T-03.4).
