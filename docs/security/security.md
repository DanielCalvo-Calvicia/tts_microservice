# Security

Only what can be verified in the repository (2026-11-05). Labels: **Implemented** (in the code and tested), **Required** (the operator must do it), **Recommended but not implemented**.

## The service

- **Not implemented:** authentication and authorisation. Every caller uses the same API (NFR-9). Service-to-service auth is not designed for the whole OBLIVION system (see the workspace `README.md`). **Required:** the network in front of port 8002 limits who can reach it. The default bind address is `127.0.0.1`; setting `SERVICE_HOST=0.0.0.0` (needed when Brain is on another machine) opens it to the LAN.
- **Implemented:** the audio format is validated (positive rate and channels, `422`); a text is never placed on a command line: espeak reads it from stdin (`--stdin`), so a text starting with `-` or holding quotes cannot become an option or a shell command (no shell is used; the program is a resolved path).
- **Implemented:** the pyttsx3 fallback runs in a subprocess; a non-zero exit is a `502`, not an unhandled exception.
- **Implemented:** the logs hold the length of a text, never its content (`Yielding text line`); `shared_logging` redacts known secret keys.
- **Implemented:** `GET /available` can carry a `reason` (the fallback note, ADR-008) to any caller. It is built from the failure text with the folder path removed (a folder is named by its last part, the home directory is `~`), on one line, at most 200 characters (`tests/composition_root/test_engine_selection.py`). The full text, with the path, stays in the log only.
- **Not implemented:** a limit on the size of a text or of an upload; the `get` queue is unbounded. A hostile caller on the network could exhaust memory.
- **Open:** `/docs`, `/redoc` and `/openapi.json` are served (FastAPI defaults).

## Secrets

- This service has **no secret**. No API key is read (the OpenAI engine does not exist in the code). `.env` is git-ignored; `.env.example` holds names and defaults only.
- `.env.staging` and `.env.production` exist locally and may hold old `OPENAI_*` names; they are read by nothing and must not be opened, copied or documented.
- Never log or echo an API key.

## Supply chain

- The Piper voice is downloaded by `scripts/fetch_voice.py` into a temporary folder, loaded once to prove it is intact, and only then moved into place; an interrupted download never leaves a half voice. The download is Piper's own (`piper.download_voices`), over the network, at deploy time only. **Recommended but not implemented:** a checksum of the voice file.
- `contracts` comes from the wheel in `vendor/` (0.16.0), built from the workspace; `shared-logging` is the local checkout (`-e ../shared-logging`).
- **Recommended but not implemented:** pinned versions and a lock file (the requirements use lower bounds); `pytest`, `ruff`, `black`, `mypy` and `httpx` are no longer in the runtime requirements: they moved to `requirements.dev.txt` on 2026-11-06, so a deployed install carries fewer packages (D-5, split done; versions still unpinned).
