# Constraints

- Windows SAPI5 via `pyttsx3`; every synthesis runs in a fresh subprocess (COM/STA isolation).
- The engine ignores the requested `sample_rate`/`channels`: it writes its own WAV format.
- There is a single shared stream (`set_stream` / `get_stream`); a new `set_stream` replaces it and ends the old one's readers.
- `get_stream` before any `set_stream` waits (long-poll) instead of failing; the speaker's autoload relies on it.
