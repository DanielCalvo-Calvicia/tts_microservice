# Task order

The order in which the tasks must be done, with the state of each one and the date its file was last updated. It follows the execution protocol of the [tasks README](README.md) (section 2): the first task that is `todo` and whose dependencies are `done`. Dependencies are in each task file; decisions that stop the chain are marked.

**Keep this file true:** every change to a task (a status, a dependency, a new task, an order change) updates this table, the board of the [tasks README](README.md) section 5 and the task file itself (see `CLAUDE.md` at the root of the repository). The *Last updated* column is the date of the last change to the task file and is refreshed by the same change.

## States

| State | Meaning |
|---|---|
| Done | Implemented and verified (or, for a decision, taken and recorded) |
| In progress | Some of its sub-tasks are done and some are not |
| Todo | Ready to start when its dependencies are done |
| Awaiting user | A decision needs the maintainer's answer; it stops the tasks that depend on it |
| Blocked | Waits for another task or for a decision |
| Recurring | Repeated after every big task |

Written on 2026-11-06 from the deployment audit, last brought in line on 2026-11-11 (pass 2 of [T-04](T-04_documentation-sync.md)). Epic T-01 is done: T-01.1.1 to T-01.1.5 on 2026-11-06 and T-01.1.6 (the pipeline round trip through Brain) on 2026-11-09; the whole T-01.2 group (decision A, ADR-008; 157 tests then), T-01.3 and T-01.4 on 2026-11-06. Epic T-02 is done (T-02.1 to T-02.4, in the `deployment` repository). In T-03, T-03.1, T-03.2 (it found D-11, fixed in the catalogue `apt` list), T-03.4 and T-03.5 are done; **T-03.3 (arm64) is postponed** (2026-11-09: it needs a Raspberry Pi 4 or newer, and no Pi test is planned until the services work fully on Windows). Nothing is todo. The restructure of the layers on 2026-11-11 changed file names that old task notes cite; those notes are a record and were not rewritten.

## A. Deployment readiness of the service (T-01)

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 1 | [T-01](T-01_deployment-readiness/T-01_deployment-readiness.md) | Deployment readiness of the service | epic | Done | all subtasks done (T-01.1.6 on 2026-11-09) | — | 2026-11-11 |
| 2 | [T-01.1](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1_baseline-checks.md) | Baseline checks | group | Done | all six leaves done (T-01.1.6 on 2026-11-09) | — | 2026-11-11 |
| 3 | [T-01.1.1](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.1_clean-install-and-tests.md) | Clean install and tests | test | Done | 136 passed in a clean clone; voice fetched twice (exit 0); findings in its Notes | — | 2026-11-06 |
| 4 | [T-01.1.2](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.2_native-deploy.md) | Native deploy with the tool | manual | Done | deployed into the scratchpad with a throwaway `--config`; voice fetched, healthy on 8002; service left running for T-01.1.3 | T-01.1.1 | 2026-11-06 |
| 5 | [T-01.1.3](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.3_log-and-endpoint-checks.md) | Log and endpoint checks | manual | Done | Piper confirmed in the log; all five endpoint checks pass | T-01.1.2 | 2026-11-06 |
| 6 | [T-01.1.4](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.4_failure-drill.md) | Failure drill | manual | Done | D-6 reproduced: warning, exit 0, "healthy and available", `is_available: true` on pyttsx3; repaired by a second deploy | T-01.1.2 | 2026-11-06 |
| 7 | [T-01.1.5](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.5_listening-check.md) | Listening check | manual | Done | maintainer kept the default (variant 3); D-2 resolved for the Piper droid voice, open for the espeak robot voice | T-01.1.1 | 2026-11-06 |
| 8 | [T-01.1.6](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.6_pipeline-round-trip.md) | Pipeline round trip through Brain | manual | Done | step 1 84 passed, 18 skipped (2026-11-06); steps 2 and 3 run 2026-11-09 with the real speaker: tts ready in Brain's preflight, three sentences spoken; found the speaker's 3 s truncation (R-6) | T-01.1.2 | 2026-11-09 |
| 9 | [T-01.2](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2_engine-visibility.md) | Engine visibility | group | Done | all four leaves done | T-01.1 | 2026-11-06 |
| 10 | [T-01.2.1](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.1_engine-report-decision.md) | Decision: where the engine report goes | decision | Done | option A chosen: `reason` of `/available`, `/health` unchanged, tool warns (ADR-008) | T-01.1.3 | 2026-11-06 |
| 11 | [T-01.2.2](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.2_engine-report.md) | Report the active engine | code | Done | `/available` carries a path-free `reason` on a fallback; 141 tests pass | T-01.2.1 | 2026-11-06 |
| 12 | [T-01.2.3](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.3_fetch-voice-exit-codes.md) | Pin the exit codes of `fetch_voice.py` with tests | test | Done | 16 tests, all 11 mutations of the script caught; 157 tests pass | T-01.1.4 | 2026-11-06 |
| 13 | [T-01.2.4](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.4_fallback-log-assertions.md) | Fallback log assertions | test | Done | 9 mutations of the log lines caught; 157 tests pass | T-01.1.3 | 2026-11-06 |
| 14 | [T-01.3](T-01_deployment-readiness/T-01.3_requirements-split.md) | Split the runtime and dev requirements | code | Done | runtime-only venv starts the service, runtime plus dev passes 157 tests; D-5 partly resolved | T-01.1.1 | 2026-11-06 |
| 15 | [T-01.4](T-01_deployment-readiness/T-01.4_service-documents.md) | Service documents true again | docs | Done | contracts version, state paragraph, Docker wording, audit update; 0 broken links; 157 tests | T-01.2.2, T-01.3 | 2026-11-06 |

## B. Deployment tool changes (T-02, the `deployment` repository)

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 16 | [T-02](T-02_deployment-tool-changes/T-02_deployment-tool-changes.md) | Deployment tool changes | epic | Done | all four tasks done; the deployment suite has one failure from camera's contracts 0.15.0, not from this epic | T-01.2 | 2026-11-06 |
| 17 | [T-02.1](T-02_deployment-tool-changes/T-02.1_fail-the-docker-build.md) | Fail the Docker build when the voice is required and missing | code | Done | `prepare_required` for tts; the Dockerfile fails the build; 20 prepare tests; deployment suite 283 passed, 2 skipped, 1 failed (camera bundles contracts 0.15.0, unrelated) | T-01.2.3 | 2026-11-06 |
| 18 | [T-02.2](T-02_deployment-tool-changes/T-02.2_fallback-in-status.md) | Show the fallback in `status` and in the readiness wait | code | Done | `check` returns `healthy and available, warning: <reason>`; 16 health tests, 10 mutations caught; deployment suite 298 passed, 2 skipped, 1 failed (camera, unrelated) | T-01.2.2 | 2026-11-06 |
| 19 | [T-02.3](T-02_deployment-tool-changes/T-02.3_build-context-filter.md) | Build context filter | code | Done | `.env.*` (except the example) and `testclear` stay out of the context; 19 new tests, 11 mutations caught; deployment suite 317 passed, 2 skipped, 1 failed (camera, unrelated) | independent | — | 2026-11-06 |
| 20 | [T-02.4](T-02_deployment-tool-changes/T-02.4_manual-corrections.md) | Manual corrections | docs | Done | three lines of words (system packages row, voices row, the catalogue comment); 317 tests pass, 1 unrelated failure | — | 2026-11-06 |

## C. Docker and arm64 acceptance (T-03)

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 21 | [T-03](T-03_docker-and-arm64-acceptance/T-03_docker-and-arm64-acceptance.md) | Docker and arm64 acceptance | epic | In progress | T-03.1, T-03.2, T-03.4 and T-03.5 done; T-03.3 (arm64) postponed, it needs a Raspberry Pi; Docker Desktop must stay started, commands use `--context desktop-linux` | T-01, T-02 | 2026-11-11 |
| 22 | [T-03.1](T-03_docker-and-arm64-acceptance/T-03.1_amd64-build.md) | Build the image on amd64 | manual | Done | image builds in 68 s on Python 3.12.16, voice fetched into `/app/models`, 792 MB; built from the pushed commit, so it lacks the uncommitted work | T-02.1, T-02.3 | 2026-11-06 |
| 23 | [T-03.2](T-03_docker-and-arm64-acceptance/T-03.2_run-and-call.md) | Run the container and call it | manual | Done | the working-tree image runs, answers and speaks; step 5 found D-11 (pyttsx3 fallback broken by the old espeak packages), fixed by `apt = ["espeak-ng", "libespeak-ng1"]`; the tool then prints `healthy and available, warning: ...` for a missing voice | T-03.1, T-02.2 | 2026-11-06 |
| 24 | [T-03.3](T-03_docker-and-arm64-acceptance/T-03.3_arm64.md) | Build and run on arm64 | manual | Postponed | needs a Raspberry Pi 4 or newer | T-03.2 | 2026-11-09 |
| 25 | [T-03.4](T-03_docker-and-arm64-acceptance/T-03.4_build-without-network.md) | Build without network | manual | Done | a nonexistent voice and a refused connection each fail the build (exit 1, clear message) and leave the image tag untouched; the correct build succeeds; no really offline machine | T-03.1, T-02.1 | 2026-11-06 |
| 26 | [T-03.5](T-03_docker-and-arm64-acceptance/T-03.5_record-the-results.md) | Record what was verified | docs | Done | recorded 2026-11-09; arm64 postponed | T-03.2, T-03.3, T-03.4 | 2026-11-09 |

## D. Recurring

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 27 | [T-04](T-04_documentation-sync.md) | Documentation sync | docs | Recurring | after T-01, T-02 and T-03 | — | 2026-11-11 |

## What can run in parallel

All of T-01 and T-02 are done. T-01.2.1, the only decision, was answered (option A). In T-03 only T-03.3 (arm64, needs a Raspberry Pi) is left, and it is postponed.
