//! Shared container handle for reusing a single Docker container across terminal tabs.

use std::pin::Pin;
use std::sync::Arc;

use bollard::container::LogOutput;
use bollard::exec::{CreateExecOptions, ResizeExecOptions, StartExecOptions, StartExecResults};
use futures::Stream;
use tokio::io::AsyncWrite;

use super::container::Container;

/// Container IO streams for interacting with a bash exec's stdin, stdout, and stderr.
pub struct IoHandles {
    pub input: Pin<Box<dyn AsyncWrite + Send>>,
    pub output: Pin<Box<dyn Stream<Item = Result<LogOutput, bollard::errors::Error>> + Send>>,
}

/// A reference-counted handle to a shared Docker container.
///
/// The container runs `sleep infinity` as its main process, keeping it alive
/// indefinitely. Each terminal tab spawns its own bash process via
/// [`exec_bash`](Self::exec_bash). The container is stopped and removed
/// when the last `Arc<SharedContainer>` is dropped.
pub struct SharedContainer {
    container: Container,
    /// Tokio runtime handle for async cleanup in [`Drop`].
    runtime_handle: tokio::runtime::Handle,
}

impl std::fmt::Debug for SharedContainer {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SharedContainer")
            .field("name", &self.container.name)
            .finish_non_exhaustive()
    }
}

impl SharedContainer {
    /// Creates and starts the shared Docker container.
    ///
    /// Pulls the Debian image, creates the container with `sleep infinity`,
    /// starts it, and captures the current tokio runtime handle for later
    /// use in [`Drop`].
    pub async fn setup() -> anyhow::Result<Arc<Self>> {
        let container = Container::setup().await?;
        let runtime_handle = tokio::runtime::Handle::current();

        Ok(Arc::new(Self {
            container,
            runtime_handle,
        }))
    }

    /// Spawns a new interactive bash process inside the container via `docker exec`.
    ///
    /// Returns the IO handles (stdin/stdout/stderr streams) and the exec ID
    /// which is needed for subsequent [`resize_exec`](Self::resize_exec) calls.
    pub async fn exec_bash(&self) -> anyhow::Result<(IoHandles, String)> {
        let exec_opts = CreateExecOptions {
            attach_stdin: Some(true),
            attach_stdout: Some(true),
            attach_stderr: Some(true),
            tty: Some(true),
            cmd: Some(vec!["/bin/bash"]),
            ..Default::default()
        };

        let exec_created = self
            .container
            .docker
            .create_exec(&self.container.name, exec_opts)
            .await?;
        let exec_id = exec_created.id;

        let start_opts = StartExecOptions {
            tty: true,
            ..Default::default()
        };

        let start_result = self
            .container
            .docker
            .start_exec(&exec_id, Some(start_opts))
            .await?;

        match start_result {
            StartExecResults::Attached { output, input } => {
                tracing::debug!("Exec bash started, exec_id={exec_id}");
                Ok((IoHandles { input, output }, exec_id))
            }
            StartExecResults::Detached => Err(anyhow::anyhow!(
                "Expected attached exec result but got detached"
            )),
        }
    }

    /// Resizes the TTY of a running exec session.
    pub async fn resize_exec(&self, exec_id: &str, cols: u16, rows: u16) -> anyhow::Result<()> {
        let opts = ResizeExecOptions {
            width: cols,
            height: rows,
        };
        self.container.docker.resize_exec(exec_id, opts).await?;
        Ok(())
    }
}

impl Drop for SharedContainer {
    fn drop(&mut self) {
        // Take the name so only the cleanup thread owns the container identity.
        // This prevents double-cleanup if `Container` ever gains a `Drop` impl.
        let name = std::mem::take(&mut self.container.name);
        if name.is_empty() {
            return; // Already cleaned up (shouldn't happen, but be defensive).
        }
        let docker = self.container.docker.clone();
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
