//! Trait definitions for PTY abstraction.
//!
//! These traits enable dependency injection and testing without a real PTY.
//! Currently unused but provide foundation for future testability improvements.

use anyhow::Result;

/// Trait for writing to a PTY.
///
/// This abstraction allows for mock implementations in tests.
#[allow(dead_code)]
pub trait PtyWrite: Send + Sync {
    /// Write bytes to the PTY.
    fn write_bytes(&self, data: &[u8]) -> Result<usize>;
}

/// Trait for PTY session management.
///
/// This abstraction allows for mock implementations in tests.
#[allow(dead_code)]
pub trait PtyControl: Send + Sync {
    /// Resize the terminal.
    fn resize(&self, rows: u16, cols: u16) -> Result<()>;

    /// Send SIGINT to the foreground process.
    fn send_sigint(&self) -> Result<()>;
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    /// Mock PTY writer for testing.
    struct MockPtyWriter {
        bytes_written: AtomicUsize,
    }

    impl MockPtyWriter {
        fn new() -> Self {
            Self {
                bytes_written: AtomicUsize::new(0),
            }
        }

        fn bytes_written(&self) -> usize {
            self.bytes_written.load(Ordering::SeqCst)
        }
    }

    impl PtyWrite for MockPtyWriter {
        fn write_bytes(&self, data: &[u8]) -> Result<usize> {
            self.bytes_written.fetch_add(data.len(), Ordering::SeqCst);
            Ok(data.len())
        }
    }

    #[test]
    fn test_mock_pty_writer() {
        let writer = Arc::new(MockPtyWriter::new());
        assert_eq!(writer.bytes_written(), 0);

        writer.write_bytes(b"hello").unwrap();
        assert_eq!(writer.bytes_written(), 5);

        writer.write_bytes(b" world").unwrap();
        assert_eq!(writer.bytes_written(), 11);
    }
}
