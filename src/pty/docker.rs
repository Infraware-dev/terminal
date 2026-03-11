//! Shared Docker container primitives used by both the test-container and arena adapters.

mod container;
mod exec_session;
mod shared;

use std::pin::Pin;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::SyncSender;

use anyhow::{Context, Result};
use bollard::container::LogOutput;
use futures::{Stream, StreamExt as _};
use tokio::io::{AsyncReadExt as _, AsyncWriteExt as _};

pub use self::container::ContainerConfig;
pub use self::exec_session::DockerExecSession;
pub use self::shared::SharedContainer;

/// Container IO streams for interacting with a Docker exec or attach session.
pub struct IoHandles {
    pub input: Pin<Box<dyn tokio::io::AsyncWrite + Send>>,
    pub output: Pin<Box<dyn Stream<Item = Result<LogOutput, bollard::errors::Error>> + Send>>,
}

impl std::fmt::Debug for IoHandles {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("IoHandles").finish_non_exhaustive()
    }
}

/// Boxed async output stream from a Docker container.
pub type OutputStream =
    Pin<Box<dyn Stream<Item = Result<LogOutput, bollard::errors::Error>> + Send>>;

/// Spawns a tokio task that forwards bytes from a sync Unix socket to an
/// async Docker stdin stream.
///
/// ```text
/// PtyWriter -> unix_write --> unix_read (this task) --> bollard input
/// ```
pub fn spawn_writer_bridge(
    unix_read: std::os::unix::net::UnixStream,
    mut input: Pin<Box<dyn tokio::io::AsyncWrite + Send>>,
) -> Result<()> {
    unix_read
        .set_nonblocking(true)
        .context("Failed to set Unix socket to non-blocking")?;
    let mut async_read = tokio::net::UnixStream::from_std(unix_read)
        .context("Failed to convert Unix socket to tokio")?;

    tokio::spawn(async move {
        let mut buf = vec![0u8; 4096];
        loop {
            match async_read.read(&mut buf).await {
                Ok(0) => break,
                Ok(n) => {
                    if input.write_all(&buf[..n]).await.is_err() {
                        break;
                    }
                    if input.flush().await.is_err() {
                        break;
                    }
                }
                Err(e) => {
                    tracing::debug!("Docker writer bridge error: {e}");
                    break;
                }
            }
        }
        tracing::debug!("Docker writer bridge task exiting");
    });

    Ok(())
}

/// Spawns a tokio task that drains a Docker async output stream into a sync
/// channel, optionally injecting a prefix message before the live stream.
///
/// ```text
/// bollard output --> this task --> SyncSender --> consumer
/// ```
pub fn spawn_reader_bridge(
    prefix: Option<Vec<u8>>,
    mut output: OutputStream,
    sender: SyncSender<Vec<u8>>,
    stop_flag: Arc<AtomicBool>,
) {
    tokio::spawn(async move {
        // Inject optional prefix (e.g. scenario prompt) before live stream
        if let Some(data) = prefix
            && sender.send(data).is_err()
        {
            return;
        }

        while let Some(chunk) = output.next().await {
            if stop_flag.load(Ordering::Acquire) {
                break;
            }
            match chunk {
                Ok(log_output) => {
                    let bytes = match log_output {
                        LogOutput::Console { message }
                        | LogOutput::StdOut { message }
                        | LogOutput::StdErr { message } => message,
                        _ => continue,
                    };
                    if sender.send(bytes.to_vec()).is_err() {
                        break;
                    }
                }
                Err(e) => {
                    tracing::debug!("Docker output stream error: {e}");
                    break;
                }
            }
        }
        tracing::debug!("Docker output reader task exiting");
    });
}

/// Parses a Docker image reference into `(repo, tag)`.
///
/// - `"nginx:1.25"` -> `("nginx", "1.25")`
/// - `"nginx"` -> `("nginx", "latest")`
/// - `"registry.io:5000/org/image:v2"` -> `("registry.io:5000/org/image", "v2")`
pub fn parse_image_ref(image: &str) -> (&str, &str) {
    match image.rsplit_once(':') {
        Some((repo, tag)) if !repo.is_empty() && !tag.contains('/') => (repo, tag),
        _ => (image, "latest"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_image_with_tag() {
        assert_eq!(parse_image_ref("nginx:1.25"), ("nginx", "1.25"));
    }

    #[test]
    fn parse_image_without_tag() {
        assert_eq!(parse_image_ref("nginx"), ("nginx", "latest"));
    }

    #[test]
    fn parse_image_with_registry_and_tag() {
        assert_eq!(
            parse_image_ref("registry.io/org/image:v2"),
            ("registry.io/org/image", "v2")
        );
    }

    #[test]
    fn parse_image_with_registry_no_tag() {
        assert_eq!(
            parse_image_ref("registry.io/org/image"),
            ("registry.io/org/image", "latest")
        );
    }

    #[test]
    fn parse_image_with_port_in_registry() {
        assert_eq!(
            parse_image_ref("localhost:5000/myimage:v1"),
            ("localhost:5000/myimage", "v1")
        );
    }
}
