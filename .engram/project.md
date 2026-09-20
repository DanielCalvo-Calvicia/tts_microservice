# Project

TTS Microservice: HTTP service that turns text into 16-bit PCM audio with the local pyttsx3 (SAPI5) engine.

Intentionally omitted from the Engram tree (add only when needed): `.devcontainer/`, `.github/`,
`k8s/`, `Dockerfile`, `docker-compose.yml`, `domain/entities/` (the shared stream's state lives in
the application service, not in a business entity).
