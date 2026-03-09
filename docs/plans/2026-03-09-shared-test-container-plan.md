# Shared Test Container Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Share a single Docker container across all terminal tabs, creating it once at startup and destroying it when the last tab is closed.

**Architecture:** A `SharedContainer` wrapper holds the `Container` behind `Arc`. The container runs `sleep infinity` as its main process. Each tab uses `docker exec` to spawn an independent bash session. `PtyProvider::TestContainer` carries the `Arc<SharedContainer>` so every session reuses the same container.

**Tech Stack:** Rust, bollard (Docker API), tokio, Arc for shared ownership

---

### Task 1: Refactor `Container` to support idle entrypoint

**Files:**
- Modify: `src/pty/adapters/test_container/container.rs:51-61` (setup method)
- Modify: `src/pty/adapters/test_container/container.rs:126-144` (create_container method)
- Modify: `src/pty/adapters/test_container/container.rs:155-175` (remove attach_container)

**Step 1: Change `Container::setup()` return type**

Change `setup()` to return just `Container` (no `IoHandles`), remove the `attach_container` call:

```rust
pub async fn setup() -> anyhow::Result<Container> {
    let docker = Docker::connect_with_local_defaults()?;
    let name = format!("infraware_{}", uuid::Uuid::new_v4());
    let container = Container { docker, name };
    container.pull_image().await?;
    container.create_container().await?;
    container.start_container().await?;

    Ok(container)
}
```

**Step 2: Change entrypoint to `sleep infinity`**

In `create_container()`, change:
```rust
cmd: Some(vec!["/bin/bash".to_string()]),
```
to:
```rust
cmd: Some(vec!["sleep".to_string(), "infinity".to_string()]),
```

Also remove `tty: Some(true)` and `open_stdin: Some(true)` since the main process doesn't need them.

**Step 3: Remove `attach_container` method**

Delete the `attach_container()` method entirely — it's no longer used.

**Step 4: Remove `resize` method from `Container`**

Delete `Container::resize()` — resize will be handled per-exec in `SharedContainer`.

**Step 5: Remove unused imports**

Remove `AttachContainerOptionsBuilder` and `ResizeContainerTTYOptionsBuilder` from the imports. Remove `IoHandles` struct and the `AsyncWrite`/`Stream` imports if no longer needed here (they'll move or be re-added in SharedContainer).

**Step 6: Make `Container` fields accessible to `SharedContainer`**

Add `pub(super)` visibility to `Container`'s `docker` and `name` fields (or keep them private and add accessor methods). Since `SharedContainer` will live in the same module file, `pub(super)` on the fields is simplest:

```rust
pub struct Container {
    pub(super) docker: Docker,
    pub(super) name: String,
}
```

**Step 7: Verify it compiles**

Run: `cargo check --features pty-test_container`
Expected: Compilation errors in `test_container.rs` (expected, will fix in next task)

**Step 8: Commit**

```
refactor(pty): simplify Container to idle entrypoint without attach
```

---

### Task 2: Add `SharedContainer` with `exec_bash` and `resize_exec`

**Files:**
- Modify: `src/pty/adapters/test_container/container.rs` (add SharedContainer struct)

**Step 1: Add exec-related bollard imports**

At the top of `container.rs`, add:
```rust
use bollard::query_parameters::{
    CreateContainerOptionsBuilder, CreateImageOptionsBuilder,
    RemoveContainerOptionsBuilder, CreateExecOptionsBuilder, ResizeExecOptionsBuilder,
    StartExecOptionsBuilder,
};
use bollard::exec::StartExecResults;
```

Note: Check actual bollard 0.20 API — the builder names may differ. The key APIs are:
- `docker.create_exec(container_name, config)`
- `docker.start_exec(exec_id, config)`
- `docker.resize_exec(exec_id, options)`

**Step 2: Add `SharedContainer` struct and `setup()`**

```rust
/// A reference-counted handle to a shared Docker container.
///
/// The container runs `sleep infinity` as its main process, keeping it alive
/// indefinitely. Each terminal tab spawns its own bash process via
/// [`exec_bash`](Self::exec_bash). The container is stopped and removed
/// when the last `Arc<SharedContainer>` is dropped.
pub struct SharedContainer {
    container: Container,
    /// Tokio runtime handle for async cleanup in `Drop`.
    runtime_handle: tokio::runtime::Handle,
}

impl std::fmt::Debug for SharedContainer {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SharedContainer")
            .field("container_name", &self.container.name)
            .finish()
    }
}

impl SharedContainer {
    /// Creates the shared container and returns an `Arc` handle.
    pub async fn setup() -> anyhow::Result<Arc<Self>> {
        let container = Container::setup().await?;
        let runtime_handle = tokio::runtime::Handle::current();
        Ok(Arc::new(Self {
            container,
            runtime_handle,
        }))
    }
}
```

**Step 3: Add `exec_bash()` method**

```rust
impl SharedContainer {
    /// Spawns a new bash process inside the container via `docker exec`.
    ///
    /// Returns I/O handles for the exec's stdin/stdout and the exec ID
    /// (needed for resize).
    pub async fn exec_bash(&self) -> anyhow::Result<(IoHandles, String)> {
        let exec_config = bollard::exec::CreateExecOptions {
            cmd: Some(vec!["/bin/bash"]),
            attach_stdin: Some(true),
            attach_stdout: Some(true),
            attach_stderr: Some(true),
            tty: Some(true),
            ..Default::default()
        };

        let exec = self
            .container
            .docker
            .create_exec(&self.container.name, exec_config)
            .await?;

        let exec_id = exec.id;
        tracing::debug!("Created exec {exec_id} in container {}", self.container.name);

        let start_config = bollard::exec::StartExecOptions {
            detach: false,
            tty: true,
            ..Default::default()
        };

        let start_result = self
            .container
            .docker
            .start_exec(&exec_id, Some(start_config))
            .await?;

        match start_result {
            StartExecResults::Attached { input, output } => {
                Ok((IoHandles { input, output }, exec_id))
            }
            StartExecResults::Detached => {
                anyhow::bail!("Exec started in detached mode unexpectedly")
            }
        }
    }
}
```

Note: The exact bollard API types may differ — verify against bollard 0.20 docs. The `StartExecResults::Attached` variant should provide `input: Pin<Box<dyn AsyncWrite + Send>>` and `output: Pin<Box<dyn Stream<Item = Result<LogOutput, Error>> + Send>>`, matching our existing `IoHandles`.

**Step 4: Add `resize_exec()` method**

```rust
impl SharedContainer {
    /// Resizes the TTY of a specific exec process.
    pub async fn resize_exec(
        &self,
        exec_id: &str,
        cols: u16,
        rows: u16,
    ) -> anyhow::Result<()> {
        let opts = ResizeExecOptionsBuilder::default()
            .w(i32::from(cols))
            .h(i32::from(rows))
            .build();
        self.container
            .docker
            .resize_exec(exec_id, opts)
            .await?;
        Ok(())
    }
}
```

**Step 5: Add `Drop` implementation**

Move the container cleanup logic (previously in `TestContainerPtySession::Drop`) here:

```rust
impl Drop for SharedContainer {
    fn drop(&mut self) {
        let docker = self.container.docker.clone();
        let name = self.container.name.clone();
        let handle = self.runtime_handle.clone();

        let join_handle = std::thread::spawn(move || {
            let container = Container { docker, name };
            if let Err(e) = handle.block_on(container.stop()) {
                tracing::error!("Failed to stop shared container on drop: {e}");
            }
        });
        if let Err(e) = join_handle.join() {
            tracing::error!("Shared container cleanup thread panicked: {e:?}");
        }
    }
}
```

Note: `Docker` must implement `Clone` (it does in bollard). We need to make `Container`'s fields accessible for this — see Task 1 Step 6.

**Step 6: Export `SharedContainer` from module**

In `src/pty/adapters/test_container.rs`, add:
```rust
pub use self::container::SharedContainer;
```

And in `src/pty/adapters.rs`:
```rust
#[cfg(feature = "pty-test_container")]
pub use self::test_container::SharedContainer;
```

And in `src/pty.rs`, re-export:
```rust
#[cfg(feature = "pty-test_container")]
pub use adapters::SharedContainer;
```

**Step 7: Verify it compiles**

Run: `cargo check --features pty-test_container`
Expected: Still errors in `test_container.rs` (next task fixes those)

**Step 8: Commit**

```
feat(pty): add SharedContainer with exec_bash and resize_exec
```

---

### Task 3: Refactor `TestContainerPtySession` to use `SharedContainer`

**Files:**
- Modify: `src/pty/adapters/test_container.rs` (entire file restructure)

**Step 1: Update struct fields**

Replace the current struct with:

```rust
pub struct TestContainerPtySession {
    /// Shared container reference. Dropped when session ends;
    /// container is cleaned up when the last Arc is dropped.
    #[expect(dead_code, reason = "Held to keep container alive via Arc ref count")]
    shared: Arc<SharedContainer>,
    /// Exec ID for this session's bash process (used for resize).
    exec_id: String,
    /// Tokio runtime handle for potential async cleanup.
    runtime_handle: tokio::runtime::Handle,
    /// Async output stream, consumed once by [`PtySession::take_reader`].
    output: std::sync::Mutex<Option<OutputStream>>,
    /// Sync write end of the writer bridge, consumed once by [`PtySession::take_writer`].
    writer_handle: Option<std::os::unix::net::UnixStream>,
    /// Cloned write handle for sending SIGINT (Ctrl+C) synchronously.
    sigint_handle: Arc<std::sync::Mutex<std::os::unix::net::UnixStream>>,
}
```

**Step 2: Replace constructor**

Replace the `new()` method with one that takes `Arc<SharedContainer>`:

```rust
impl TestContainerPtySession {
    /// Creates a new PTY session by spawning a bash process in the shared container.
    pub async fn new(shared: Arc<SharedContainer>) -> Result<Self> {
        let (handles, exec_id) = shared.exec_bash().await?;

        let (unix_read, unix_write) = std::os::unix::net::UnixStream::pair()
            .context("Failed to create Unix socket pair for writer bridge")?;

        let sigint_writer = unix_write
            .try_clone()
            .context("Failed to clone Unix socket for sigint")?;

        spawn_writer_bridge(unix_read, handles.input)?;

        let runtime_handle = tokio::runtime::Handle::current();

        Ok(Self {
            shared,
            exec_id,
            runtime_handle,
            output: std::sync::Mutex::new(Some(handles.output)),
            writer_handle: Some(unix_write),
            sigint_handle: Arc::new(std::sync::Mutex::new(sigint_writer)),
        })
    }
}
```

**Step 3: Remove the `Drop` implementation**

Delete the entire `impl Drop for TestContainerPtySession` block. The `Arc<SharedContainer>` handles cleanup.

**Step 4: Update `Debug` implementation**

```rust
impl std::fmt::Debug for TestContainerPtySession {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let has_output = self.output.lock().map(|o| o.is_some()).unwrap_or(false);
        f.debug_struct("TestContainerPtySession")
            .field("exec_id", &self.exec_id)
            .field("has_output", &has_output)
            .field("has_writer", &self.writer_handle.is_some())
            .finish_non_exhaustive()
    }
}
```

**Step 5: Update `PtySession::resize`**

```rust
async fn resize(&self, size: PtySize) -> Result<()> {
    self.shared
        .resize_exec(&self.exec_id, size.cols, size.rows)
        .await
        .context("Failed to resize exec TTY")
}
```

**Step 6: Remove `container` field references**

The `take_reader`, `take_writer`, and `send_sigint` methods remain unchanged since they operate on the Unix socket bridges, not on the container directly.

**Step 7: Verify it compiles**

Run: `cargo check --features pty-test_container`
Expected: Errors in `manager.rs` (next task)

**Step 8: Commit**

```
refactor(pty): TestContainerPtySession uses SharedContainer via Arc
```

---

### Task 4: Update `PtyProvider` and `PtyManager`

**Files:**
- Modify: `src/pty/manager.rs:16-21` (PtyProvider enum)
- Modify: `src/pty/manager.rs:33-53` (PtyManager::new)

**Step 1: Change `PtyProvider::TestContainer` to carry shared ref**

```rust
#[derive(Debug, Clone)]
pub enum PtyProvider {
    Local,
    #[cfg(feature = "pty-test_container")]
    TestContainer {
        shared: Arc<super::adapters::SharedContainer>,
    },
}
```

Note: Remove `Copy` and `Eq` derives since `Arc` is not `Copy`. Keep `Clone`. Remove `PartialEq` too (Arc doesn't derive it by default, and we don't need it).

**Step 2: Update `PtyManager::new()` match arm**

```rust
#[cfg(feature = "pty-test_container")]
PtyProvider::TestContainer { shared } => (
    Box::new(
        super::adapters::TestContainerPtySession::new(shared).await?,
    ) as Box<dyn PtySession>,
    "test-container-shell".to_string(),
),
```

**Step 3: Add import for Arc**

Add `use std::sync::Arc;` if not already present (it is).

**Step 4: Verify it compiles**

Run: `cargo check --features pty-test_container`
Expected: Errors in `state.rs`, `session.rs`, `main.rs` (next tasks)

**Step 5: Commit**

```
refactor(pty): PtyProvider::TestContainer carries Arc<SharedContainer>
```

---

### Task 5: Update `AppState` and `AppOptions`

**Files:**
- Modify: `src/app/state.rs` (add shared_container field, update constructor)
- Modify: `src/app.rs:55-58` (AppOptions struct)

**Step 1: Update `AppOptions`**

In `src/app.rs`, change `AppOptions`:

```rust
pub struct AppOptions {
    /// Pty provider type (Local or TestContainer)
    pub pty_provider: PtyProviderType,
}

/// Selects which PTY backend to use (without carrying runtime state).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PtyProviderType {
    Local,
    #[cfg(feature = "pty-test_container")]
    TestContainer,
}
```

This is needed because `AppOptions` is created in `main()` before the tokio runtime exists, so it can't hold `Arc<SharedContainer>` yet. The actual `PtyProvider` is constructed later.

**Step 2: Update `AppState` to hold shared container**

In `src/app/state.rs`:

```rust
use crate::pty::PtyProvider;

#[cfg(feature = "pty-test_container")]
use std::sync::Arc;
#[cfg(feature = "pty-test_container")]
use crate::pty::SharedContainer;

pub struct AppState {
    pub sessions: HashMap<SessionId, TerminalSession>,
    pub pty_provider_type: PtyProviderType,
    #[cfg(feature = "pty-test_container")]
    pub shared_container: Option<Arc<SharedContainer>>,
    pub active_session_id: SessionId,
    pub next_session_id: SessionId,
    pub current_input_buffer: String,
    pub current_command_buffer: String,
    pub should_quit: bool,
}
```

**Step 3: Update `AppState::new()`**

Update constructor to accept the new fields. The `shared_container` is set after async init.

**Step 4: Add helper to build `PtyProvider`**

Add a method to `AppState`:

```rust
impl AppState {
    /// Builds a `PtyProvider` for creating a new session.
    pub fn pty_provider(&self) -> PtyProvider {
        match self.pty_provider_type {
            PtyProviderType::Local => PtyProvider::Local,
            #[cfg(feature = "pty-test_container")]
            PtyProviderType::TestContainer => {
                let shared = self
                    .shared_container
                    .clone()
                    .expect("SharedContainer not initialized");
                PtyProvider::TestContainer { shared }
            }
        }
    }
}
```

**Step 5: Update tests**

Update `create_test_state()` and `create_empty_state()` in test modules to use new field names.

**Step 6: Verify it compiles**

Run: `cargo check --features pty-test_container`

**Step 7: Commit**

```
refactor(app): AppState supports shared container via PtyProviderType
```

---

### Task 6: Wire up `SharedContainer` initialization in `InfrawareApp`

**Files:**
- Modify: `src/app.rs:226-275` (InfrawareApp::new)
- Modify: `src/app/session_manager.rs:37-43` (SessionManager::create)
- Modify: `src/session.rs:122` (TerminalSession::new signature)
- Modify: `src/main.rs:98-109` (app_options)

**Step 1: Update `main.rs` to use `PtyProviderType`**

```rust
fn app_options(_args: &Args) -> AppOptions {
    #[cfg(feature = "pty-test_container")]
    let pty_provider = if _args.use_pty_test_container {
        crate::app::PtyProviderType::TestContainer
    } else {
        crate::app::PtyProviderType::Local
    };
    #[cfg(not(feature = "pty-test_container"))]
    let pty_provider = crate::app::PtyProviderType::Local;

    AppOptions {
        pty_provider,
    }
}
```

**Step 2: Initialize `SharedContainer` in `InfrawareApp::new()`**

In `InfrawareApp::new()`, after creating the runtime, initialize the shared container if needed:

```rust
// Initialize shared container if using test container backend
#[cfg(feature = "pty-test_container")]
let shared_container = if matches!(options.pty_provider, PtyProviderType::TestContainer) {
    Some(
        runtime
            .block_on(SharedContainer::setup())
            .expect("Failed to initialize shared Docker container"),
    )
} else {
    None
};
#[cfg(not(feature = "pty-test_container"))]
let shared_container: Option<()> = None; // unused but keeps cfg simple
```

Then pass `shared_container` into `AppState::new()`.

**Step 3: Update `TerminalSession::new()` to take `PtyProvider` by value**

The current signature takes `PtyProvider` — since it now contains `Arc`, it must be passed by value (it already is, but we need to ensure `Clone` is used when calling for multiple sessions). Update `SessionManager::create()`:

```rust
pub fn create(state: &mut AppState, runtime: &tokio::runtime::Handle) -> SessionId {
    let id = state.allocate_session_id();
    let provider = state.pty_provider();
    let session = TerminalSession::new(id, runtime, provider);
    state.sessions.insert(id, session);
    tracing::info!("Created new session {}", id);
    id
}
```

**Step 4: Update initial session creation in `InfrawareApp::new()`**

Use the same `pty_provider()` helper for the initial session too.

**Step 5: Verify it compiles**

Run: `cargo check --features pty-test_container`
Expected: Clean compilation

Also verify without the feature:
Run: `cargo check`
Expected: Clean compilation

**Step 6: Commit**

```
feat(pty): wire shared container initialization at app startup
```

---

### Task 7: Verify and fix compilation for both feature flag states

**Files:**
- All modified files (fix any remaining compilation issues)

**Step 1: Build without feature flag**

Run: `cargo build`
Expected: Clean build

**Step 2: Build with feature flag**

Run: `cargo build --features pty-test_container`
Expected: Clean build

**Step 3: Run clippy on both**

Run: `cargo clippy -- -D warnings`
Run: `cargo clippy --features pty-test_container -- -D warnings`
Expected: No warnings

**Step 4: Run tests**

Run: `cargo test`
Expected: All tests pass

**Step 5: Format**

Run: `cargo +nightly fmt --all`

**Step 6: Commit (if any fixes)**

```
fix(pty): fix compilation for both feature flag states
```

---

### Task 8: Update design doc and CLAUDE.md

**Files:**
- Modify: `docs/plans/2026-03-09-shared-test-container-design.md` (mark as implemented)
- Modify: `CLAUDE.md` (update architecture notes if needed)

**Step 1: Mark design as implemented**

Add `**Status: Implemented**` at the top of the design doc.

**Step 2: Update CLAUDE.md**

Update the `PtyProvider` description in CLAUDE.md to mention that `TestContainer` carries a shared container reference.

**Step 3: Commit**

```
docs: update shared container design status and CLAUDE.md
```
