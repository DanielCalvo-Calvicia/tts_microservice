# Monitoring and operations

What exists today, checked against the code on 2026-11-05; anything else is stated as absent.

## Probes

| Probe | Behaviour |
|---|---|
| `GET /health` | `200`, envelope with `healthy: true`, whenever the process answers; touches no engine |
| `GET /available` | `200`, `is_available` and `reason`. Piper and espeak answer `true` once loaded (they are loaded or replaced by the fallback before the server starts); pyttsx3 runs a real check in a subprocess. Its failure is a `500` envelope. **`reason` is `null` on the configured engine and a `fallback: pyttsx3 instead of piper (...)` note when the fallback speaks** (ADR-008; `is_available` stays `true`). The deployment tool and Brain's preflight use this route as the readiness check; Brain ignores `reason` while `is_available` is `true`, so the fallback shows in the log and to a person or tool that reads `reason` |

Start-up is slow only when the voice loads (a few seconds). Brain's preflight waits 60 s, so **nothing is ever downloaded at start**: `scripts/fetch_voice.py` runs at deploy time.

## Shutdown

`SIGINT`/`SIGTERM` stops uvicorn (`server.serve()` returns). Nothing holds a device. Open `get` streams end with the process; a synthesis in flight is lost.

## Logs and tracing

`shared_logging` (`init_logging("tts")`): one JSON line per event with `trace_id`, `span_id`, `service` and `environment`. `TracingMiddleware` continues an incoming W3C `traceparent` and answers with `x-trace-id` (`tests/composition_root/test_tracing.py`). `LOG_LEVEL` decides the level; uvicorn's logs go through the same logger (`log_config=None`).

Lines worth knowing (constant messages, keyword fields):

| Message | Level | Meaning |
|---|---|---|
| `TtsService initialized` | info | `engine` is the adapter class actually in use |
| `Piper unavailable; falling back to pyttsx3` / `espeak unavailable; falling back to pyttsx3` | error | The chosen voice did not load; `reason` says why (with the full text, folder path included). The robot still speaks, with the old voice, and `GET /available` carries a path-free version of the same cause. The log file is appended across restarts: look only at the lines after the last `Started server process` |
| `Piper voice loaded`, `espeak ready` | info | The engine is ready (voice name, sample rate). `Piper voice loaded` and the two fallback lines above are pinned by `tests/composition_root/test_engine_selection.py` (message, level `ERROR`, logger, non-empty `reason`): a test fails if one stops being written |
| `Operation failed` | error | A request failed; `action` and `error` |
| `Shared stream generation completed` / `failed` / `cancelled` | info / error | End of a `set`: chunks and bytes, the exception, or replaced by a newer `set` |
| `Skipped blank text item` | info | A blank text was ignored |
| `TTS audio stream failed` | error | The `get` stream broke (a `stream_failed` event follows) |

The service logs the **length** of a text, not the text (`Yielding text line`, `length=`). Log levels and redaction are the package's (`shared-logging/docs/logging.md`).

## Resources

Piper keeps one ONNX session behind a lock: a sentence at a time. A synthesis runs in a thread (`asyncio.to_thread`), so a long text does not block the event loop. The voice file is about 60 MB; the process holds the loaded model in memory. espeak runs one subprocess per sentence with a 30 s timeout.

## Not present

- Metrics and alerting: none.
- Tracing export: off by default (`TRACE_EXPORT_*` of `shared_logging`).
- Rate limits, queue limits: the `get` queue is unbounded; one `set` is active at a time.
- Hardware: none needed.
