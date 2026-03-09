//! Core application state management.
//!
//! Contains `AppState` which holds the mutable state of the terminal application
//! including sessions, buffers, and control flags. This module is designed to be
//! testable without egui dependencies.

use std::collections::HashMap;
#[cfg(feature = "pty-test_container")]
use std::sync::Arc;

use crate::app::PtyProviderType;
#[cfg(feature = "pty-test_container")]
use crate::pty::SharedContainer;
use crate::session::{SessionId, TerminalSession};

/// Core application state holding sessions and control flags.
///
/// This struct contains all mutable state that is independent of the UI framework,
/// making it suitable for unit testing.
#[derive(Debug)]
pub struct AppState {
    /// All terminal sessions, keyed by session ID
    pub sessions: HashMap<SessionId, TerminalSession>,

    /// Pty provider type for new sessions
    pub pty_provider_type: PtyProviderType,

    /// Shared test container (if using test container backend).
    /// Created once at startup; cloned into each new session's `PtyProvider`.
    #[cfg(feature = "pty-test_container")]
    pub shared_container: Option<Arc<SharedContainer>>,

    /// Currently focused session ID
    pub active_session_id: SessionId,

    /// Next session ID to assign (monotonically increasing)
    pub next_session_id: SessionId,

    /// Buffer for collecting user input during HITL interactions
    pub current_input_buffer: String,

    /// Buffer for tracking the current command line (for classification)
    pub current_command_buffer: String,

    /// Flag to quit application
    pub should_quit: bool,
}

impl AppState {
    /// Creates a new application state with initial sessions.
    pub fn new(
        sessions: HashMap<SessionId, TerminalSession>,
        active_session_id: SessionId,
        pty_provider_type: PtyProviderType,
        #[cfg(feature = "pty-test_container")] shared_container: Option<Arc<SharedContainer>>,
    ) -> Self {
        let next_session_id = sessions.keys().max().map(|&id| id + 1).unwrap_or(0);

        Self {
            sessions,
            active_session_id,
            next_session_id,
            pty_provider_type,
            #[cfg(feature = "pty-test_container")]
            shared_container,
            current_input_buffer: String::new(),
            current_command_buffer: String::new(),
            should_quit: false,
        }
    }

    /// Builds a [`crate::pty::PtyProvider`] for creating a new session.
    pub fn pty_provider(&self) -> crate::pty::PtyProvider {
        match self.pty_provider_type {
            PtyProviderType::Local => crate::pty::PtyProvider::Local,
            #[cfg(feature = "pty-test_container")]
            PtyProviderType::TestContainer => {
                let shared = self
                    .shared_container
                    .clone()
                    .expect("SharedContainer not initialized for TestContainer provider");
                crate::pty::PtyProvider::TestContainer { shared }
            }
        }
    }

    /// Returns a reference to the active session.
    pub fn active_session(&self) -> Option<&TerminalSession> {
        self.sessions.get(&self.active_session_id)
    }

    /// Returns a mutable reference to the active session.
    pub fn active_session_mut(&mut self) -> Option<&mut TerminalSession> {
        self.sessions.get_mut(&self.active_session_id)
    }

    /// Returns the next session ID and increments the counter.
    pub fn allocate_session_id(&mut self) -> SessionId {
        let id = self.next_session_id;
        self.next_session_id += 1;
        id
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_state() -> AppState {
        // Create empty state for testing (no real sessions needed for state logic tests)
        AppState {
            sessions: HashMap::new(),
            active_session_id: 0,
            next_session_id: 1,
            current_input_buffer: String::new(),
            current_command_buffer: String::new(),
            pty_provider_type: PtyProviderType::Local,
            #[cfg(feature = "pty-test_container")]
            shared_container: None,
            should_quit: false,
        }
    }

    #[test]
    fn test_allocate_session_id() {
        let mut state = create_test_state();
        assert_eq!(state.allocate_session_id(), 1);
        assert_eq!(state.allocate_session_id(), 2);
        assert_eq!(state.allocate_session_id(), 3);
        assert_eq!(state.next_session_id, 4);
    }

    #[test]
    fn test_input_buffer_manipulation() {
        let mut state = create_test_state();
        state.current_input_buffer = "test input".to_string();

        let taken = std::mem::take(&mut state.current_input_buffer);
        assert_eq!(taken, "test input");
        assert!(state.current_input_buffer.is_empty());
    }

    #[test]
    fn test_command_buffer_manipulation() {
        let mut state = create_test_state();
        state.current_command_buffer = "some command".to_string();

        state.current_command_buffer.clear();
        assert!(state.current_command_buffer.is_empty());
    }

    #[test]
    fn test_sessions_empty() {
        let state = create_test_state();
        assert_eq!(state.sessions.len(), 0);
    }

    #[test]
    fn test_sessions_contains_key() {
        let state = create_test_state();
        assert!(!state.sessions.contains_key(&0));
        assert!(!state.sessions.contains_key(&1));
    }

    #[test]
    fn test_active_session_none() {
        let state = create_test_state();
        assert!(state.active_session().is_none());
    }
}
