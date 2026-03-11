# PTY Backends

Infraware Terminal uses a pluggable PTY (Pseudo-Terminal) backend system. Each terminal session runs on a PTY backend that provides interactive shell access — either on the local host or inside a Docker container.

## Architecture

```
                    ┌──────────────────────┐
                    │   TerminalSession    │
                    │                      │
                    │  PtyReader / PtyWriter│
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │     PtyManager       │
                    │  Box<dyn PtySession> │
                    └──────────┬───────────┘
                               │
         ┌─────────────────────┼──────────────────────────┐
         │                     │                          │
   ┌─────▼──────────┐   ┌─────▼───────────┐   ┌─────────▼──────────┐
   │LocalPtySession │   │DockerExecSession│   │DockerExecSession   │
   │(portable-pty)  │   │(test-container) │   │(arena)             │
   │                │   │                 │   │                    │
   │Host shell      │   │Debian container │   │Scenario image +   │
   │process         │   │                 │   │ScenarioManifest   │
   └────────────────┘   └────────┬────────┘   └─────────┬──────────┘
                                 │                       │
                                 └───────────┬───────────┘
                                             │
                              ┌──────────────▼────────────────┐
                              │  pty/docker/ module           │
                              │  ├─ Container + ContainerConfig│
                              │  ├─ SharedContainer (Arc)     │
                              │  └─ DockerExecSession impl    │
                              └───────────────────────────────┘
```

All backends implement the `PtySession` trait, which provides:

- **`take_reader`** — streams output bytes to a sync channel
- **`take_writer`** — returns a writer handle for sending input
- **`resize`** — changes terminal dimensions
- **`send_sigint`** — sends Ctrl+C / SIGINT

## Available Backends

### Local (default)

The local backend spawns a shell process on the host system using [`portable-pty`](https://docs.rs/portable-pty/). This is the default and requires no additional setup.

- Detects the best available shell: **zsh** > **bash** > **sh**
- Spawns an interactive shell (`-i` flag)
- Inherits the parent process environment
- Sets `TERM=xterm-256color` for full terminal emulation

**Usage:**

```bash
cargo run
```

### Test Container (Docker)

The test container backend runs an isolated Debian container via the Docker API using [`bollard`](https://docs.rs/bollard/). This is useful for:

- **Sandboxed command execution** — the AI agent can run commands without affecting the host
- **Consistent testing environment** — always a clean Debian system
- **Security** — commands execute inside a disposable container

By default the container uses the `debian:bookworm-slim` image and runs `/bin/bash` with TTY enabled.
You can override the image with the `--pty-test-container-image` flag (accepts `image:tag` format; tag defaults to `latest` when omitted).

**Prerequisites:**

- Docker daemon running and accessible (via Unix socket or TCP)
- The `pty-test_container` Cargo feature enabled

**Usage:**

```bash
# Build with the test container feature (default image: debian:bookworm-slim)
cargo run --features pty-test_container -- --use-pty-test-container

# Or via environment variable
USE_PTY_TEST_CONTAINER=true cargo run --features pty-test_container

# Use a custom image
cargo run --features pty-test_container -- --use-pty-test-container --pty-test-container-image ubuntu:24.04
```

**How it works:**

The adapter bridges Docker's async I/O to the sync `PtyReader`/`PtyWriter` types using Unix socket pairs and tokio tasks:

```
Writer path:
  PtyWriter → Unix socket (sync) → tokio task → bollard stdin (async)

Reader path:
  bollard stdout (async) → tokio task → SyncSender → PtyReader consumer
```

On startup the adapter:

1. Pulls the configured image (default: `debian:bookworm-slim`, if not cached)
2. Creates a container with `tty=true`, `open_stdin=true`, `cmd=[/bin/bash]`
3. Starts the container
4. Attaches to stdin/stdout/stderr streams
5. Sets up async-to-sync bridges for reader and writer

When the session is killed, the container is stopped and removed.

### Arena (Docker)

The arena backend runs a Docker container configured for incident investigation challenges. Like the test container backend, it uses the Docker API via [`bollard`](https://docs.rs/bollard/). Arena differs in that the image is selected from a predefined set of scenarios, and a scenario manifest is read and displayed on startup.

**Prerequisites:**

- Docker daemon running and accessible (via Unix socket or TCP)
- The `arena` Cargo feature enabled (which includes the `docker` feature)

**Usage:**

```bash
# Run with a predefined arena scenario
cargo run --features arena -- --arena the-502-cascade
```

**How it works:**

Arena scenarios are defined in `src/pty/manager.rs` via the `ArenaScenario` enum. Each scenario maps to a Docker image (e.g., `The502Cascade` → `veeso/arena-the-502-cascade:latest`). On startup:

1. Pull the scenario image (if not cached)
2. Create and start a container with TTY enabled
3. Read `/arena/scenario.json` from the container via `docker exec`
4. Format and inject the incident prompt into the terminal output (ANSI-formatted)
5. Hand off to the live shell stream

The implementation shares code with the test container backend — both use `DockerExecSession` from `pty/docker/exec_session.rs`.

See [docs/arena-mode.md](arena-mode.md) for detailed information on building scenario images and the arena challenge system.

## Configuration

| Parameter | CLI Flag | Env Variable | Default |
|-----------|----------|--------------|---------|
| PTY backend | `--use-pty-test-container` | `USE_PTY_TEST_CONTAINER` | `false` (local) |
| Arena scenario | `--arena <SCENARIO>` | — | *(none — arena mode is opt-in)* |
| Container image | `--pty-test-container-image` | — | `debian:bookworm-slim` |
| Log level | `--log-level` / `-l` | `RUST_LOG` or `LOG_LEVEL` | `info` |

## Feature Flags

| Feature | Dependencies | Description |
|---------|-------------|-------------|
| *(default)* | `portable-pty` | Local PTY backend (always available) |
| `docker` | `bollard` | Base Docker support (shared by `pty-test_container` and `arena`) |
| `pty-test_container` | `docker` | Test container backend (requires `docker` feature) |
| `arena` | `docker` | Arena scenario backend (requires `docker` feature) |

## Adding a New Backend

1. Create a new module under `src/pty/adapters/` (e.g., `src/pty/adapters/ssh.rs` or `src/pty/adapters/ssh/`)
2. Implement the `PtySession` trait
3. Add a variant to `PtyProvider` enum in `src/pty/manager.rs`
4. Add construction logic in `PtyManager::new()`
5. Wire the CLI flag / env variable in `src/args.rs` and `src/main.rs`
6. Gate behind a feature flag if it adds optional dependencies

**For Docker-based backends:** If your backend needs Docker container management, reuse the `pty/docker/` module (which provides `SharedContainer`, `Container`, and `ContainerConfig`). If your backend needs a `PtySession` implementation, consider whether `DockerExecSession` can be shared or if a new implementation is needed.
