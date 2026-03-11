//! Docker exec-based PTY session shared by arena and test-container adapters.

use std::sync::Arc;
use std::sync::atomic::AtomicBool;
use std::sync::mpsc::SyncSender;

use anyhow::{Context, Result};
use async_trait::async_trait;
use portable_pty::PtySize;

use super::SharedContainer;
use crate::pty::io::{PtyReader, PtyWriter};
use crate::pty::traits::PtySession;

/// PTY session backed by a `docker exec` process inside a [`SharedContainer`].
///
/// Bridges bollard's async I/O streams to the sync [`PtyReader`]/[`PtyWriter`]
/// types expected by [`PtySession`] using Unix socket pairs and tokio tasks.
///
/// An optional `reader_prefix` can inject bytes (e.g. a scenario prompt)
/// before the live container output stream.
pub struct DockerExecSession {
    container: Arc<SharedContainer>,
    exec_id: String,
    output: std::sync::Mutex<Option<super::OutputStream>>,
    writer_handle: Option<std::os::unix::net::UnixStream>,
    sigint_handle: Arc<std::sync::Mutex<std::os::unix::net::UnixStream>>,
    /// Bytes injected before the live stream in [`PtySession::take_reader`].
    reader_prefix: Option<Vec<u8>>,
}

impl std::fmt::Debug for DockerExecSession {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let has_output = self.output.lock().map(|o| o.is_some()).unwrap_or(false);
        f.debug_struct("DockerExecSession")
            .field("exec_id", &self.exec_id)
            .field("has_output", &has_output)
            .field("has_writer", &self.writer_handle.is_some())
            .field("has_reader_prefix", &self.reader_prefix.is_some())
            .finish_non_exhaustive()
    }
}

impl DockerExecSession {
    /// Creates a new exec-based PTY session inside the shared container.
    ///
    /// Spawns a bash process via `docker exec`, then sets up the async-to-sync
    /// bridge for the writer side. The reader bridge is deferred to
    /// [`PtySession::take_reader`].
    ///
    /// `reader_prefix` is an optional byte payload injected before the live
    /// output stream (used by arena mode to display the scenario prompt).
    pub async fn new(
        container: Arc<SharedContainer>,
        reader_prefix: Option<Vec<u8>>,
    ) -> Result<Self> {
        let (handles, exec_id) = container.exec_session(None).await?;

        let (unix_read, unix_write) = std::os::unix::net::UnixStream::pair()
            .context("Failed to create Unix socket pair for writer bridge")?;

        let sigint_writer = unix_write
            .try_clone()
            .context("Failed to clone Unix socket for sigint")?;

        super::spawn_writer_bridge(unix_read, handles.input)?;

        Ok(Self {
            container,
            exec_id,
            output: std::sync::Mutex::new(Some(handles.output)),
            writer_handle: Some(unix_write),
            sigint_handle: Arc::new(std::sync::Mutex::new(sigint_writer)),
            reader_prefix,
        })
    }
}

#[async_trait]
impl PtySession for DockerExecSession {
    async fn take_reader(&mut self, sender: SyncSender<Vec<u8>>) -> Result<PtyReader> {
        let output = self
            .output
            .lock()
            .expect("output lock poisoned")
            .take()
            .context("Output stream already taken")?;

        let stop_flag = Arc::new(AtomicBool::new(false));
        super::spawn_reader_bridge(self.reader_prefix.take(), output, sender, stop_flag.clone());

        Ok(PtyReader::with_stop_flag(stop_flag))
    }

    async fn take_writer(&mut self) -> Result<Arc<PtyWriter>> {
        let unix_write = self
            .writer_handle
            .take()
            .context("Writer already taken - can only be called once")?;

        Ok(Arc::new(PtyWriter::new(Box::new(unix_write))))
    }

    async fn resize(&self, size: PtySize) -> Result<()> {
        self.container
            .resize_exec(&self.exec_id, size.cols, size.rows)
            .await
            .context("Failed to resize docker exec TTY")
    }

    fn send_sigint(&self) -> Result<()> {
        use std::io::Write as _;
        let mut writer = self
            .sigint_handle
            .lock()
            .expect("sigint handle lock poisoned");
        writer
            .write_all(&[0x03])
            .context("Failed to send Ctrl+C to docker container")
    }
}
