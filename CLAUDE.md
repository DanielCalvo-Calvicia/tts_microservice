# CLAUDE.md: tts_microservice

Port **8002**. Python/FastAPI. Text to speech. Status: working, needs retest after recent changes. See `README.md` and `../CLAUDE.md`.

Current state (2026-11-11): branch `feature_ai_claude_2`. Last commit `fbec6c5` (2026-11-09, one commit ahead of `origin/feature_ai_claude_2`, not pushed) "TTS: report the fallback in /available, split the requirements, tests, task plan and documents": it holds the documentation (`docs/`), the fallback report in `GET /available` (ADR-008), the `fetch_voice.py` tests, the log assertions, the split of the dev requirements from the runtime ones, and the `contracts` 0.16.0 wheel in `vendor/`. The espeak engine (`543008f`, 2026-10-04) and the Piper engine (`6a2f3d2`) are in. The `deployment` repository holds its own side of the plan (`prepare_required`, the Dockerfile, the `espeak-ng` apt list: commit `abf0815`) and has other uncommitted edits unrelated to tts. **Uncommitted (2026-11-11, this repo):** the restructure to the layout of `stt_microservice` (three ports `TtsServicePort` / `TtsInboundPort` / `TtsOutboundPort`, `dtos/inbound` and `dtos/outbound`, the HTTP adapter split into `routes/`, `response/`, `errors/`, `helpers/`, one file per dependency in `composition_root/dependencies/`, `test_dtos.py` and `test_ports.py`; no behaviour change), `requirements-dev.txt` renamed `requirements.dev.txt`, `.engram/` deleted, and the documents brought in line with all of it. Tests: `170 passed, 1 warning` (2026-11-11; 157 on 2026-11-06 before the restructure). Verified on 2026-11-06 (Windows 11, Python 3.14): a deploy with the deployment tool into a scratch folder (voice fetched, Piper, `/available` true), a deliberate voice failure (the silent fallback, now reported in `reason`), a clean clone, and a runtime-only venv. Earlier fresh-machine deploys ran on Python 3.11 and 3.14 (see the deployment memory). The Piper droid sound was judged by ear and kept on 2026-11-06 (the espeak robot voice was not). Docker images built on amd64 with Python 3.12 hold the voice (T-03.1; one from the pushed commit, one from the working tree) and the working-tree image runs, answers and, with a missing voice, speaks on the pyttsx3 fallback and is reported by the tool as `healthy and available, warning: ...` (T-03.2); a build whose voice cannot be fetched fails with exit 1 and a clear message (T-03.4). That needed the tts `apt` list in the deployment catalogue changed from `espeak espeak-data libespeak1` to `espeak-ng libespeak-ng1` (debt D-11: the old packages broke pyttsx3 in the image). **Not verified:** access from another machine, Linux or Raspberry Pi natively, arm64 (see `docs/tasks/`), and a real round trip through Brain with a speaker. Ruff (28 findings from the microphone venv) and mypy are not clean or installed in this venv. Docs index: [README.md](README.md) (Documentation table); task plan: [docs/tasks/README.md](docs/tasks/README.md).

## MANDATORY: every change updates the documentation

**No change is finished until the documents that describe it are true again.** Do it in the same piece of work, not later, and say what you updated when you report the work.

| If you change... | Update, in the same change |
|---|---|
| Code, a package, a folder or a file name | [docs/architecture/architecture.md](docs/architecture/architecture.md) (layout and diagram), the layout of `README.md` |
| An environment variable, a default, a range | `.env.example`, the table of `README.md`, [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md); then `brain_microservice\windows\Scripts\python.exe deployment\scripts\env_inventory.py --write` from the workspace root |
| A route, an event, a field, a status code or an error | [docs/api/api.md](docs/api/api.md), the table of `README.md`, [docs/requirements/requirements.md](docs/requirements/requirements.md); the event itself goes into `contracts` first |
| Logging, probes, shutdown, resources | [docs/operations/monitoring.md](docs/operations/monitoring.md) |
| Auth, secrets, input limits, dependencies | [docs/security/security.md](docs/security/security.md) |
| Install steps, system packages, the voice, Docker, `catalogue.toml` entry | [docs/deployment/deployment.md](docs/deployment/deployment.md) and `deployment/docs/DEPLOYMENT.md` |
| A requirement (new, changed, done) | [docs/requirements/requirements.md](docs/requirements/requirements.md) and the status table of `README.md` |
| A decision (an engine, a protocol, a rule) | a new ADR in [docs/decisions/](docs/decisions/README.md) (or a dated note on the one it changes) and its row in the index |
| A known limit or debt (found, fixed) | the debt table of `docs/architecture/architecture.md` (keep the IDs) |
| The `contracts` wheel or the test count | `README.md` (Status, Development), this file, the architecture header |

How: use dated notes in ADRs (they are history); correct the text in the other documents (they describe the present); mark planned as planned and built as built, never claim something works that was not run; check the links still resolve; when documents and code disagree and you cannot tell which is right, ask the user.

## Role

Brain uploads text events and reads audio events back.

| Path | Use |
|---|---|
| `POST /process/stream/set` | Brain uploads text (NDJSON `TTS_INBOUND` events). Answers **202** with an ack stream (`stream_started`, then `input_completed` or `error`; schema `UPLOAD_ACK`). A non-NDJSON body is plain text, one utterance per line |
| `GET /process/stream/get` | Brain reads audio events (NDJSON, `TTS_OUTBOUND`); heartbeat every 15 s; waits if nothing was set yet |
| `POST /process/stream` | Single-request variant (text body, headerless PCM16 back; `sample_rate`, `channels` query params, default 22050 / 1) |
| `POST /process/batch?text=` | One text → base64 audio + `sample_rate` + `channels`; 400 on blank text |
| `GET /health`, `/available` | Liveness; engine readiness. `/available` carries `reason` (`null`, or `fallback: pyttsx3 instead of piper (...)` while the fallback speaks; `is_available` stays true, ADR-008) |

Errors: 400 blank text, 422 invalid/mismatching format, 502 engine failed, else 500.
Engines (`TTS_ENGINE`): **`piper`** (default; local neural voice `en_GB-alan-medium`, in-process ONNX, then `droid_voice.py`: pitch lift by resampling + brightness, comb echoes, ring mod, all numpy) **`espeak`** (a real robot voice: espeak or espeak-ng formant synthesis, one subprocess per sentence with the text on stdin, then `robot_voice.py`: ring modulation, sample-and-hold, bit crush; `infrastructure/outbound/espeak_speech/`; falls back to pyttsx3 when the program is missing) and `pyttsx3` (subprocess, temp WAVs; the **fallback** when the Piper voice file is missing or does not load, chosen in `composition_root/dependencies/speech_synthesis_dependency.py`). Env: `TTS_ENGINE`, `TTS_PIPER_VOICE/MODEL_DIR/SPEED`, `TTS_PITCH_SEMITONES`, `TTS_DROID_EFFECT`, `TTS_ESPEAK_COMMAND/VOICE/SPEED/PITCH/WORD_GAP_MS`, `TTS_ROBOT_EFFECT`, `TTS_SPEECH_RATE`, `TTS_VOICE_NAME`, `SERVICE_NAME/HOST/PORT`, `LOG_LEVEL`. **There is no OpenAI TTS engine in the code** (the `tts/set_configuration.py` and `init_outbound.py` contracts in `contracts` still describe one; they are unused).

The voice (about 60 MB) is NOT in git (`models/` is ignored) nor in pip. The deployment tool fetches it with `scripts/fetch_voice.py` (its `prepare` step in `config/catalogue.toml`, run after the `.env` is written; downloads to a temp folder, loads it, then moves it into place). Never download at service start: Brain's preflight waits only 60 s. Listening check: `scripts/render_samples.py` writes WAVs to `models/samples/`; the Piper droid values (pitch 2.0, strength 0.5) were judged by ear and kept on 2026-11-06; the espeak robot values are tuned on paper and by tests, not by ear.

## Layout

`main.py` → `main_flow/` → `composition_root/` → `application/` → `domain/` → `infrastructure/` (`outbound/piper_speech/`, `outbound/espeak_speech/`, `outbound/pyttsx3_speech/`). Same folders as `stt_microservice`: `application/dtos/{inbound,outbound}`, `application/ports/{inbound,service,outbound}` (`TtsInboundPort`, `TtsServicePort`, `TtsOutboundPort`), `infrastructure/inbound/http/{routes,response,errors,helpers}` (`http_handler.py` only wires the endpoints), one `*_dependency.py` per factory in `composition_root/dependencies/`. `tests/architecture/` pins the dependency rule, the DTO folders and the ports.

## Rules

- Events use `contracts.stream` (`TTS_INBOUND`/`TTS_OUTBOUND`, `TTS_INPUT_ACK`, an alias of `UPLOAD_ACK`) and the shared codec. Only Brain's TTS adapter reads the ack.
- Output is PCM16 mono in `bytes_base64`. TTS converts its engine output (both engines, `convert_pcm16`) to the sample rate and channels requested; Brain asks for 24 kHz. No other service converts audio.
- **Gotcha:** `testclear/` at the repo root is a whole Python venv (`Lib/site-packages`), not just scratch. Never build on it, and exclude it from every grep or glob.
- `contracts` comes from `vendor/contracts_microservice-<version>.whl` (0.16.0); refresh it with `contracts/scripts/bundle.py`.
- Ruff/mypy/black are configured in `pyproject.toml` but not installed in this venv. Do not bulk-fix lint unasked.
- The old `.engram/` notes were deleted on 2026-11-11 (as in stt). `.env.staging` and `.env.production` exist: do not open them.
- Never log or echo API keys.

## Commands

```powershell
& windows\Scripts\python.exe -m pip install -r requirements.dev.txt   # once: pytest, httpx, ruff, black, mypy (the tool installs only the runtime files)
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest
```
