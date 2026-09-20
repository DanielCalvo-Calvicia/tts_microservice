# TTS Microservice

HTTP service that turns text into 16-bit PCM audio with the local `pyttsx3` engine (Windows SAPI5).

## Run

```bash
pip install -r requirements.windows.txt
python main.py
```

Configuration is read from the environment (a `.env` file is loaded if present); see `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_NAME` | `TTS Microservice` | API title / log name |
| `SERVICE_HOST` | `127.0.0.1` | Bind address |
| `SERVICE_PORT` | `8002` | Bind port |
| `LOG_LEVEL` | `INFO` | Read by the shared logging module; `TRACE`→DEBUG, `WARN`→WARNING also accepted |
| `LOG_FORMAT`, `SERVICE_NAME`, `TRACE_EXPORT_*` | see docs | Also read by the shared logging module: [`shared-logging/docs/logging.md`](../shared-logging/docs/logging.md) |
| `TTS_SPEECH_RATE` | `140` | Speech speed (words per minute) |
| `TTS_VOICE_NAME` | `Zira` | Preferred voice (name contains this); otherwise the first English voice |

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/available` | `{"is_available": bool}`: whether pyttsx3 starts |
| POST | `/process/stream` | Body is text, one utterance per non-empty line. Streams the PCM back as it is produced |
| POST | `/process/stream/set` | Same body. Answers `202` at once and keeps synthesizing in the background |
| GET | `/process/stream/get` | Streams the audio of the last `set`. Waits if there is none yet; ends when that stream ends |
| POST | `/process/batch?text=...` | Synthesizes `text` and returns `{"audio_data_base64", "sample_rate", "channels"}`. `400` if the text is blank |

Stream endpoints take `sample_rate` (22050) and `channels` (1) as query parameters; both must be positive.
The engine writes its own WAV format, so they are echoed back but not applied to the audio.

JSON responses use the envelope `action / status / status_code / message / timestamp / data`.
Every failure currently returns HTTP 500, except blank text (400).

A new `set` replaces the previous one: its audio queue is dropped and readers of the old stream see it end.

## Project layout

```text
main.py            entry point (calls main_flow)
main_flow/         startup (logging: shared `shared_logging` package)
composition_root/  the only place concrete adapters are wired together
infrastructure/    config, HTTP (inbound) and pyttsx3 (outbound) adapters
application/       use-case service, ports, DTOs, application errors
domain/            audio format value object, text rules
```

Dependencies point inward only (`infrastructure → application → domain`); `tests/architecture/`
enforces this.

## Development

```bash
pytest                    # unit + architecture tests (no speech engine needed)
mypy .
ruff check .
black --check .
python tests/simple.py    # end-to-end against a running service
```

Architecture: [docs/architecture/architecture.md](docs/architecture/architecture.md).
The previous layout is documented in [docs/old/](docs/old/).
