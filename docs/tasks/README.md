# Tasks

Hierarchical task plan to make the **new deployment of `tts_microservice`** work and prove it: **T-01 deployment readiness of the service, T-02 changes in the deployment tool (the `deployment` repository), T-03 Docker and arm64 acceptance, T-04 documentation sync**. It was generated on 2026-11-06 from the deployment audit ([../deployment_audit/tts.md](../deployment_audit/tts.md)), and every claim it relies on was read in the code on 2026-11-05 (section 4). It is written to be executed step by step by the assistant: every leaf task states what to change, what it must not do, and how to prove it is done.

The status of every task is on the board in section 5. The order in which to do them, with state and date, is in [ORDER.md](ORDER.md) (kept in step with the board and with every task file).

**Plan revision 1 (2026-11-06):** first version. Nothing is done. One decision stopped part of the chain: [T-01.2.1](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.1_engine-report-decision.md) (where the engine report goes) was answered on 2026-11-06: option A, recorded in [ADR-008](../decisions/ADR-008-fallback-reported-in-available-reason.md); T-01.2.2 is unblocked.

## 1. Structure and naming

- Every task is a Markdown file. A task with subtasks lives in a folder of the same name, and its own file has the same name inside that folder. Leaves are single files.
- IDs are hierarchical and stable: `T-01` → `T-01.2` → `T-01.2.3`. Never reuse or renumber an ID.
- A parent task describes goal, order and exit criteria; **leaves carry the detail**.
- Every task file starts with the same header table (`Status`, `Kind`, `Parent`, `Depends on`, `Blocks`, `Size`) and has the sections *Goal*, *Read first*, *Files*, *Specification* or *Steps*, *Acceptance criteria*, *Verification* and *Notes*.

```
docs/tasks/
├── README.md                                   (this file)
├── ORDER.md                                    the order, the state and the date of every task
├── T-01_deployment-readiness/                  epic 1 (this repository)
│   ├── T-01_deployment-readiness.md
│   ├── T-01.1_baseline-checks/                 group with its leaves
│   ├── T-01.2_engine-visibility/
│   ├── T-01.3_requirements-split.md            leaf directly under T-01
│   └── T-01.4_service-documents.md
├── T-02_deployment-tool-changes/               epic 2 (the `deployment` repository)
├── T-03_docker-and-arm64-acceptance/           epic 3
└── T-04_documentation-sync.md                  recurring
```

Kinds: `code`, `test`, `decision`, `docs`, `manual` (needs a real machine, a real device or a person: the assistant prepares the commands and says what to look at; the maintainer runs it, or the assistant runs it after the maintainer says so).

## 2. Execution protocol (how the assistant works through this plan)

1. Pick the first task whose status is `todo` and whose `Depends on` tasks are all `done`. A decision (`decision`) that is `awaiting-user` **stops the chain** for the tasks that depend on it: ask the user, record the answer in the task's *Notes*, then continue.
2. Read the files listed in the task's *Read first*, and the repository `CLAUDE.md` of the repository you are about to edit (`tts_microservice` here; `deployment/CLAUDE.md` for T-02).
3. Create or modify only the files listed under *Files* (tests included). Another file, dependency or folder requires updating the task first.
4. Implement, then run the task's *Verification* and the baseline of section 3. A task is `done` only when every acceptance criterion passes.
5. Set the task's `Status` to `done`, update its row on the board (section 5) and in [ORDER.md](ORDER.md), update the parent if its exit criteria are met, and record any new fact or deviation in the task's *Notes*.
6. Update the documents the change touches, in the same piece of work (table in the `CLAUDE.md` of the repository).
7. Do not commit, push or publish unless the user asks. Do not run anything that deploys, builds an image or reaches another machine without saying so first (`deploy`, `docker build`, anything with `--remote`).

Status values: `todo`, `awaiting-user` (a decision needs an answer), `blocked` (depends on unfinished or undecided work), `in-progress`, `done`, `postponed` (decided not to run yet; it does not block the Windows work).

## 3. Baseline definition of done (applies to every code or test task)

- `windows\Scripts\python.exe -m pytest` passes from `tts_microservice` (157 passed, 1 warning on 2026-11-06 after T-01.2.3; 141 after T-01.2.2; 136 on 2026-11-05; a task that adds tests raises the number, and the new count goes into the documents that name it: the table of the `CLAUDE.md`).
- Tests live under `tests/`, mirroring the layer they cover (`application`, `domain`, `infrastructure`, `composition_root`, `architecture`); they need no real speech engine, no network and no hardware (fakes, `tmp_path`, `monkeypatch`). `tests/architecture/test_dependency_rules.py` stays green: dependencies point inward only.
- Logging only through `shared_logging` (`get_logger(__name__)`), constant message strings with keyword fields; never stdlib `logging`.
- Settings only from environment variables, documented in `.env.example`; after any `.env.example` change run `brain_microservice\windows\Scripts\python.exe deployment\scripts\env_inventory.py --write` from the workspace root.
- A route, field or event that other services see goes into `contracts` first (and bumps its version), then the producers and consumers. The service never hand-writes event JSON.
- No secrets in code, tests, fixtures or documents. Never open `.env`, `.env.staging` or `.env.production`.
- Ruff, black and mypy are configured but not installed in this venv: do not bulk-fix lint unasked. Keep the line endings of the file you edit (most source files are CRLF).
- Use the service venv (`windows\Scripts\python.exe`), not a global Python. Search only inside the service and exclude `windows/` and `testclear/` (a whole venv).
- The documents the change touches are updated in the same change (table in `CLAUDE.md`): this is part of done.

## 4. Facts the tasks rely on

Verified on 2026-11-05 against the code of both repositories, unless a row says otherwise.

| # | Fact |
|---|---|
| F1 | The tts repository is on branch `feature_ai_claude_2`; the last commit is `54a6259` "Bundle contracts 0.15.0"; the documentation (`docs/*`, `README.md`, `CLAUDE.md`) is uncommitted. The suite is `136 passed, 1 warning`. |
| F2 | `requirements.windows.txt` and `requirements.linux.txt` are identical: fastapi, uvicorn, python-dotenv, pydantic, httpx, pyttsx3, numpy, `piper-tts>=1.8.0,<2`, pytest, ruff, black, mypy, `-e ../shared-logging` and `./vendor/contracts_microservice-0.15.0-py3-none-any.whl`. Nothing in the service imports `httpx`. |
| F3 | `-e ../shared-logging` points at a sibling folder, so the file cannot be installed from a lone clone. The deployment tool strips `-e ../` lines (`deployment/infrastructure/outbound/installer/native_installer.py:21`) and installs a wheel of the library from `libs/`. |
| F4 | `piper-tts` 1.8.0 (needs Python 3.9 or newer) bundles `espeak-ng-data` and `espeakbridge`, and pulls onnxruntime 1.30.0. The `apt` packages `espeak`, `espeak-data`, `libespeak1` serve the pyttsx3 fallback on Linux and the `espeak` engine, not Piper. |
| F5 | `GET /available` and `GET /health` answer with `AvailabilityResponse` and `HealthCheckResponse` from `contracts.api.microservices.common` (shared by all services). `PiperSpeechSynthesis.is_available()` always returns `True`; the pyttsx3 one starts a subprocess with `pyttsx3.init()`. So `/available` is `true` on the Piper path and on the fallback alike. |
| F6 | The fallback is chosen in `composition_root/dependencies/tts_dependencies.py` (`new_speech_synthesis`) and logs `Piper unavailable; falling back to pyttsx3` or `espeak unavailable; falling back to pyttsx3` at error level. `tests/composition_root/test_engine_selection.py` covers a missing voice, a corrupt voice and a missing espeak, but does not assert the log line. |
| F7 | `scripts/fetch_voice.py` exits 0 when the voice is ready or the engine is not piper, and 1 on any download or load error. Run on 2026-11-05 with the voice present it prints "ready" (exit 0). |
| F8 | `deployment/docker/service.Dockerfile` runs the `prepare` script while building with `|| echo "warning: prepare step failed"`, so a failed voice download does not fail the build. The `.env` is bind-mounted at runtime, so only the default voice is baked into the image. `deployment/domain/rules/env_resolution.py:39` forces `SERVICE_HOST=0.0.0.0` for Docker. |
| F9 | `prepare_context` in `deployment/infrastructure/outbound/runtime/docker_runtime.py` copies the service folder with an ignore list of `.git`, `__pycache__`, `.venv`, `windows`, `.env`, `*.pyc`. It does not skip `testclear` or `.env.staging` / `.env.production`. |
| F10 | `deployment/config/catalogue.toml` entry `[services.tts]`: port 8002, `ready = "/available"`, `libraries = ["shared-logging"]`, `apt = ["espeak", "espeak-data", "libespeak1"]`, `prepare = ["scripts/fetch_voice.py"]`, no `min_python`. The manual says the apt packages are "only the pyttsx3 fallback". |
| F11 | The voice file is already in `tts_microservice/models/` on the maintainer's machine, so a check on the working folder proves nothing about a fresh deploy. |
| F12 | The active Docker CLI context is `raspberry` (an SSH context to the Pi), which timed out on 2026-11-05; the `desktop-linux` engine was not running. No image was built. A build here needs Docker Desktop started, and the right context chosen per command (`docker --context desktop-linux ...`), never by changing the saved context. |
| F13 | Debts and requirements this plan closes: D-4, D-5, D-6, D-2 and FR-14, NFR-7, NFR-10 in [../architecture/architecture.md](../architecture/architecture.md) and [../requirements/requirements.md](../requirements/requirements.md). |

## 5. Status board

| ID | Task | Kind | Status |
|---|---|---|---|
| [T-01](T-01_deployment-readiness/T-01_deployment-readiness.md) | **Deployment readiness of the service** (epic) | epic | in-progress |
| [T-01.1](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1_baseline-checks.md) | Baseline checks (no code change) | group | in-progress |
| [T-01.1.1](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.1_clean-install-and-tests.md) | Clean install and tests | test | done |
| [T-01.1.2](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.2_native-deploy.md) | Native deploy with the tool | manual | done |
| [T-01.1.3](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.3_log-and-endpoint-checks.md) | Log and endpoint checks | manual | done |
| [T-01.1.4](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.4_failure-drill.md) | Failure drill: a voice that cannot be fetched | manual | done |
| [T-01.1.5](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.5_listening-check.md) | Listening check | manual | done |
| [T-01.1.6](T-01_deployment-readiness/T-01.1_baseline-checks/T-01.1.6_pipeline-round-trip.md) | Pipeline round trip through Brain | manual | done |
| [T-01.2](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2_engine-visibility.md) | Engine visibility | group | done |
| [T-01.2.1](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.1_engine-report-decision.md) | Decision: where the engine report goes | decision | done (A) |
| [T-01.2.2](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.2_engine-report.md) | Report the active engine | code | done |
| [T-01.2.3](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.3_fetch-voice-exit-codes.md) | Pin the exit codes of `fetch_voice.py` with tests | test | done |
| [T-01.2.4](T-01_deployment-readiness/T-01.2_engine-visibility/T-01.2.4_fallback-log-assertions.md) | Fallback log assertions | test | done |
| [T-01.3](T-01_deployment-readiness/T-01.3_requirements-split.md) | Split the runtime and dev requirements | code | done |
| [T-01.4](T-01_deployment-readiness/T-01.4_service-documents.md) | Service documents true again | docs | done |
| [T-02](T-02_deployment-tool-changes/T-02_deployment-tool-changes.md) | **Deployment tool changes** (the `deployment` repository) | epic | done |
| [T-02.1](T-02_deployment-tool-changes/T-02.1_fail-the-docker-build.md) | Fail the Docker build when the voice is required and missing | code | done |
| [T-02.2](T-02_deployment-tool-changes/T-02.2_fallback-in-status.md) | Show the fallback in `status` and in the readiness wait | code | done |
| [T-02.3](T-02_deployment-tool-changes/T-02.3_build-context-filter.md) | Build context filter | code | done |
| [T-02.4](T-02_deployment-tool-changes/T-02.4_manual-corrections.md) | Manual corrections (apt packages, baked voice) | docs | done |
| [T-03](T-03_docker-and-arm64-acceptance/T-03_docker-and-arm64-acceptance.md) | **Docker and arm64 acceptance** | epic | in-progress |
| [T-03.1](T-03_docker-and-arm64-acceptance/T-03.1_amd64-build.md) | Build the image on amd64 | manual | done |
| [T-03.2](T-03_docker-and-arm64-acceptance/T-03.2_run-and-call.md) | Run the container and call it | manual | done |
| [T-03.3](T-03_docker-and-arm64-acceptance/T-03.3_arm64.md) | Build and run on arm64 | manual | postponed |
| [T-03.4](T-03_docker-and-arm64-acceptance/T-03.4_build-without-network.md) | Build without network | manual | done |
| [T-03.5](T-03_docker-and-arm64-acceptance/T-03.5_record-the-results.md) | Record what was verified | docs | done |
| [T-04](T-04_documentation-sync.md) | **Documentation sync** (recurring) | docs | recurring |
