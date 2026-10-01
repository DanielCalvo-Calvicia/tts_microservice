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
Configuration is read from the environment (a `.env` file is loaded if present); see `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `SERVICE_NAME` | `TTS Microservice` | API title / log name |
| `SERVICE_HOST` | `127.0.0.1` | Bind address |
| `SERVICE_PORT` | `8002` | Bind port |
| `LOG_LEVEL` | `INFO` | Read by the shared logging module; `TRACE`→DEBUG, `WARN`→WARNING also accepted |
| `LOG_FORMAT`, `SERVICE_NAME`, `TRACE_EXPORT_*` | see docs | Also read by the shared logging module: [`shared-logging/docs/logging.md`](../shared-logging/docs/logging.md) |
| `TTS_ENGINE` | `piper` | `piper` or `pyttsx3` |
| `TTS_PIPER_VOICE` | `en_GB-alan-medium` | Piper voice name |
| `TTS_PIPER_MODEL_DIR` | `models` | Folder with `<voice>.onnx` and `<voice>.onnx.json` (relative to the service) |
| `TTS_PIPER_SPEED` | `1.0` | Pace multiplier (`1.1` = a little brisker) |
| `TTS_PITCH_SEMITONES` | `2.0` | Pitch lift, the pace is kept (`0` = as recorded) |
| `TTS_DROID_EFFECT` | `0.5` | Effect strength: `0` off, `0.5` light, `1` obvious, `2` maximum |
| `TTS_SPEECH_RATE` | `140` | pyttsx3 only: words per minute |
| `TTS_VOICE_NAME` | `Zira` | pyttsx3 only: preferred voice (name contains this); otherwise the first English voice |

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/available` | `{"is_available": bool}`: whether the engine works (Piper once its voice is loaded, else whether pyttsx3 starts) |
| POST | `/process/stream` | Body is text, one utterance per non-empty line. Streams the PCM back as it is produced |
| POST | `/process/stream/set` | Same body. Answers `202` at once and keeps synthesizing in the background |
| GET | `/process/stream/get` | Streams the audio of the last `set`. Waits if there is none yet; ends when that stream ends |
| POST | `/process/batch?text=...` | Synthesizes `text` and returns `{"audio_data_base64", "sample_rate", "channels"}`. `400` if the text is blank |

Stream endpoints take `sample_rate` (22050) and `channels` (1) as query parameters; both must be positive.
The audio is converted to that rate and channel count before it leaves the service.

JSON responses use the envelope `action / status / status_code / message / timestamp / data`.
Every failure currently returns HTTP 500, except blank text (400).

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

```bash
pytest                    # unit + architecture tests (no speech engine needed)
mypy .
ruff check .
black --check .
python tests/simple.py    # end-to-end against a running service
```

Architecture: [docs/architecture/architecture.md](docs/architecture/architecture.md).
The previous layout is documented in [docs/old/](docs/old/).
