# Requirements

Status as of 2026-11-06. **Done** means implemented and covered by the tests (170 pass on 2026-11-11, after the restructure of the layers; the statuses below date from 2026-11-06 and did not change); **Partly done** means some of it exists; **Not done** means absent on purpose or not started. Every row names the ADR or document that records it. The requirements were derived from the code and the project notes; the maintainer has not signed them off.

## Functional

| ID | Requirement | Status | Record |
|---|---|---|---|
| FR-1 | Convert text to PCM16 audio over HTTP, with the sample rate and channel count the caller asks for (default 22050 Hz, mono) | Done | [API](../api/api.md), ADR-003 |
| FR-2 | Accept text from Brain as a live NDJSON stream of `TTS_INBOUND` events and answer with an ack stream (`stream_started`, `input_completed`, `error`) | Done | ADR-002 |
| FR-3 | Serve the audio of the last upload as `TTS_OUTBOUND` events: `stream_started`, `partial`, `completed`, a recoverable `error` per failed text, `heartbeat` every 15 s | Done | ADR-002 |
| FR-4 | A new upload replaces the previous one; a reader that connects before any upload waits | Done | [Architecture](../architecture/architecture.md) |
| FR-5 | Plain-text upload (one utterance per line) for simple clients; single-request variants `/process/stream` and `/process/batch` | Done | [API](../api/api.md) |
| FR-6 | Skip blank texts; `/process/batch` rejects a blank text with `400` | Done | |
| FR-7 | Default voice: Piper `en_GB-alan-medium` with the droid effect (pitch lift, brightness, comb echoes, ring modulation) | Done | ADR-004 |
| FR-8 | Alternative voices: `espeak` (formant synthesis plus a robot effect) and `pyttsx3` | Done | ADR-005 |
| FR-9 | Fall back to `pyttsx3` when the chosen Piper voice or espeak cannot load, so the service always starts | Done: the service starts on the fallback. In the first Docker image the fallback voice itself failed (D-11); fixed by the espeak-ng packages and seen working in a container on 2026-11-06 | ADR-006, ADR-008, D-11 |
| FR-10 | Fetch the Piper voice at deploy time (`scripts/fetch_voice.py`), never at start; exit code `0` ready or not needed, `1` could not fetch, both pinned by `tests/scripts/test_fetch_voice.py` (2026-11-06) | Done | ADR-006, [Deployment](../deployment/deployment.md) |
| FR-11 | Report errors as `400` blank text, `422` invalid or mismatching format, `502` engine failure, `500` else | Done | [API](../api/api.md) |
| FR-12 | `GET /health` and `GET /available` (with a `reason`, see FR-15) | Done | [API](../api/api.md) |
| FR-13 | Listening samples of the voice variants (`scripts/render_samples.py`) | Done | |
| FR-14 | Judge the voice by ear and tune the effect values | Partly done: the Piper droid voice was judged and the defaults kept (2026-11-06, T-01.1.5); the `espeak` robot voice was not | D-2 |
| FR-15 | Say in `GET /available` (`reason`, path-free, `is_available` unchanged) when the pyttsx3 fallback speaks instead of the chosen engine | Done in the service (2026-11-06, T-01.2.2, tests) and shown by the deployment tool (T-02.2); seen against a real fallback in a Docker container through `oblivion.py start/status` (T-03.2, 2026-11-06) | ADR-008, D-6 |

## Non-functional

| ID | Requirement | Status | Record |
|---|---|---|---|
| NFR-1 | Same layered layout as the other services (`main.py`, `main_flow`, `composition_root`, `application`, `domain`, `infrastructure`); dependencies point inward, enforced by `tests/architecture/` | Done | [Architecture](../architecture/architecture.md), ADR-001 |
| NFR-2 | Wire format from `contracts.stream`, encoded and decoded with the shared codec; never hand-written event JSON | Done | ADR-002 |
| NFR-3 | JSON answers use the `ApiEnvelope` | Done | |
| NFR-4 | Audio is PCM16 mono in `bytes_base64`; the conversion to the requested format happens here and nowhere else | Done | ADR-003 |
| NFR-5 | Logging only through `shared_logging`, with constant messages and keyword fields; W3C trace context is continued | Done | [Monitoring](../operations/monitoring.md) |
| NFR-6 | All settings come from environment variables with a documented `.env.example`; no hardcoded port | Done | [Variables](../configuration/environment-variables.md) |
| NFR-7 | Works on Windows and on Linux/Raspberry Pi (`requirements.linux.txt`) | Partly done | Tested on Windows only; Linux and arm64 are not verified (D-4) |
| NFR-8 | The service needs no hardware and runs without a speech engine in the tests | Done | |
| NFR-9 | No authentication; the network limits who can call it | Done as a decision; not a solution | [Security](../security/security.md) |
| NFR-10 | A sentence synthesizes faster than it takes to say it on a Raspberry Pi | Not verified | D-4 |
| NFR-11 | The audio of a text is available to Brain within the preflight and call timeouts | Not measured | |
| NFR-12 | A deployed install contains only what the service runs on: the runtime requirements files, with tests and tooling in `requirements.dev.txt` | Done (2026-11-06, T-01.3): a runtime-only venv starts the service; runtime plus dev passes the suite. Versions are not pinned (D-5) | [Deployment](../deployment/deployment.md) |

## Known gaps

See [the debt list in the architecture document](../architecture/architecture.md#known-remaining-debt) (D-1 to D-11).
