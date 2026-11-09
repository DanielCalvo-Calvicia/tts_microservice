# Architecture

TTS Microservice follows the same Clean Architecture layout as `microphone_microservice` ([ADR-001](../decisions/ADR-001-layered-architecture.md)).
It supersedes the docs in `docs/old/`. Reviewed against the code on 2026-11-05 (branch `feature_ai_claude_2`, commit `54a6259`, `contracts` 0.15.0; the working tree now bundles 0.16.0, uncommitted); updated 2026-11-06 for the fallback report and the `fetch_voice.py` tests (157 tests pass). Related documents: [API](../api/api.md), [variables](../configuration/environment-variables.md), [monitoring](../operations/monitoring.md), [security](../security/security.md), [deployment](../deployment/deployment.md), [requirements](../requirements/requirements.md), [decisions](../decisions/README.md).

## Layers and dependency rule

```
composition_root  ──▶  infrastructure  ──▶  application  ──▶  domain
 (chooses concretes)    inbound/outbound     ports+services    value objects, operations
```

Source-code dependencies point inward only. Runtime calls go outward (HTTP → service → engine)
through ports owned by `application`.

```
TtsHandler ──▶ TtsSynthesisPort ◀── TtsService ──▶ SpeechSynthesisPort ◀── PiperSpeechSynthesis ──▶ PiperEngine ──▶ piper (ONNX) + droid_voice (numpy)
(inbound)      (driving port)       (application)    (driven port)          (outbound, default)
                                         │                                ◀── EspeakSpeechSynthesis ──▶ EspeakEngine ──▶ espeak-ng subprocess + robot_voice (numpy)
                                         │                                    (outbound, option)
                                         │                                ◀── Pyttsx3SpeechSynthesis ──▶ Pyttsx3Subprocess ──▶ pyttsx3
                                         ▼                                    (outbound, fallback)
                              domain: AudioFormat, text rules, PCM conversion
```

`composition_root/dependencies/tts_dependencies.py` picks the engine from `TTS_ENGINE` (`piper` default, `espeak`, `pyttsx3`). If the Piper voice file is missing or does not load, or espeak is not installed or cannot speak (`SynthesisFailed`), it logs an error and uses pyttsx3 instead, so the service always starts ([ADR-006](../decisions/ADR-006-fallback-and-voice-at-deploy-time.md)). The Piper voice (about 60 MB) is not in git or pip: `scripts/fetch_voice.py` downloads it into `models/` (run by the deployment `prepare` step). `new_http_app` adds the shared `TracingMiddleware` (W3C trace context, `x-trace-id`).

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
                                  AudioStreamOutboundDTO, AudioBatchOutboundDTO,
                                  audio_segment_outbound (StreamFormat, AudioChunk, SegmentCompleted, SegmentFailed)
  ports/inbound/tts_synthesis_port.py       TtsSynthesisPort (driving)
  ports/outbound/speech_synthesis_port.py   SpeechSynthesisPort (driven)
  services/tts_service.py         TtsService — validates, skips blank texts, owns the shared stream
infrastructure/
  config/                         ServerConfig, TtsConfig (env -> frozen dataclasses, validated at start)
  inbound/http/                   http_handler.py (TtsHandler), http_envelope.py, http_error_mapper.py,
                                  ndjson_text_input.py (TTS inbound events -> texts), audio_events.py (audio -> TTS outbound events),
                                  input_stream_response.py (the ack stream of /process/stream/set)
  outbound/piper_speech/          piper_speech_synthesis.py (default engine: pitch, droid effect, format),
                                  piper_engine.py (the only module that drives Piper), droid_voice.py (numpy effect chain)
  outbound/espeak_speech/         espeak_speech_synthesis.py (engine, robot effect, format),
                                  espeak_engine.py (the only module that drives espeak: one subprocess per sentence, text on stdin),
                                  robot_voice.py (numpy: ring modulation, sample-and-hold, bit crush)
  outbound/pyttsx3_speech/        pyttsx3_speech_synthesis.py (temp WAV -> PCM chunks),
                                  pyttsx3_subprocess.py (the only module that drives pyttsx3)
composition_root/
  dependencies/tts_dependencies.py       new_speech_synthesis / new_tts_service / new_http_app
  containers/http_container.py           HttpContainer, new_http_container
scripts/  fetch_voice.py (deploy-time voice download), render_samples.py (listening samples)
vendor/   contracts_microservice-0.16.0-py3-none-any.whl   (refresh with contracts/scripts/bundle.py; the last commit has 0.15.0)
tests/  domain/ application/ infrastructure/ composition_root/ architecture/ scripts/   (pytest, 157)   +   simple.py (e2e)
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
* **Contract streams (since the 2026-09-20 commit, [ADR-002](../decisions/ADR-002-contract-streams.md), [ADR-003](../decisions/ADR-003-audio-conversion-in-tts.md)).** Text arrives as `TTS_INBOUND` NDJSON events and audio leaves as `TTS_OUTBOUND` events; the upload answers with an ack stream ending in `input_completed`. Engine output is converted to the requested sample rate and channels (`domain.operations.pcm.convert_pcm16`), so the earlier "echoed, not applied" limitation is gone.
* **Natural HTTP statuses** (`http_error_mapper.py`): 400 blank text, 422 invalid or mismatching format, 502 engine failure, else 500.
* **Piper default (commit `6a2f3d2`, [ADR-004](../decisions/ADR-004-piper-default-with-droid-effect.md)).** Piper `en_GB-alan-medium` plus the numpy droid effect (`droid_voice.py`: pitch lift by resampling, brightness, comb echoes, ring modulation), with pyttsx3 as fallback. New settings: `TTS_ENGINE`, `TTS_PIPER_VOICE`, `TTS_PIPER_MODEL_DIR`, `TTS_PIPER_SPEED`, `TTS_PITCH_SEMITONES`, `TTS_DROID_EFFECT`; `TTS_SPEECH_RATE` and `TTS_VOICE_NAME` are pyttsx3-only.

* **espeak engine (commit `543008f`, 2026-10-04, [ADR-005](../decisions/ADR-005-espeak-robot-engine.md)).** A formant-synthesis machine voice with a robot effect; new settings `TTS_ESPEAK_*` and `TTS_ROBOT_EFFECT`.
* **Tracing.** `TracingMiddleware` from `shared_logging` continues the incoming `traceparent` and answers with `x-trace-id`.
* **Contracts** 0.11.0 to 0.15.0 were bundled (commits of 2026-10-05 to 2026-10-08); 0.16.0 is bundled in the working tree since 2026-11-06 (uncommitted, not part of the deployment-readiness tasks). Only the 0.14.0 commit touched anything beyond the wheel and the requirements: small typing fixes in `http_handler.py`, `input_stream_response.py` and `fetch_voice.py`, and `pyrightconfig.json`. The shared stream is described in [ADR-007](../decisions/ADR-007-single-shared-stream.md).

## Known remaining debt

Stable IDs: the other documents cite them.

| ID | Debt | Status |
|---|---|---|
| D-1 | `ruff` (28 findings from the microphone venv, 6 auto-fixable), `mypy` and `black` are configured in `pyproject.toml` but not installed in this venv; not bulk-fixed on purpose. `tests/simple.py` is an end-to-end script that needs a running service and was not run in the last pass | Open |
| D-2 | The Piper droid effect (pitch 2.0, strength 0.5) was judged by ear by the maintainer on 2026-11-06 and the defaults were kept (T-01.1.5, `scripts/render_samples.py`, variant `3_default_droid`). The `espeak` robot effect values (`TTS_ROBOT_EFFECT`) are still tuned on paper and by tests, not by ear (`render_samples.py` does not render them; the five samples in `models/samples/robot/` date from 2026-10-04) | Resolved for the Piper droid voice; open for the `espeak` robot voice |
| D-3 | `POST /process/stream` is labelled `audio/wav` but carries headerless PCM | Open |
| D-4 | Linux and Raspberry Pi are untested: `piper-tts`/onnxruntime on arm64, and whether a sentence renders faster than real time. **Seen 2026-11-06 (T-03.1):** on Linux amd64 in a Docker image, Python 3.12.16 installs `piper-tts` 1.8.0 and onnxruntime 1.31.1 as binary wheels and the voice downloads and loads at build; nothing was run on Linux hardware or arm64, and the container was not started | Open (amd64 install seen; arm64 and speed open; **postponed 2026-11-09**: no Raspberry Pi test until the services work fully on Windows) |
| D-5 | **Split built 2026-11-06 (T-01.3):** `pytest`, `httpx` (test client), `ruff`, `black`, `mypy` moved to `requirements-dev.txt`; the runtime files hold only what the service imports (`httpx` was never imported by the service). **Still open:** no lock file, versions are lower bounds (only `piper-tts<2` has an upper bound), so a deploy resolves whatever is newest | Partly resolved (versions open) |
| D-6 | The fallback to pyttsx3 used to be silent to callers. **Service half built 2026-11-06 (T-01.2.2, ADR-008):** `GET /available` keeps `is_available: true` and carries a path-free `reason` (`fallback: pyttsx3 instead of piper (...)`). **Docker build half (T-02.1, in the `deployment` repository):** `prepare_required = true` for tts makes a failed voice fetch fail `docker build`; seen with real `docker build`s on 2026-11-06 (T-03.4): a nonexistent voice and a refused connection each ended with exit 1 and `error: the prepare step '...' failed with exit code 1 and this service requires it. Check the network and build again.`, and the `oblivion/tts:local` tag was not changed by the failed builds. **Tool half (T-02.2):** `deploy`, `start`, `update` and `status` print `healthy and available, warning: <reason>` and still succeed; seen in a real container through `oblivion.py start/status` (T-03.2). **Not seen:** a build on a machine that is really offline, and the same on arm64 | Resolved on amd64 Windows+Docker (2026-11-06); real offline and arm64 not run |
| D-7 | The `get` queue is unbounded and the size of a text or an upload is not limited | Open |
| D-8 | Local `.env*` files may name `TTS_ADAPTER` and `OPENAI_*`; the code reads none of them. There is no OpenAI engine, though `contracts` still has unused `tts/set_configuration.py` and `init_outbound.py` describing one | Open (in `contracts`) |
| D-9 | `GET /process/stream/get` accepts `keep_open_after_completed` and ignores it | Accepted |
| D-10 | Domain/application errors map to 400/422/502; the requested `sample_rate` and `channels` are applied; a failed text is a recoverable `error` event | Resolved |
| D-11 | **Found 2026-11-06 (T-03.2):** in the Docker image (Debian bookworm, apt `espeak espeak-data libespeak1` = espeak 1.48) the pyttsx3 fallback cannot initialise (`SetVoiceByName failed ... gmw/en`: pyttsx3 2.99 asks for an espeak-ng voice name). A voice that cannot be fetched then leaves the service up but unavailable (`is_available: false`, `/process/batch` 502, Brain's preflight fails): ADR-006's "the robot always speaks" did not hold there. The `espeak` engine worked with the same packages. **Fixed the same day:** the tts `apt` list in the deployment catalogue is now `espeak-ng`, `libespeak-ng1` (`espeak-ng-data` follows as a dependency); an image built with it runs, and with a missing voice the service answers `is_available: true` with the fallback `reason`, speaks with pyttsx3 (24 kHz mono, 49,356 bytes for "hello"), and `oblivion.py start`/`status` print `healthy and available, warning: fallback: ...` (exit 0). Both voices also work in the image's probe. **Not verified:** a native Raspberry Pi OS Bookworm install, which probably had the same problem (same Debian release) and now gets the new list through `--system-deps` | Resolved in Docker amd64 (2026-11-06, T-03.2); Pi not run |
