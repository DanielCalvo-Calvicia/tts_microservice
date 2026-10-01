# TTS Microservice

HTTP service that turns text into 16-bit PCM audio. The default engine is **Piper** (a local neural voice,
`en_GB-alan-medium`) with a light "droid" effect chain (pitch lift, brightness, metallic resonance). The old
`pyttsx3` engine (Windows SAPI5 / espeak) is the fallback.

## Run

```bash
pip install -r requirements.windows.txt
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
| `TTS_ENGINE` | `piper` | `piper` or `pyttsx3`; anything else fails at startup with a `ValueError` |
| `TTS_PIPER_VOICE` | `en_GB-alan-medium` | Piper voice name |
| `TTS_PIPER_MODEL_DIR` | `models` | Folder with `<voice>.onnx` and `<voice>.onnx.json` (relative to the service) |
| `TTS_PIPER_SPEED` | `1.0` | Pace multiplier (`1.1` = a little brisker); must be > 0 |
| `TTS_PITCH_SEMITONES` | `2.0` | Pitch lift, the pace is kept (`0` = as recorded) |
| `TTS_DROID_EFFECT` | `0.5` | Effect strength: `0` off, `0.5` light, `1` obvious, `2` maximum; must be >= 0 |
| `TTS_SPEECH_RATE` | `140` | pyttsx3 only: words per minute |
| `TTS_VOICE_NAME` | `Zira` | pyttsx3 only: preferred voice (name contains this); otherwise the first English voice |

`LOG_FORMAT`, `LOG_OUTPUT`, `ENVIRONMENT` and `TRACE_EXPORT_*` are also read by the shared logging package, not by this service: see [`shared-logging/docs/logging.md`](../shared-logging/docs/logging.md). The table equals `.env.example` and `ServerConfig`/`TtsConfig` in `infrastructure/config/`. There is no OpenAI TTS engine in the code.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/available` | `{"is_available": bool}`: whether the engine works (Piper once its voice is loaded, else whether pyttsx3 starts) |
| POST | `/process/stream` | Body is text, one utterance per non-empty line. Streams headerless PCM16 back as it is produced (labelled `audio/wav`) |
| POST | `/process/stream/set` | Brain's upload. With `Content-Type: application/x-ndjson` the body is a live stream of `TTS_INBOUND` events (`partial` text pieces, `completed`); the answer is `202` and stays open as an ack stream: `stream_started`, then `input_completed` when the sender ended, or a recoverable `error`. Any other body is plain text (one utterance per line) and gets a `202` JSON envelope; synthesis continues in the background |
| GET | `/process/stream/get` | The audio of the last `set` as `TTS_OUTBOUND` NDJSON events (`application/x-ndjson`): `stream_started` (`sample_rate`, `channels`), per text some `partial` (`bytes_base64`) and one `completed`; a recoverable `error` event (`synthesis_failed`) if a text fails; `heartbeat` every 15 s when idle. Waits if there is no `set` yet. Query `sample_rate`/`channels` may be repeated but must match the `set` (else 422); `keep_open_after_completed` is accepted and ignored |
| POST | `/process/batch?text=...` | Synthesizes `text`; `data` is `ProcessBatchResponse{audio_data_base64, sample_rate, channels}`. `400` if the text is blank |

Stream endpoints take `sample_rate` (22050) and `channels` (1) as query parameters; both must be positive.
The audio is converted to that rate and channel count before it leaves the service.

JSON responses use the envelope `action / status / status_code / message / timestamp / data` (`contracts.api.common.envelope.ApiEnvelope`). Failures map to HTTP status codes in `infrastructure/inbound/http/http_error_mapper.py`: `400` blank text, `422` invalid audio format or one that differs from the stream's, `502` the speech engine failed, `500` anything else. There is no authentication.

A new `set` replaces the previous one: its audio queue is dropped and readers of the old stream see it end.

## Project layout

```text
main.py            entry point (calls main_flow)
main_flow/         startup (logging: shared `shared_logging` package)
composition_root/  the only place concrete adapters are wired together
infrastructure/    config, HTTP (inbound), Piper and pyttsx3 (outbound) adapters
application/       use-case service, ports, DTOs, application errors
domain/            audio format value object, text rules
```

Dependencies point inward only (`infrastructure → application → domain`); `tests/architecture/`
enforces this.

## Development

```powershell
windows\Scripts\python.exe -m pytest        # unit + architecture tests (no speech engine needed)
windows\Scripts\python.exe tests\simple.py  # end-to-end against a running service
```

Result on 2026-10-01: `100 passed, 1 warning` in 14 s (the warning is a Starlette `TestClient` deprecation notice). `ruff`, `mypy` and `black` are configured in `pyproject.toml` but not installed in this venv; the microphone venv's ruff reports 28 findings here (6 auto-fixable), not fixed on purpose. `tests/simple.py` and listening to the voice (the effect values were tuned by tests, not by ear) were not done in this pass.

Architecture: [docs/architecture/architecture.md](docs/architecture/architecture.md).
The previous layout is documented in [docs/old/](docs/old/).
