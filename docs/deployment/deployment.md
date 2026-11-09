# Deployment

How the service is installed and run. Checked on 2026-11-06 against `requirements*.txt`, `scripts/`, and `deployment/config/catalogue.toml` of the workspace. The deployment tool and its manual ([`deployment/docs/DEPLOYMENT.md`](../../../deployment/docs/DEPLOYMENT.md)) are the source of truth for venvs, start order and the machine layout; this page records what is specific to tts.

## Facts for the deployment tool

| Item | Value |
|---|---|
| Repository / branch | `tts_microservice`, `feature_ai_claude_2` |
| Port | `8002` (`SERVICE_PORT`) |
| Readiness | `GET /available` |
| Requirements | `requirements.windows.txt`, `requirements.linux.txt`: **runtime only** (identical today); the tool installs only these. Tests and tooling are in `requirements-dev.txt`, never installed by the tool |
| Libraries | `shared-logging` (editable checkout), `contracts` (wheel in `vendor/`) |
| System packages (Debian / Raspberry Pi OS) | `espeak-ng` and `libespeak-ng1` (`espeak-ng-data` follows as a dependency), for the `espeak` engine and the pyttsx3 fallback. **Changed on 2026-11-06 from `espeak`, `espeak-data` and `libespeak1`:** in the Docker image (Debian bookworm) the old packages made the pyttsx3 fallback fail (`SetVoiceByName failed ... gmw/en`, debt D-11) while the `espeak` engine worked; with the espeak-ng packages both work (T-03.2). The `espeak` engine prefers `espeak-ng` when installed; the default Piper voice does not need them, it brings its own espeak-ng. Same wording as `deployment/docs/DEPLOYMENT.md` |
| `prepare` | `scripts/fetch_voice.py`, after the `.env` is written (deploy, update, rollback). A failure only warns |
| Hardware | none |
| Consumed by | Brain (`TTS_BASE_URL`) |

## By hand

```powershell
python -m venv windows            # Python 3.11 to 3.14; the venv folder keeps this name on Linux too
windows\Scripts\python.exe -m pip install -r requirements.windows.txt
copy .env.example .env            # adjust SERVICE_HOST for another machine; no secrets
windows\Scripts\python.exe scripts\fetch_voice.py   # about 60 MB, once
windows\Scripts\python.exe main.py
```

On Linux the interpreter is `windows/bin/python` and the requirements file `requirements.linux.txt`.

To run the tests, add the development file to the same venv: `windows\Scripts\python.exe -m pip install -r requirements-dev.txt` (pytest, `httpx` for the test client, ruff, black, mypy). Then `windows\Scripts\python.exe -m pytest`. A deployed install does not have them, by design.

## The Piper voice

About 60 MB, in neither git (`models/` is ignored) nor pip. `fetch_voice.py` reads the same settings as the service, does nothing when `TTS_ENGINE` is not `piper` or the voice already loads, otherwise downloads into a temporary folder, loads it once, and moves it into place (config file last). Exit code `0` = ready or not needed, `1` = could not fetch (a failure prints `Could not fetch Piper voice <name>: <error>` and the hint that the service will start with the pyttsx3 voice, both on stderr); `--voice <name>` fetches that voice even when `TTS_ENGINE` is not `piper`. Both codes and the atomic move are pinned by `tests/scripts/test_fetch_voice.py` (no network, no real model). **Never download at start**: Brain's preflight waits only 60 s (ADR-006).

Without the voice the service logs `Piper unavailable; falling back to pyttsx3`, speaks with the old voice, and `GET /available` answers `is_available: true` with a `reason` that starts with `fallback:`. **Check `reason` and the log after a deploy**: a missing voice is a warning, not a failure. The deployment tool shows the `reason` since 2026-11-06 (T-02.2): `deploy`, `start`, `update` and `status` print `healthy and available, warning: fallback: pyttsx3 instead of piper (...)` instead of a plain `healthy and available`, and still succeed. Tested against fake servers; seen against a real fallback in a Docker container (T-03.2, 2026-11-06).

## Verification after a deploy

1. `GET /available` returns `is_available: true` **and `reason: null`**. A `reason` starting with `fallback:` means the pyttsx3 voice is speaking instead of Piper (ADR-008): fix the cause it names (usually `python scripts/fetch_voice.py`, or deploy again) and restart. With the deployment tool, `status` shows the same text after `healthy and available, warning:`.
2. The log shows `Piper voice loaded` (not the fallback line) and `TtsService initialized` with `engine=PiperSpeechSynthesis`.
3. `POST /process/batch?text=hello&sample_rate=24000` returns audio; `scripts/render_samples.py` writes WAVs to `models/samples/` for a listening check.

## Docker

The generic `deployment/docker/service.Dockerfile` runs `prepare` while building, so the voice is baked into the image. **Built and run on amd64 on 2026-11-06 (T-03.1, T-03.2); arm64 has not been tried (T-03.3).** A second image, built from the working tree through the tool's own context code (652 MB, Python 3.12.16, contracts 0.16.0, runtime packages only), was started with `oblivion.py start` (`docker run ... -p 127.0.0.1:8002:8002 --mount ...env,target=/app/.env,readonly`): `Piper voice loaded`, `/available` `is_available: true` with `reason: null`, `/process/batch` 24 kHz mono audio (also on the host's LAN address; not from another machine), `status` plain `healthy and available`. With a missing voice in the mounted env it stayed available with the fallback `reason`, spoke with pyttsx3 (49,356 bytes for "hello") and the tool printed `healthy and available, warning: fallback: pyttsx3 instead of piper (...)` and exited 0, after the `apt` list was changed to the espeak-ng packages (before that the pyttsx3 fallback could not start in the image, D-11). The rest of this paragraph describes the first build (T-03.1), from the pushed commit with the old `apt` list. The build was done on Docker Desktop 29.5.2 (`docker --context desktop-linux`), from a clean clone of the pushed commit `54a6259` (so without the uncommitted work of the tasks), with the arguments the tool generates, `--no-cache`: it succeeded in 68 s, on `python:3.12-slim-bookworm` (Python 3.12.16); pip installed only binary wheels (no compilation) with fastapi 0.162.0, numpy 2.5.4, onnxruntime 1.31.1 and piper-tts 1.8.0; the required `prepare` step printed `Fetching Piper voice en_GB-alan-medium into /app/models (about 60 MB)` and `Piper voice en_GB-alan-medium is ready` (7.7 s); `/app/models` holds `en_GB-alan-medium.onnx` (63,201,294 bytes) and its `.onnx.json`; the only env-type file in `/app` is `.env.example`; the image is 792 MB on disk (236 MB of content). That image still contains pytest, ruff, black, mypy and httpx and contracts 0.15.0, because the pushed commit still has the old requirements: the split (T-01.3) and contracts 0.16.0 are uncommitted. Changed in the deployment tool on 2026-11-06 (T-02.1), first built above; the failure case was run with Docker on 2026-11-06 (T-03.4: a nonexistent voice via `--build-arg PREPARE="scripts/fetch_voice.py --voice en_XX-nothing-medium"` and a refused connection via a dead `HTTPS_PROXY` each gave `docker build` exit 1 with the message below, and the `oblivion/tts:local` tag stayed on the old image; `--network none` is useless for this test because BuildKit then ignores the cached layers and fails in `apt`): the catalogue entry of tts has `prepare_required = true`, `docker build` receives `--build-arg PREPARE_REQUIRED=1`, and the Dockerfile fails the build when `fetch_voice.py` fails (it names the script, the exit code and "Check the network and build again"); other services still only warn, and a native deploy still only warns. The shell of that `RUN` line is covered by tests that run it with a real `sh`, and by the real builds above. The build context no longer carries `.env.*` (`.env.staging`, `.env.production`; `.env.example` stays), `testclear/`, `windows/`, `.venv/`, `.git/` or bytecode (T-02.3, tested with a fake tree; no image built). Building the image needs network unless the voice is already in the `models/` folder of the service tree that is copied into the context. An image that nevertheless starts on pyttsx3 (a different `TTS_PIPER_VOICE` set later in the mounted `.env`) reports it in `GET /available` (`reason`, ADR-008). Piper's ONNX runtime on arm64 is unverified (D-4); Python 3.12 installs on amd64 (above).

## Verified deployments

A real fresh-machine deploy of this service ran on Python 3.11 and Python 3.14 (workspace notes). The Piper droid voice was judged by ear and its defaults kept on 2026-11-06; the espeak robot voice was not. Findings of the deployment audit: [deployment_audit/tts.md](../deployment_audit/tts.md).

On 2026-11-06 (Windows 11, Python 3.14.2, T-01.1 and T-01.3): a lone clone does not install `requirements.windows.txt` without the sibling `shared-logging` folder (the tool strips `-e ../` lines and installs a wheel instead); a deploy with the tool into a scratch folder fetched the voice and came up on Piper; a clean venv with only the runtime file starts `main.py`, loads the Piper voice, and answers `/health`, `/available` and `/process/batch` (no pytest, ruff, black, mypy or httpx installed), and a clean venv with the runtime and development files passes the whole suite (157 tests). The same day, in Docker (amd64, Python 3.12.16, T-03.1): the image builds and holds the voice (see Docker above). Not verified: a running container, Linux or Raspberry Pi natively, arm64.
