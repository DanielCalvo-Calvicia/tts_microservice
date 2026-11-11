# Environment variables

Read once at start-up by `ServerConfig.from_env()` and `TtsConfig.from_env()` (`infrastructure/config/`), after `load_dotenv(find_dotenv(".env"))` in `main_flow/http.py`. A variable already in the process environment wins over the `.env` file. The template with comments is [`.env.example`](../../.env.example); the [README](../../README.md) repeats the table. An invalid value stops the start with a `ValueError` naming the variable. **No variable of this service holds a secret**; never put one in `.env.example`, the code or a document. `.env.staging` and `.env.production` may exist locally: they are not documentation sources.

## Server

| Variable | Default | Description |
|---|---|---|
| `SERVICE_NAME` | `TTS Microservice` | API title |
| `SERVICE_HOST` | `127.0.0.1` | Bind address. Set `0.0.0.0` when Brain runs on another machine |
| `SERVICE_PORT` | `8002` | Bind port |

## Engine

| Variable | Default | Description |
|---|---|---|
| `TTS_ENGINE` | `piper` | `piper`, `espeak` or `pyttsx3` (case-insensitive); anything else fails the start. A chosen `piper` or `espeak` that cannot load falls back to `pyttsx3` (logged as an error), so the service always starts |

## Piper (default engine)

| Variable | Default | Description |
|---|---|---|
| `TTS_PIPER_VOICE` | `en_GB-alan-medium` | Voice name; the files `<voice>.onnx` and `<voice>.onnx.json` must be in the model folder |
| `TTS_PIPER_MODEL_DIR` | `models` | Model folder; a relative path is relative to the service folder, not to the working directory |
| `TTS_PIPER_SPEED` | `1.0` | Pace multiplier; must be greater than 0 |
| `TTS_PITCH_SEMITONES` | `2.0` | Pitch lift by resampling; the pace is kept; `0` = as recorded |
| `TTS_DROID_EFFECT` | `0.5` | Effect strength: `0` off, `0.5` light, `1` obvious, `2` maximum (clamped); must be 0 or more |

## espeak

| Variable | Default | Description |
|---|---|---|
| `TTS_ESPEAK_COMMAND` | empty | The program; empty means `espeak-ng` if installed, else `espeak` |
| `TTS_ESPEAK_VOICE` | `en` | Voice and variant (`en+m3`, `en+klatt3`, `en+croak`...); empty falls back to `en` |
| `TTS_ESPEAK_SPEED` | `150` | Words per minute, 80 to 390 |
| `TTS_ESPEAK_PITCH` | `30` | 0 to 99, lower is deeper |
| `TTS_ESPEAK_WORD_GAP_MS` | `20` | Extra silence between words, milliseconds, 0 or more (espeak counts it in 10 ms units) |
| `TTS_ROBOT_EFFECT` | `1.0` | Ring modulation, sample-and-hold, bit crush: `0` off, `1` default, `3` maximum (clamped); 0 or more |

## pyttsx3 (fallback)

| Variable | Default | Description |
|---|---|---|
| `TTS_SPEECH_RATE` | `140` | Words per minute |
| `TTS_VOICE_NAME` | `Zira` | Preferred voice (its name contains this text); otherwise the first English voice |

## Read by `shared_logging`, not by this service

`LOG_LEVEL` (`TRACE`, `DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`, `CRITICAL`; default `INFO`), `LOG_FORMAT`, `LOG_OUTPUT`, `ENVIRONMENT`, `TRACE_EXPORT_*`. See [`shared-logging/docs/logging.md`](../../../shared-logging/docs/logging.md).

## Not read (do not add them back)

`TTS_ADAPTER` and `OPENAI_*` sit in some old local `.env*` files and in the unused `tts/set_configuration.py` and `init_outbound.py` contracts of `contracts`. **There is no OpenAI TTS engine in the code.**
