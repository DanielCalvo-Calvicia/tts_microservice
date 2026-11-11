# T-03 — Docker and arm64 acceptance

| | |
|---|---|
| Status | in-progress (T-03.1, T-03.2, T-03.4 and T-03.5 done; T-03.3 is postponed: it needs a Raspberry Pi) |
| Kind | epic |
| Depends on | T-01, T-02 |
| Blocks | — |

## Goal

Prove, on real systems, the two things the audit could only read: the Docker image of tts builds and speaks with Piper, and the service installs and runs on arm64 (a Raspberry Pi 4 or newer). Nothing in this epic has ever been run (D-4, NFR-7, NFR-10).

## Preconditions (the assistant checks them first and stops if one fails)

- Docker is running on the machine where the image is built. On the maintainer's PC, Docker Desktop must be started; its engine was not running on 2026-11-05 (F12).
- **The Docker CLI context.** The saved context on that machine was `raspberry` (an SSH context to the Pi), which timed out. Every `docker` command in this epic names its context (`docker --context desktop-linux ...` for the PC, the Pi's context for T-03.3), and the saved context is never changed. The deployment tool calls plain `docker`, so before running it for a Docker deploy ask the maintainer which context is active (`docker context ls` marks it with `*`).
- Network access for the base image, pip and the voice (about 60 MB): say so and wait for a yes before the first build.
- Build from a clean clone or through the tool (which clones), never from the working folder (F9, T-02.3).

## Subtasks

| Order | Task | Kind | State |
|---|---|---|---|
| 1 | [T-03.1 Build the image on amd64](T-03.1_amd64-build.md) | manual | done (2026-11-06) |
| 2 | [T-03.2 Run the container and call it](T-03.2_run-and-call.md) | manual | done (2026-11-06; D-11 found and fixed) |
| 3 | [T-03.3 Build and run on arm64](T-03.3_arm64.md) | manual | todo (needs a Raspberry Pi) |
| 4 | [T-03.4 Build without network](T-03.4_build-without-network.md) | manual | done (2026-11-06) |
| 5 | [T-03.5 Record what was verified](T-03.5_record-the-results.md) | docs | done |

## Exit criteria

Each leaf has its observed result (or exact failure) in *Notes*; `docs/deployment/deployment.md` ("Docker" and "Verified deployments") names what was run, on which machine and architecture, and what was not.
