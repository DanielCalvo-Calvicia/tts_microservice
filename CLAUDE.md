# CLAUDE.md: tts_microservice

Port **8002**. Python/FastAPI. Text to speech. Status: working, needs retest after recent changes. See `README.md` and `../CLAUDE.md`.

## Role

Brain uploads text events and reads audio events back.

| Path | Use |
|---|---|
| `POST /process/stream/set` | Brain uploads text (NDJSON events) |
| `GET /process/stream/get` | Brain reads audio events; waits if nothing was set yet |
| `POST /process/batch?text=` | One text → base64 audio + `sample_rate` |
| `GET /health`, `/available` | Liveness, engine readiness |

Engines: local `pyttsx3` (run in a subprocess, writes temp WAVs; voice via `TTS_VOICE_NAME`, speed via `TTS_SPEECH_RATE`) or OpenAI TTS.

## Layout

`main.py` → `main_flow/` → `composition_root/` → `application/` → `domain/` → `infrastructure/`.

## Rules

- Events use `contracts.stream` (`TTS_INBOUND`/`TTS_OUTBOUND`, plus `TTS_INPUT_ACK`) and the shared codec.
- Output is PCM16 mono in `bytes_base64`. TTS converts its engine output to the sample rate Brain requests (24 kHz). No other service converts audio.
- The `testclear` folder at the repo root is scratch. Do not build on it.
- Never log or echo API keys.

## Commands

```powershell
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest
```
