# T-04 — Documentation sync

| | |
|---|---|
| Status | recurring |
| Kind | docs |
| Depends on | — |
| Blocks | — |

## Goal

A pass, repeated after every big task, that makes the documents describe the code and the evidence. It is the safety net of the rule in `CLAUDE.md` (every change updates its documents in the same change).

## When

After T-01, after T-02 and after T-03 (and whenever a task note says a document moved).

## Checklist

1. Counts: the test total, the contracts wheel version, the Python versions tested: in `CLAUDE.md`, `README.md`, the header of `docs/architecture/architecture.md`.
2. The debt table (D-1 to D-10) and the requirements table: status, evidence and task for every row this plan touched (D-2, D-4, D-5, D-6; FR-9, FR-12, FR-14, NFR-7, NFR-10).
3. The tts documents against the deployment ones: `docs/deployment/deployment.md` against `deployment/docs/DEPLOYMENT.md` and the `[services.tts]` entry of `deployment/config/catalogue.toml` (packages, `prepare`, readiness).
4. The audit: [../deployment_audit/tts.md](../deployment_audit/tts.md) keeps its text as an audit; add a dated note where a finding changed.
5. The tasks: the board in [README.md](README.md), [ORDER.md](ORDER.md) and every task file show the same state; links resolve; paths named in tasks still exist.
6. `brain_microservice\windows\Scripts\python.exe deployment\scripts\env_inventory.py --write` from the workspace root if an `.env.example` changed.

## Log

| Pass | Date | Notes |
|---|---|---|
| 1 | 2026-11-06 | Plan written; nothing built yet. |
| 2 | 2026-11-11 | After the restructure to the layout of `stt_microservice` (three ports, `dtos/inbound` and `dtos/outbound`, `routes/`, `response/`, `errors/`, `helpers/`, one dependency file each; `requirements.dev.txt`; `.engram/` removed). Done: test count 170; the paths in README, CLAUDE.md, architecture, API, ADR-001/006/008 (dated notes); "uncommitted" statements corrected (commit `fbec6c5` holds the 2026-11-06 work and contracts 0.16.0); the board and ORDER (T-01 and T-01.1 are done, T-03 is open only for the postponed arm64 task). Not rewritten on purpose: the task notes and `deployment_audit/tts.md` (records; they still cite the old file names). Links: 0 broken. |
