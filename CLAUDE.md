# CLAUDE.md: tts_microservice

Port **8002**. Python/FastAPI. Text to speech. Status: working, needs retest after recent changes. See `README.md` and `../CLAUDE.md`.

Current state (2026-10-01): branch `feature_ai_claude_2`, working tree clean, **1 commit ahead of `origin/feature_ai_claude_2` (not pushed)**. Last commit `6a2f3d2` "TTS: Piper neural voice (en_GB-alan-medium) with droid effect, pyttsx3 fallback" (before it `3653f74` "Bundle contracts 0.9.0"). Tests: `100 passed, 1 warning`. A real fresh-machine deploy of this service ran on Python 3.11 and 3.14 (see the deployment memory); the sound was not judged by ear and ruff (28 findings from the microphone venv) / mypy are not clean or installed here.

## Role

Brain uploads text events and reads audio events back.

| Path | Use |
|---|---|
| `POST /process/stream/set` | Brain uploads text (NDJSON `TTS_INBOUND` events). Answers **202** with an ack stream (`stream_started`, then `input_completed` or `error`; schema `UPLOAD_ACK`). A non-NDJSON body is plain text, one utterance per line |
| `GET /process/stream/get` | Brain reads audio events (NDJSON, `TTS_OUTBOUND`); heartbeat every 15 s; waits if nothing was set yet |
| `POST /process/stream` | Single-request variant (text body, headerless PCM16 back; `sample_rate`, `channels` query params, default 22050 / 1) |
| `POST /process/batch?text=` | One text → base64 audio + `sample_rate` + `channels`; 400 on blank text |
| `GET /health`, `/available` | Liveness, engine readiness |

Errors: 400 blank text, 422 invalid/mismatching format, 502 engine failed, else 500.
Engines (`TTS_ENGINE`): **`piper`** (default; local neural voice `en_GB-alan-medium`, in-process ONNX, then `droid_voice.py`: pitch lift by resampling + brightness, comb echoes, ring mod, all numpy) and `pyttsx3` (subprocess, temp WAVs; the **fallback** when the Piper voice file is missing or does not load, chosen in `composition_root/dependencies/tts_dependencies.py`). Env: `TTS_ENGINE`, `TTS_PIPER_VOICE/MODEL_DIR/SPEED`, `TTS_PITCH_SEMITONES`, `TTS_DROID_EFFECT`, `TTS_SPEECH_RATE`, `TTS_VOICE_NAME`, `SERVICE_NAME/HOST/PORT`, `LOG_LEVEL`. **There is no OpenAI TTS engine in the code** (the `tts/set_configuration.py` and `init_outbound.py` contracts in `contracts` still describe one; they are unused).

The voice (about 60 MB) is NOT in git (`models/` is ignored) nor in pip. The deployment tool fetches it with `scripts/fetch_voice.py` (its `prepare` step in `services.toml`, run after the `.env` is written; downloads to a temp folder, loads it, then moves it into place). Never download at service start: Brain's preflight waits only 60 s. Listening check: `scripts/render_samples.py` writes WAVs to `models/samples/`; the effect values are tuned on paper and by tests, not by ear.

## Layout

`main.py` → `main_flow/` → `composition_root/` → `application/` → `domain/` → `infrastructure/` (`outbound/piper_speech/`, `outbound/pyttsx3_speech/`).

## Rules

- Events use `contracts.stream` (`TTS_INBOUND`/`TTS_OUTBOUND`, `TTS_INPUT_ACK`, an alias of `UPLOAD_ACK`) and the shared codec. Only Brain's TTS adapter reads the ack.
- Output is PCM16 mono in `bytes_base64`. TTS converts its engine output (both engines, `convert_pcm16`) to the sample rate and channels requested; Brain asks for 24 kHz. No other service converts audio.
- **Gotcha:** `testclear/` at the repo root is a whole Python venv (`Lib/site-packages`), not just scratch. Never build on it, and exclude it from every grep or glob.
- `contracts` comes from `vendor/contracts_microservice-<version>.whl` (0.10.0); refresh it with `contracts/scripts/bundle.py`.
- Ruff/mypy/black are configured in `pyproject.toml` but not installed in this venv. Do not bulk-fix lint unasked.
- `.engram/` holds old notes. Do not trust it over the code. `.env.staging` and `.env.production` exist: do not open them.
- Never log or echo API keys.

## Commands

```powershell
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest
```
