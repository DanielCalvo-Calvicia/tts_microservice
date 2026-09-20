# Architecture

TTS Microservice follows the same Clean Architecture layout as `microphone_microservice`.
It supersedes the docs in `docs/old/`.

## Layers and dependency rule

```
composition_root  ──▶  infrastructure  ──▶  application  ──▶  domain
 (chooses concretes)    inbound/outbound     ports+services    value objects, operations
```

Source-code dependencies point inward only. Runtime calls go outward (HTTP → service → engine)
through ports owned by `application`.

```
TtsHandler ──▶ TtsSynthesisPort ◀── TtsService ──▶ SpeechSynthesisPort ◀── Pyttsx3SpeechSynthesis ──▶ Pyttsx3Subprocess ──▶ pyttsx3
(inbound)      (driving port)       (application)    (driven port)          (outbound)                 (subprocess)
                                         │
                                         ▼
                              domain: AudioFormat, text rules
```

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
  value_objects/audio_format.py   AudioFormat(sample_rate, channels) — all fields > 0
  operations/text.py              is_speakable, require_speakable
application/
  errors.py                       ApplicationError, SynthesisFailed
  dtos/                           ProcessStreamInboundDTO, ProcessBatchInboundDTO,
                                  AudioStreamOutboundDTO, AudioBatchOutboundDTO
  ports/inbound/tts_synthesis_port.py       TtsSynthesisPort (driving)
  ports/outbound/speech_synthesis_port.py   SpeechSynthesisPort (driven)
  services/tts_service.py         TtsService — validates, skips blank texts, owns the shared stream
infrastructure/
  config/                         ServerConfig, TtsConfig (env -> frozen dataclasses)
  inbound/http/                   http_handler.py (TtsHandler), http_envelope.py, http_error_mapper.py
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

## Known remaining debt

1. Domain errors are not mapped to 4xx (`InvalidAudioFormat` → 422, `SynthesisFailed` → 502); see `http_error_mapper.py`, decision D4.
2. The requested `sample_rate` and `channels` are validated and echoed but not applied: pyttsx3 writes its own WAV format.
3. `process_stream`/`get_stream` are labelled `audio/wav` but carry headerless PCM.
4. A synthesis failure ends a stream quietly (it is logged); a client cannot tell it from a normal end.
5. `TTS_ADAPTER` and the `OPENAI_*` variables in local `.env*` files are read nowhere; only pyttsx3 exists.
6. `tests/simple.py` is an end-to-end script that needs a running service.
