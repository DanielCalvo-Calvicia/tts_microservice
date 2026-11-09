# TTS Microservice

HTTP service that turns text into 16-bit PCM audio. The default engine is **Piper** (a local neural voice,
`en_GB-alan-medium`) with a light "droid" effect chain (pitch lift, brightness, metallic resonance). `espeak`
(a formant machine voice with a robot effect) is an option and the old `pyttsx3` engine (Windows SAPI5 / espeak)
is the fallback. Port **8002**, Python / FastAPI, no hardware.

## Status

Working, needs a retest after the recent changes. Branch `feature_ai_claude_2`, `contracts` 0.16.0 bundled (uncommitted; the last commit has 0.15.0), 157 tests pass (2026-11-06). Not done: judging the `espeak` robot voice by ear (the Piper droid voice was judged and its defaults kept on 2026-11-06), Linux/Raspberry Pi runs and a running Docker container (an image builds on amd64 with Python 3.12), ruff/mypy clean-up. Full list: [known debt](docs/architecture/architecture.md#known-remaining-debt).

| Area | State |
|---|---|
| HTTP API (`set`/`get` streams, `stream`, `batch`, `health`, `available`) | Built, tested |
| Piper voice with droid effect | Built; effect values judged by ear and kept (2026-11-06) |
| espeak robot voice | Built, tested with fakes; needs `espeak-ng` installed |
| pyttsx3 fallback | Built |
| Tracing and structured logs | Built (`shared_logging`) |
| Authentication | None; the network limits access |

## Run

```bash
pip install -r requirements.windows.txt     # runtime only (Linux: requirements.linux.txt); tests and tooling: requirements-dev.txt
python scripts/fetch_voice.py     # downloads the Piper voice (about 60 MB) into models/, once
python main.py
```

The deployment tool runs `scripts/fetch_voice.py` for you. Without the voice file the service logs
`Piper unavailable; falling back to pyttsx3` and speaks with the old voice, so it never fails to start.
`python scripts/render_samples.py` writes listening samples (plain, pitch only, droid, strong) to `models/samples/`.
Configuration is read from the environment (a `.env` file is loaded if present); see `.env.example`. The default bind address is `127.0.0.1`; set `SERVICE_HOST` (for example `0.0.0.0`) when Brain runs on another machine. Use the service's own venv (`windows\Scripts\python.exe`).

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_NAME` | `TTS Microservice` | API title / log name |
| `SERVICE_HOST` | `127.0.0.1` | Bind address |
| `SERVICE_PORT` | `8002` | Bind port |
| `LOG_LEVEL` | `INFO` | Read by the shared logging module (`TRACE`, `DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`, `CRITICAL`) |
| `TTS_ENGINE` | `piper` | `piper`, `espeak` (a real machine voice, formant synthesis) or `pyttsx3`; anything else fails at startup with a `ValueError` |
| `TTS_ESPEAK_COMMAND` | empty | espeak only: the program; empty = `espeak-ng` if installed, else `espeak` |
| `TTS_ESPEAK_VOICE` | `en` | espeak only: voice and variant (`en+m3`, `en+klatt3`, `en+croak` ...; `espeak --voices` lists them) |
| `TTS_ESPEAK_SPEED` | `150` | espeak only: words per minute, 80-390 |
| `TTS_ESPEAK_PITCH` | `30` | espeak only: 0-99, lower is deeper |
| `TTS_ESPEAK_WORD_GAP_MS` | `20` | espeak only: extra silence between words, in milliseconds |
| `TTS_ROBOT_EFFECT` | `1.0` | espeak only: ring modulation, sample hold and bit crush: `0` off, `1` default, `3` maximum |
| `TTS_PIPER_VOICE` | `en_GB-alan-medium` | Piper voice name |
| `TTS_PIPER_MODEL_DIR` | `models` | Folder with `<voice>.onnx` and `<voice>.onnx.json` (relative to the service) |
| `TTS_PIPER_SPEED` | `1.0` | Pace multiplier (`1.1` = a little brisker); must be > 0 |
| `TTS_PITCH_SEMITONES` | `2.0` | Pitch lift, the pace is kept (`0` = as recorded) |
| `TTS_DROID_EFFECT` | `0.5` | Effect strength: `0` off, `0.5` light, `1` obvious, `2` maximum; must be >= 0 |
| `TTS_SPEECH_RATE` | `140` | pyttsx3 only: words per minute |
| `TTS_VOICE_NAME` | `Zira` | pyttsx3 only: preferred voice (name contains this); otherwise the first English voice |

`LOG_FORMAT`, `LOG_OUTPUT`, `ENVIRONMENT` and `TRACE_EXPORT_*` are also read by the shared logging package, not by this service: see [`shared-logging/docs/logging.md`](../shared-logging/docs/logging.md). The table equals `.env.example` and `ServerConfig`/`TtsConfig` in `infrastructure/config/`; the full description with ranges is in [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md). There is no OpenAI TTS engine in the code.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/available` | `{"is_available": bool, "reason": str or null}`: whether the engine works (Piper once its voice is loaded, else whether pyttsx3 starts). `reason` is `null` on the configured engine and a `fallback: pyttsx3 instead of piper (...)` note when the fallback speaks; `is_available` stays `true` then (ADR-008) |
| POST | `/process/stream` | Body is text, one utterance per non-empty line. Streams headerless PCM16 back as it is produced (labelled `audio/wav`) |
| POST | `/process/stream/set` | Brain's upload. With `Content-Type: application/x-ndjson` the body is a live stream of `TTS_INBOUND` events (`partial` text pieces, `completed`); the answer is `202` and stays open as an ack stream: `stream_started`, then `input_completed` when the sender ended, or a recoverable `error`. Any other body is plain text (one utterance per line) and gets a `202` JSON envelope; synthesis continues in the background |
| GET | `/process/stream/get` | The audio of the last `set` as `TTS_OUTBOUND` NDJSON events (`application/x-ndjson`): `stream_started` (`sample_rate`, `channels`), per text some `partial` (`bytes_base64`) and one `completed`; a recoverable `error` event (`synthesis_failed`) if a text fails; `heartbeat` every 15 s when idle. Waits if there is no `set` yet. Query `sample_rate`/`channels` may be repeated but must match the `set` (else 422); `keep_open_after_completed` is accepted and ignored |
| POST | `/process/batch?text=...` | Synthesizes `text`; `data` is `ProcessBatchResponse{audio_data_base64, sample_rate, channels}`. `400` if the text is blank |

Stream endpoints take `sample_rate` (22050) and `channels` (1) as query parameters; both must be positive.
The audio is converted to that rate and channel count before it leaves the service.

Details of every route, event and status: [docs/api/api.md](docs/api/api.md). JSON responses use the envelope `action / status / status_code / message / timestamp / data` (`contracts.api.common.envelope.ApiEnvelope`). Failures map to HTTP status codes in `infrastructure/inbound/http/http_error_mapper.py`: `400` blank text, `422` invalid audio format or one that differs from the stream's, `502` the speech engine failed, `500` anything else. There is no authentication.

A new `set` replaces the previous one: its audio queue is dropped and readers of the old stream see it end.

## Project layout

```text
main.py            entry point (calls main_flow)
main_flow/         startup (logging: shared `shared_logging` package)
composition_root/  the only place concrete adapters are wired together
infrastructure/    config, HTTP (inbound), Piper, espeak and pyttsx3 (outbound) adapters
scripts/           fetch_voice.py (deploy-time voice download), render_samples.py (listening samples)
docs/              architecture, API, configuration, decisions (ADRs), deployment, monitoring, requirements, security
application/       use-case service, ports, DTOs, application errors
domain/            audio format value object, text rules
```

Dependencies point inward only (`infrastructure → application → domain`); `tests/architecture/`
enforces this.

## Development

```powershell
windows\Scripts\python.exe -m pip install -r requirements-dev.txt   # once, next to requirements.windows.txt: pytest, httpx, ruff, black, mypy
windows\Scripts\python.exe -m pytest        # unit + architecture tests (no speech engine needed)
windows\Scripts\python.exe tests\simple.py  # end-to-end against a running service
```

Result on 2026-11-06: `157 passed, 1 warning` in 15 s (136 on 2026-11-05; 5 new tests cover the fallback `reason` of `/available`, 16 cover the exit codes of `scripts/fetch_voice.py`). The warning is a Starlette `TestClient` deprecation notice. `ruff`, `mypy` and `black` are configured in `pyproject.toml` but not installed in this venv; the microphone venv's ruff reported 28 findings here on 2026-10-01 (6 auto-fixable), not fixed on purpose. `tests/simple.py` was not run in this pass. The Piper droid voice was listened to on 2026-11-06 (T-01.1.5) and its defaults kept; the `espeak` robot voice was not.

## Documentation

| Document | Content |
|---|---|
| [docs/architecture/architecture.md](docs/architecture/architecture.md) | Layers, layout, data flow, changes, known debt (D-1 to D-11) |
| [docs/api/api.md](docs/api/api.md) | Routes, events, audio format, errors |
| [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md) | Every variable, default and range |
| [docs/operations/monitoring.md](docs/operations/monitoring.md) | Probes, shutdown, logs, tracing, resources |
| [docs/security/security.md](docs/security/security.md) | What is protected, what is not |
| [docs/deployment/deployment.md](docs/deployment/deployment.md) | Install, the Piper voice, verification, Docker |
| [docs/requirements/requirements.md](docs/requirements/requirements.md) | Functional and non-functional requirements with status |
| [docs/decisions/](docs/decisions/README.md) | Architecture decision records (ADR-001 to ADR-008) |
| [docs/deployment_audit/tts.md](docs/deployment_audit/tts.md) | Deployment audit findings (with a dated update of what the tasks found) |
| [docs/tasks/README.md](docs/tasks/README.md) | The task plan for the new deployment: board, order ([ORDER.md](docs/tasks/ORDER.md)), facts |
| [CLAUDE.md](CLAUDE.md) | Rules for working in the repository, including the mandatory update of the documentation |
| [docs/old/](docs/old/) | The previous layout; superseded, do not trust |
