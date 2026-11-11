# T-02 — Deployment tool changes (the `deployment` repository)

| | |
|---|---|
| Status | done (2026-11-06; the deployment suite has one failure that is not from this epic, see Exit criteria) |
| Kind | epic |
| Depends on | T-01.2 (for T-02.1 and T-02.2) |
| Blocks | T-03 |

## Goal

Change the deployment tool so that a tts deploy cannot fail silently: the Docker build fails when the Piper voice is required and missing, the tool shows when the service reports a fallback, the build context cannot carry secrets, and the manual says what is true about tts.

## Rules for this epic

- `deployment` is its own repository with its own `CLAUDE.md`: **read `deployment/CLAUDE.md` before editing anything** and follow it (the layered layout, "define every fact once", everything external through `Shell`, dry-run without side effects, tests for the install path).
- The edits are made in `D:\Hobbys\IA\OBLIVION\deployment`, not in this repository. This epic lives here because its cause and its acceptance are tts's. Do not commit or push in either repository unless asked.
- The deployment tests are run with the brain venv, from `deployment/` (about 150 s; run them in the background): `..\brain_microservice\windows\Scripts\python.exe -m pytest tests -q`.
- The `deployment` repository already has uncommitted changes that are not part of this plan (`catalogue.toml`, `DEPLOYMENT.md`, camera and stepper files, seen on 2026-11-05). Read `git status` and `git diff` of a file before editing it, and change only the lines this plan names.

## Subtasks

| Order | Task | Kind | State |
|---|---|---|---|
| 1 | [T-02.1 Fail the Docker build when the voice is required and missing](T-02.1_fail-the-docker-build.md) | code | done (2026-11-06; one unrelated failure in the deployment suite) |
| 2 | [T-02.2 Show the fallback in `status` and in the readiness wait](T-02.2_fallback-in-status.md) | code | done (2026-11-06; same unrelated suite failure) |
| 3 | [T-02.3 Build context filter](T-02.3_build-context-filter.md) | code | done (2026-11-06; same unrelated suite failure) |
| 4 | [T-02.4 Manual corrections](T-02.4_manual-corrections.md) | docs | done (2026-11-06) |

## Exit criteria

A Docker build of tts with no network fails with a clear message; a deploy against a service that reports a fallback prints a warning with the reason; the context copied for a build contains no `.env.*` file and no venv; `deployment/docs/DEPLOYMENT.md` matches `docs/deployment/deployment.md` of tts; the deployment test suite passes.

**State on 2026-11-06.** Met by tests, not yet by a real Docker run: a required voice fetch fails the build (the Dockerfile's shell is run with a real `sh`; the real build is T-03.4); a service that reports a fallback prints a warning with the reason (fake servers; the real case is T-03.2); the build context has no `.env.*` except the example and no venv (fake tree; the real image is T-03.1); the manual says the same as the tts documents about the packages, the baked voice, the health warning and the context. **Deployment suite: `317 passed, 2 skipped, 1 failed`.** The failure, `tests/test_compat.py::test_the_real_workspace_is_compatible`, is not from this epic: `camera_microservice/vendor/` still bundles contracts 0.15.0 while every other service has 0.16.0. This exit criterion therefore stays unmet until the maintainer bundles 0.16.0 into camera (or accepts the failure).
