# Shared Test Container Design

## Problem

Each terminal tab creates its own Docker container when using `TestContainerPtySession`.
Opening multiple tabs (Cmd+T) spins up multiple containers, which is wasteful and slow.
We want all tabs to share a single container instance.

## Design

### Core idea

A single Docker container is created at app startup and shared across all terminal sessions
via `Arc<SharedContainer>`. Each tab spawns its own bash process inside the container using
`docker exec`. The container is stopped and removed when the last `Arc` reference is dropped.

### SharedContainer

New struct in `src/pty/adapters/test_container/container.rs`:

```rust
pub struct SharedContainer {
    container: Container,
}
```

- `setup() -> Result<Arc<Self>>`: Creates the container with `sleep infinity` as entrypoint
  (keeps container alive without a shell).
- `exec_bash() -> Result<(IoHandles, String)>`: Runs `docker exec` with tty+stdin,
  returns I/O handles and exec ID.
- `resize_exec(exec_id, cols, rows)`: Resizes a specific exec process TTY.
- `Drop`: Stops and removes the container (same cleanup thread pattern as current impl).

### Container changes

- Entrypoint changes from `/bin/bash` to `sleep infinity`.
- `setup()` returns just `Container` (no `IoHandles`) since nobody attaches to the main process.
- Remove `attach_container` call from setup.
- Remove `resize()` method (replaced by `SharedContainer::resize_exec()`).

### TestContainerPtySession changes

- Single constructor: `new(shared: Arc<SharedContainer>) -> Result<Self>`.
- Always stores `exec_id: String` (not optional).
- `resize()` delegates to `shared.resize_exec(exec_id, ...)`.
- Drop just drops the `Arc<SharedContainer>` (no container stop/remove logic).

### PtyProvider changes

```rust
pub enum PtyProvider {
    Local,
    #[cfg(feature = "pty-test_container")]
    TestContainer { shared: Arc<SharedContainer> },
}
```

No `Option` -- always carries the shared reference.

### AppState changes

Add a feature-gated field:

```rust
#[cfg(feature = "pty-test_container")]
pub shared_container: Option<Arc<SharedContainer>>,
```

Initialized at app startup (before first session) when test container mode is active.
Cloned into `PtyProvider::TestContainer` for each new session.

## File changes

| File | Change |
|------|--------|
| `src/pty/adapters/test_container/container.rs` | Entrypoint to `sleep infinity`, remove `IoHandles` from `setup()`, remove attach, add `SharedContainer` |
| `src/pty/adapters/test_container.rs` | Single constructor with `Arc<SharedContainer>`, always `exec_id`, remove Drop cleanup |
| `src/pty/manager.rs` | `PtyProvider::TestContainer` carries `Arc<SharedContainer>` |
| `src/app/state.rs` | Add `shared_container` field (feature-gated) |
| `src/app.rs` or `src/app/session_manager.rs` | Initialize `SharedContainer` at startup, pass into sessions |
| `src/session.rs` | Adjust `PtyProvider` construction |
| `src/main.rs` | Move test container init to async context |

## Lifecycle

```
App startup (test container mode)
  |
  v
SharedContainer::setup()
  -> Docker connect, pull image, create container (sleep infinity), start
  -> Arc<SharedContainer> stored in AppState
  |
  v
New tab (Cmd+T)
  |
  v
Clone Arc<SharedContainer> into PtyProvider::TestContainer
  -> TestContainerPtySession::new(shared)
  -> shared.exec_bash() -> docker exec /bin/bash with tty
  -> Wire Unix socket bridges (same as current)
  -> Session gets independent stdin/stdout
  |
  v
Tab closed
  -> Drop TestContainerPtySession
  -> Drop Arc<SharedContainer> (ref count decrements)
  -> If last ref: Drop SharedContainer -> stop + remove container
```
