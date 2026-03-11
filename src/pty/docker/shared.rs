//! Shared container handle for reusing a single Docker container across terminal sessions.

use std::sync::Arc;

#[cfg(feature = "arena")]
use bollard::container::LogOutput;
use bollard::exec::{CreateExecOptions, ResizeExecOptions, StartExecOptions, StartExecResults};
#[cfg(feature = "arena")]
use futures::StreamExt as _;

use super::IoHandles;
use super::container::{Container, ContainerConfig};

/// A reference-counted handle to a shared Docker container.
///
/// The container is stopped and removed when the last `Arc<SharedContainer>`
/// is dropped. Individual sessions interact with the container via
/// [`exec_bash`](Self::exec_bash).
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
    /// Creates and starts a Docker container with the given configuration.
    pub async fn setup(config: ContainerConfig) -> anyhow::Result<Arc<Self>> {
        let container = Container::setup(config).await?;
        let runtime_handle = tokio::runtime::Handle::current();

        Ok(Arc::new(Self {
            container,
            runtime_handle,
        }))
    }

    /// Spawns a new interactive process inside the container via `docker exec`.
    ///
    /// When `cmd` is `None`, runs `/bin/bash`. Pass a custom command to run
    /// something else (e.g. a wrapper that prints a banner before exec'ing bash).
    ///
    /// Returns the IO handles and the exec ID (needed for [`resize_exec`](Self::resize_exec)).
    pub async fn exec_session(
        &self,
        cmd: Option<Vec<String>>,
    ) -> anyhow::Result<(IoHandles, String)> {
        let cmd = cmd.unwrap_or_else(|| vec!["/bin/bash".to_string()]);
        let cmd_refs: Vec<&str> = cmd.iter().map(String::as_str).collect();
        let exec_opts = CreateExecOptions {
            attach_stdin: Some(true),
            attach_stdout: Some(true),
            attach_stderr: Some(true),
            tty: Some(true),
            cmd: Some(cmd_refs),
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

    /// Reads a file from inside the running container via `docker exec cat <path>`.
    #[cfg(feature = "arena")]
    pub async fn exec_read_file(&self, path: &str) -> anyhow::Result<String> {
        let exec_opts = CreateExecOptions {
            attach_stdout: Some(true),
            attach_stderr: Some(true),
            cmd: Some(vec!["cat", path]),
            ..Default::default()
        };

        let exec = self
            .container
            .docker
            .create_exec(&self.container.name, exec_opts)
            .await?;

        let start_opts = StartExecOptions {
            ..Default::default()
        };
        let start_result = self
            .container
            .docker
            .start_exec(&exec.id, Some(start_opts))
            .await?;

        let mut result = String::new();
        match start_result {
            StartExecResults::Attached { mut output, .. } => {
                while let Some(chunk) = output.next().await {
                    match chunk? {
                        LogOutput::StdOut { message } => {
                            result.push_str(&String::from_utf8_lossy(&message));
                        }
                        LogOutput::StdErr { message } => {
                            let stderr = String::from_utf8_lossy(&message);
                            if !stderr.trim().is_empty() {
                                return Err(anyhow::anyhow!(
                                    "Error reading {path} from container: {stderr}"
                                ));
                            }
                        }
                        _ => {}
                    }
                }
            }
            StartExecResults::Detached => {
                return Err(anyhow::anyhow!(
                    "Expected attached exec result but got detached"
                ));
            }
        }

        Ok(result)
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
        let name = std::mem::take(&mut self.container.name);
        if name.is_empty() {
            return;
        }
        let docker = self.container.docker.clone();
        let image_ref = std::mem::take(&mut self.container.image_ref);
        let handle = self.runtime_handle.clone();
        let join_handle = std::thread::spawn(move || {
            let container = Container {
                docker,
                name,
                image_ref,
            };
            if let Err(e) = handle.block_on(container.stop()) {
                tracing::error!("Failed to stop shared container on drop: {e}");
            }
        });
        if let Err(e) = join_handle.join() {
            tracing::error!("Shared container cleanup thread panicked: {e:?}");
        }
    }
}
