# CLAUDE.md: tts_microservice

Port **8002**. Python/FastAPI. Text to speech. Status: working, needs retest after recent changes. See `README.md` and `../CLAUDE.md`.

Current state (2026-09-22): branch `feature_ai_claude`, clean, last commit "TTS: live NDJSON text in, contract audio events out, format conversion, natural statuses".

## Role

Brain uploads text events and reads audio events back.

| Path | Use |
|---|---|
| `POST /process/stream/set` | Brain uploads text (NDJSON events). Answers **202** with an ack stream (`TTS_INPUT_ACK`) |
| `GET /process/stream/get` | Brain reads audio events; waits if nothing was set yet |
| `POST /process/stream` | Single-request variant (`sample_rate`, `channels` query params) |
| `POST /process/batch?text=` | One text → base64 audio + `sample_rate` |
| `GET /health`, `/available` | Liveness, engine readiness |

Engine: local `pyttsx3` only (run in a subprocess, writes temp WAVs). Env: `TTS_VOICE_NAME`, `TTS_SPEECH_RATE`, `SERVICE_NAME/HOST/PORT`, `LOG_LEVEL`. **There is no OpenAI TTS engine in the code**, and no engine variable, even though `README.md` and `docs/architecture/architecture.md` mention one. Do not assume it exists.

## Layout

`main.py` → `main_flow/` → `composition_root/` → `application/` → `domain/` → `infrastructure/` (`outbound/pyttsx3_speech/`).

## Rules

- Events use `contracts.stream` (`TTS_INBOUND`/`TTS_OUTBOUND`, `TTS_INPUT_ACK`, which is an alias of `UPLOAD_ACK`) and the shared codec. Only Brain's TTS adapter reads the ack.
- Output is PCM16 mono in `bytes_base64`. TTS converts its engine output to the sample rate Brain requests (24 kHz). No other service converts audio.
- **Gotcha:** `testclear/` at the repo root is a whole Python venv (`Lib/site-packages`), not just scratch. Never build on it, and exclude it from every grep or glob.
- Ruff/mypy are configured in `pyproject.toml` but not installed in this venv. Do not bulk-fix lint unasked.
- `.engram/` holds old notes. Do not trust it over the code. `.env.staging` and `.env.production` exist: do not open them.
- Never log or echo API keys.

## Commands

```powershell
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest
```
