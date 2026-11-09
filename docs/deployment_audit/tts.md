# tts_microservice (port 8002)

Verified against the code on 2026-11-05 (tts suite: 136 passed). Tags: [C] read in code or config, [D] documented elsewhere, [U] not verified.

## Role
Text to speech: Piper neural voice `en_GB-alan-medium` plus a numpy "droid" effect. Other engines: `espeak` (formant synthesis plus a robot effect) and `pyttsx3` (the fallback). Brain uploads text and reads audio back (PCM16 mono, converted to the sample rate Brain asks for, 24 kHz). Endpoints: `/process/stream/{set,get}`, `/process/stream`, `/process/batch`, `/health`, `/available`. [C]

## Dependencies
- **Python packages:** fastapi, uvicorn, python-dotenv, pydantic, pyttsx3, numpy, piper-tts (`>=1.8.0,<2`, resolves to 1.8.0 with onnxruntime 1.30.0; needs Python 3.9 or newer). `httpx` is listed but nothing in the service imports it. Also pytest, ruff, black and mypy (see Problems). [C]
- **Non-pip libraries:** `shared-logging` (`-e ../shared-logging` in the requirements files; the deploy tool strips `-e ../` lines and installs a wheel from `libs/`) and the vendored `contracts` 0.15.0 wheel in `vendor/`. [C]
- **System packages (`apt` in `catalogue.toml`):** `espeak`, `espeak-data`, `libespeak1`. Needed for two things: the pyttsx3 fallback on Linux (`libespeak1`) and the `espeak` engine (`espeak` or `espeak-ng` on PATH, `espeak-ng` preferred). The Piper path needs none: the piper package bundles espeak-ng data and its own bridge. [C]

## Hardware
None.

## Portability
- The voice (about 60 MB) is in neither git (`models/` is ignored) nor pip. The deploy tool fetches it with `scripts/fetch_voice.py` after the `.env` is written. [C]
- `fetch_voice.py` downloads to a temp folder, loads the voice, and only then moves it into place. It exits 0 when the voice is already there or the engine is not piper, and 1 on any download error. No test covers it. [C]
- A fresh deploy ran on Python 3.11 and 3.14 [D]. The Docker image defaults to Python 3.12, which has not been exercised [U]. The sound has not been judged by ear.
- onnxruntime (via piper) is architecture-specific [U on arm64].
- Windows and Linux use identical requirements files. [C]

## Local
Works. If the voice is missing or does not load, the service logs `Piper unavailable; falling back to pyttsx3` and starts on pyttsx3. The same happens for `espeak` when the program is missing. [C]

## Docker
Feasible. Everything below is read from `deployment/docker/service.Dockerfile` and `docker_runtime.py`; no image has been built [U].

- The generic Dockerfile runs `prepare` (`python scripts/fetch_voice.py`) while building, with default settings, so the **default** voice is baked into the image. A different `TTS_PIPER_VOICE` set later (the `.env` is bind-mounted at runtime) finds no voice and silently falls back to pyttsx3.
- The deploy tool forces `SERVICE_HOST=0.0.0.0` for Docker (`env_resolution.py`), so the `127.0.0.1` default in `.env.example` and the README does not matter there.
- The build context copy skips only `.git`, `__pycache__`, `.venv`, `windows`, `.env` and `*.pyc`. Build from a clean clone: a working folder with `testclear/` or `.env.staging` would be copied into the image.
- The `apt` packages are installed in the image. See Dependencies for why they are not only for the fallback.
- No `HEALTHCHECK` in the Dockerfile; the deploy tool waits on `/available`.

## Configuration
`TTS_ENGINE`, `TTS_PIPER_*`, `TTS_PITCH_SEMITONES`, `TTS_DROID_EFFECT`, `TTS_ESPEAK_*`, `TTS_ROBOT_EFFECT`, `TTS_SPEECH_RATE`, `TTS_VOICE_NAME`, `SERVICE_*`, `LOG_LEVEL`. A relative `TTS_PIPER_MODEL_DIR` resolves from `SERVICE_ROOT = Path(__file__).resolve().parents[2]` (`tts_config.py:7`), so the service needs its folder layout (fine at `/app`). [C]

## Problems
1. **A failed voice download is silent in Docker.** `service.Dockerfile` runs `prepare` with `|| echo warning`, so the build succeeds and the image falls back to pyttsx3. The native deploy also only warns, by design (a machine offline during deploy must still come up).
2. **Readiness cannot tell Piper from the fallback.** `/available` is always true for Piper, and also true for the pyttsx3 fallback when espeak is installed. The deploy tool's readiness wait and any "is it up" check therefore pass on a silent fallback. `AvailabilityResponse` already has an optional `reason` field that tts never sets.
3. **Dev tools at runtime.** pytest, ruff, black and mypy are in both requirements files; `httpx` is unused.
4. **Never download at service start.** Brain's preflight waits only 60 s. Correct as is; keep it.
5. **Piper on arm64 is unverified** [U], and so is Python 3.12 (the Docker default).
6. **`fetch_voice.py` has no test.** Its two exit codes (0 ready or not needed, 1 could not fetch) are enough for a strict Docker build, because engines other than Piper already exit 0. What is missing is the policy of which services must fail the build, and a test that pins the exit codes. *(Correction of an earlier version of this audit, which called the single failure code a problem.)*

## Recommended changes
1. **Fail the Docker build when the voice is requested and missing.** The change belongs in the deployment repo (`service.Dockerfile`, the catalogue and `docker_runtime.py`), not in tts: a per-service flag in the catalogue, so the native path and other services keep warning.
2. **Make the fallback visible.** Use the existing `reason` of `AvailabilityResponse` on `/available` (`is_available` stays true, because Brain's preflight must not fail), and show it in the deploy tool's `status`. The alternative is new fields in `contracts`; that is a decision for the maintainer.
3. **Split the requirements** into runtime and dev files, and drop `httpx` from the runtime file if confirmed unused.
4. **Verify `piper-tts` and onnxruntime install on aarch64**, and the image on Python 3.12.
5. **Docs:** say the `apt` packages also serve the `espeak` engine (the system packages table of `DEPLOYMENT.md` calls them "fallback only"). Update `CLAUDE.md` (contracts 0.15.0, test count).

## Tests
- Existing: 136 pass. `tests/composition_root/test_engine_selection.py` already covers a missing voice, a corrupt voice and a missing espeak falling back to pyttsx3.
- **Add:** log assertions for each fallback, tests for `fetch_voice.py`, and a test for the engine report once it exists.
- **Docker, on amd64 and arm64:** build, then check the container log for `Piper voice loaded` and the absence of `Piper unavailable; falling back`. Do not rely on `/available` true or on sample rate and channels alone: both are the same on the fallback. Then synthesize a sentence and check the audio is not empty.

The work items that follow from this audit are in [../tasks/README.md](../tasks/README.md).

## Update 2026-11-06 (what the tasks found or changed; the text above is the audit as written on 2026-11-05)

- **Dependencies, Problem 3:** `httpx` is not imported by the service but is needed by the tests (`fastapi.testclient`); it moved to `requirements-dev.txt` with pytest, ruff, black and mypy. Runtime and dev requirements are split (T-01.3, verified in two clean venvs). Versions are still lower bounds.
- **Problem 2 (readiness cannot tell Piper from the fallback), service half:** `GET /available` now carries a path-free `reason` (`fallback: pyttsx3 instead of piper (...)`) while `is_available` stays `true` (ADR-008, T-01.2.2). The deployment tool reads it since T-02.2 (the same day): `deploy`, `start`, `update` and `status` print `healthy and available, warning: <reason>`; tested with fake servers, not yet against a real fallback.
- **Problem 1 (silent failure):** reproduced on a real native deploy with a voice name that does not exist (T-01.1.4): `deploy` warned, exited 0 and ended with `healthy and available`; the log had the error line; `/available` was `true` with audio from pyttsx3 (69,776 bytes against 30,286 for the same word on Piper). A second deploy with the voice repaired it. The Docker half is not built (T-02.1) and not run.
- **Problem 6 (`fetch_voice.py` has no test):** 16 tests now pin its two exit codes and the atomic move (T-01.2.3); all 11 one-line mutations tried on the script are caught.
- **Tests:** 157 pass (136 on 2026-11-05). The three fallback paths and the happy path are asserted in the log (T-01.2.4).
- **Portability:** a native deploy on Windows with Python 3.14.2 was run from a clean clone path and with the tool (T-01.1). Later the same day (T-03.1) a Docker image was built on amd64 with Python 3.12.16: only binary wheels were installed, the required voice step succeeded, and the image holds the voice (792 MB on disk). Linux and Raspberry Pi natively, arm64 and a running container are still not run.
- **Recommended change 1 (fail the Docker build), written the same day in the `deployment` repository (T-02.1):** a per-service key `prepare_required` in `config/catalogue.toml` (true for tts), passed as the build argument `PREPARE_REQUIRED=1`; the Dockerfile then fails the build with the script, its exit code and "Check the network and build again". The native path and other services still only warn. Covered by tests (the Dockerfile's shell is run with a real `sh`); the success path was seen in a real `docker build` (T-03.1: the required step ran and the build passed); the failure case was run too (T-03.4): a nonexistent voice and a refused connection each ended the build with exit 1 and the message above, and the image tag was not touched. A build on a really offline machine was not run.
- **Build context (Docker section, third bullet), same day (T-02.3):** the copy for a build now leaves out `.env.*` except `.env.example`, and `testclear/`, and keeps the old exclusions; tested on a fake tree with a mutation check. The audit's worry was a working folder: a clone made by the tool cannot hold `.env.staging` or `.env.production` (they are untracked and git-ignored in tts and the other service repositories; only stepper tracks a `.env`, which was already excluded).
- **Recommended change 5 (docs), same day (T-02.4):** the system packages and voices rows of `deployment/docs/DEPLOYMENT.md` and the comment on the `apt` line of the catalogue said the `espeak` packages serve the pyttsx3 fallback **and** the `espeak` engine (words only; no package list changed). **Corrected later the same day (T-03.2):** in the Docker image the old `espeak` packages served the `espeak` engine but the pyttsx3 fallback FAILED on them (debt D-11); the audit's reading of the `apt` list was incomplete. The catalogue's `apt` list for tts is now `espeak-ng`, `libespeak-ng1`, and a rebuilt image speaks on the fallback (see the Docker section of the deployment document). The part about `CLAUDE.md` (contracts version, test count) was done in T-01.4.
- **Not changed by any task so far:** nothing of the audit's recommendations is left unwritten; what is left is proof by running: Docker and arm64 (T-03).
- **Update 2026-11-09:** the maintainer postponed the Raspberry Pi and arm64 checks (T-03.3) until the services work fully on Windows. Problem 5 (Piper and onnxruntime on arm64) therefore stays unverified on purpose. T-03.5 recorded what was run on amd64.
