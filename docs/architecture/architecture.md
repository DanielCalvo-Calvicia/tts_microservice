# Architecture

TTS Microservice follows the same Clean Architecture layout as `microphone_microservice`.
It supersedes the docs in `docs/old/`. Reviewed against the code on 2026-10-01 (branch `feature_ai_claude_2`, commit `6a2f3d2`).

## Layers and dependency rule

```
composition_root  ──▶  infrastructure  ──▶  application  ──▶  domain
 (chooses concretes)    inbound/outbound     ports+services    value objects, operations
```

Source-code dependencies point inward only. Runtime calls go outward (HTTP → service → engine)
through ports owned by `application`.

```
TtsHandler ──▶ TtsSynthesisPort ◀── TtsService ──▶ SpeechSynthesisPort ◀── PiperSpeechSynthesis ──▶ PiperEngine ──▶ piper (ONNX) + droid_voice (numpy)
(inbound)      (driving port)       (application)    (driven port)          (outbound, default)                       ◀── Pyttsx3SpeechSynthesis ──▶ Pyttsx3Subprocess ──▶ pyttsx3
                                         │                                                                               (outbound, fallback)
                                         ▼
                              domain: AudioFormat, text rules, PCM conversion
```

`composition_root/dependencies/tts_dependencies.py` picks the engine from `TTS_ENGINE` (`piper` default). If the Piper voice file is missing or does not load (`SynthesisFailed`), it logs an error and uses pyttsx3 instead, so the service always starts. The Piper voice (about 60 MB) is not in git or pip: `scripts/fetch_voice.py` downloads it into `models/` (run by the deployment `prepare` step).

`tests/architecture/test_dependency_rules.py` enforces this by parsing imports:

| Layer | May import | Must not import |
|---|---|---|
| `domain` | stdlib, `domain` | everything else |
| `application` | stdlib, `domain`, `application` | `infrastructure`, `composition_root`, fastapi/starlette/pydantic/uvicorn/numpy/httpx/dotenv/pyttsx3 |
| `infrastructure/inbound` | application, domain, frameworks | `infrastructure.outbound`, `composition_root` |
| `infrastructure/outbound` | application, domain, frameworks | `infrastructure.inbound`, `composition_root` |
| `composition_root` | everything | — |
| `main_flow` | `composition_root`, `infrastructure.config` | `infrastructure.inbound`, `infrastructure.outbound` |

## Layout

```
main.py                           calls main_flow.http.run_http()
main_flow/
  http.py                         .env -> config -> container -> uvicorn
domain/
  errors.py                       DomainError, InvalidAudioFormat, EmptyText
  operations/pcm.py               convert_pcm16 (sample rate and channel conversion)
  value_objects/audio_format.py   AudioFormat(sample_rate, channels) — all fields > 0
  operations/text.py              is_speakable, require_speakable
application/
  errors.py                       ApplicationError, SynthesisFailed, AudioFormatMismatch
  dtos/                           ProcessStreamInboundDTO, ProcessBatchInboundDTO,
                                  AudioStreamOutboundDTO, AudioBatchOutboundDTO
  ports/inbound/tts_synthesis_port.py       TtsSynthesisPort (driving)
  ports/outbound/speech_synthesis_port.py   SpeechSynthesisPort (driven)
  services/tts_service.py         TtsService — validates, skips blank texts, owns the shared stream
infrastructure/
  config/                         ServerConfig, TtsConfig (env -> frozen dataclasses)
  inbound/http/                   http_handler.py (TtsHandler), http_envelope.py, http_error_mapper.py,
                                  ndjson_text_input.py (TTS inbound events -> texts), audio_events.py (audio -> TTS outbound events),
                                  input_stream_response.py (the ack stream of /process/stream/set)
  outbound/piper_speech/          piper_speech_synthesis.py (default engine: pitch, droid effect, format),
                                  piper_engine.py (the only module that drives Piper), droid_voice.py (numpy effect chain)
  outbound/pyttsx3_speech/        pyttsx3_speech_synthesis.py (temp WAV -> PCM chunks),
                                  pyttsx3_subprocess.py (the only module that drives pyttsx3)
composition_root/
  dependencies/tts_dependencies.py       new_speech_synthesis / new_tts_service / new_http_app
  containers/http_container.py           HttpContainer, new_http_container
tests/  domain/ application/ infrastructure/ composition_root/ architecture/   (pytest)   +   simple.py (e2e)
```

## What changed from the previous layout

* `application/dtos/mapper/` is gone: the inbound, service and outbound DTO triples were field-for-field copies.
* The shared single-flow stream (queue, background task, replace-on-set) moved from the engine adapter into
  `TtsService`, so it is engine-independent and tested with a fake engine.
* The three copies of "synthesize to a temp WAV, read it in 1024-frame chunks, delete it" (stream, batch and
  decoupled) are now one method, `Pyttsx3SpeechSynthesis._pcm_chunks`.
* Blank-text handling is a domain rule (`is_speakable`) applied by the service, not repeated in the adapters.
* `infrastructure/config.py` + `infrastructure/logger.py` (environment resolution from `.vscode/launch.json`,
  per-environment log levels) are replaced by `infrastructure/config/` and the shared `shared_logging` package (`init_logging("tts")` in `main_flow/http.py`);
  `LOG_LEVEL` decides. `APP_ENV` no longer changes log levels (it only fills the `environment` log field); uvicorn's own logs go through the same logger.
* `pyttsx3` is driven by `Pyttsx3Subprocess`, which raises `SynthesisFailed` on a non-zero exit. The old helper
  returned the exception, and every caller ignored it.
* The 410-line `fastapi_adapter.py` (which also acted as an inbound port) is one small `TtsHandler`.

## Bugs fixed during the move

* `POST /process/batch` returned **empty audio**: it returned the last `readframes()` result, which is `b""` by
  definition of the loop. It now returns all of the PCM.
* `POST /process/batch` also pushed its chunks into the shared `set`/`get` queue, so a batch call injected
  audio into whoever was reading `GET /process/stream/get`. It no longer touches it.
* A blank `text` on `/process/batch` was meant to be a 400 but was raised inside `try/except Exception`, so it came
  back as a 500 with the message doubled. It is now a real 400.
* A failed synthesis used to surface as a `wave` `EOFError` from reading an empty file; it is now a `SynthesisFailed`
  with the engine's stderr.

## Deliberate changes

* `AudioFormat` rejects a non-positive `sample_rate` or `channels` (they used to be ignored).
* **Contract streams (since the 2026-09-20 commit).** Text arrives as `TTS_INBOUND` NDJSON events and audio leaves as `TTS_OUTBOUND` events; the upload answers with an ack stream ending in `input_completed`. Engine output is converted to the requested sample rate and channels (`domain.operations.pcm.convert_pcm16`), so the earlier "echoed, not applied" limitation is gone.
* **Natural HTTP statuses** (`http_error_mapper.py`): 400 blank text, 422 invalid or mismatching format, 502 engine failure, else 500.
* **Piper default (commit `6a2f3d2`).** Piper `en_GB-alan-medium` plus the numpy droid effect (`droid_voice.py`: pitch lift by resampling, brightness, comb echoes, ring modulation), with pyttsx3 as fallback. New settings: `TTS_ENGINE`, `TTS_PIPER_VOICE`, `TTS_PIPER_MODEL_DIR`, `TTS_PIPER_SPEED`, `TTS_PITCH_SEMITONES`, `TTS_DROID_EFFECT`; `TTS_SPEECH_RATE` and `TTS_VOICE_NAME` are pyttsx3-only.

## Known remaining debt

1. (Resolved) Domain/application errors map to 400/422/502 (see above).
2. (Resolved) The requested `sample_rate` and `channels` are applied by conversion.
3. `POST /process/stream` is labelled `audio/wav` but carries headerless PCM (`GET /process/stream/get` uses NDJSON events).
4. (Resolved) A failed text now produces a recoverable `error` event (`synthesis_failed`) on `get`; the stream carries on.
5. The old notes said `TTS_ADAPTER` and `OPENAI_*` variables sit in the local `.env*` files and are read nowhere; the code reads none of them (the `.env` files were not opened). Only Piper and pyttsx3 exist.
6. `tests/simple.py` is an end-to-end script that needs a running service.
7. The droid effect values are tuned on paper and by tests, not by ear (`scripts/render_samples.py` writes samples to `models/samples/` for listening).
