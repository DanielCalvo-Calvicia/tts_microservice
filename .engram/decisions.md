# Decisions

- D1: No `cmd/` folder (shadows stdlib `cmd`); entry point is `main.py` + `main_flow/`.
- D2: Config is stdlib frozen dataclasses in `infrastructure/config/`.
- D3: The shared stream (queue + background task) lives in `TtsService`, not in the engine adapter.
- D4: HTTP status mapping stays "everything is 500" except `EmptyText` -> 400 (`http_error_mapper.py`).
- D5: The pyttsx3 subprocess is a collaborator (`Pyttsx3Subprocess`) so WAV/PCM handling is testable without an engine.
- D6: The request body is read before `set_stream` returns: the background synthesis outlives the request.
- D7: Runtime environments (`APP_ENV` log levels, `infrastructure/logger.py`, launch-profile parsing) were dropped; logging is stdlib and `LOG_LEVEL` decides.
