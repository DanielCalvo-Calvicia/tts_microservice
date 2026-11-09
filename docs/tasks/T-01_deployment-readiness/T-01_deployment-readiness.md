# T-01 — Deployment readiness of the service

| | |
|---|---|
| Status | todo |
| Kind | epic |
| Depends on | — |
| Blocks | T-03 |

## Goal

A deploy of `tts_microservice` (native on Windows, native on Linux or a Raspberry Pi, and Docker) that comes up speaking with the Piper voice, and that says so loudly, in a place a tool can read, when it does not. Today a missing voice is a log line only: `/available` stays `true`, so the deployment tool and Brain's preflight cannot tell Piper from the pyttsx3 fallback (debt D-6, [ADR-006](../../decisions/ADR-006-fallback-and-voice-at-deploy-time.md)).

## Why

The deployment audit ([../../deployment_audit/tts.md](../../deployment_audit/tts.md)) found that the service itself is sound and the risk is silence: a voice that failed to download, in Docker or natively, still yields a healthy-looking service. The tasks below first measure what is true today (T-01.1, no code change), then make the engine visible and the failure distinguishable (T-01.2), then tidy the requirements (T-01.3) and the documents (T-01.4).

## Decisions kept (do not reopen)

- **Never download at service start** (ADR-006): Brain's preflight waits only 60 s.
- **The service must still start and speak on the fallback** when the voice is missing: a machine that was offline during the deploy must come up. The change is that the fallback becomes visible, not that it becomes an error.
- **Brain is the only coordinator**; the report is read by the deployment tool and by people, never by another service calling tts directly.

## Subtasks

| Order | Task | State |
|---|---|---|
| 1 | [T-01.1 Baseline checks](T-01.1_baseline-checks/T-01.1_baseline-checks.md) | in progress (T-01.1.1 to T-01.1.5 done) |
| 2 | [T-01.2 Engine visibility](T-01.2_engine-visibility/T-01.2_engine-visibility.md) | done (2026-11-06: decision A, ADR-008; T-01.2.2 to T-01.2.4 built; 157 tests) |
| 3 | [T-01.3 Split the runtime and dev requirements](T-01.3_requirements-split.md) | done (2026-11-06) |
| 4 | [T-01.4 Service documents true again](T-01.4_service-documents.md) | done (2026-11-06) |

## Exit criteria

- T-01.1 is done and its findings are in the *Notes* of its leaves.
- On a fresh machine the deployment tool reports tts as Piper (or as a fallback, loudly), and a test fails if a fallback stops being reported.
- The runtime install contains no test or lint tools and no unused package.
- `docs/deployment/deployment.md`, the architecture debt table, the requirements and the `CLAUDE.md` say what is true.
