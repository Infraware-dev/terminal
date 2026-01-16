//! Application state management with State Machine pattern.
//!
//! This module provides a type-safe state machine for application modes
//! with validated transitions and logging.
//!
//! # Architecture
//!
//! ```text
//! EngineStatus (from backend) → AppMode (UI state) → Throbber ON/OFF
//! ```
//!
//! `AppMode` is derived from `EngineStatus` via `From` trait implementation.

use anyhow::{Result, bail};
use infraware_shared::{EngineStatus, Interrupt};

/// Application mode states.
///
/// The state machine enforces valid transitions between modes.
/// Invalid transitions return an error.
#[derive(Debug, Clone, PartialEq, Default)]
#[allow(dead_code)] // Variants used when LLM integration is active
pub enum AppMode {
    /// Normal operation - waiting for user input
    #[default]
    Normal,
    /// Waiting for LLM response after "command not found"
    WaitingLLM,
    /// LLM requested command approval (y/n)
    AwaitingApproval { command: String, message: String },
    /// LLM asked a question (free-text answer)
    AwaitingAnswer {
        question: String,
        options: Option<Vec<String>>,
    },
    /// Executing approved command in PTY, capturing output
    ExecutingCommand { command: String },
}

/// Events that trigger state transitions.
#[derive(Debug, Clone)]
#[expect(
    dead_code,
    reason = "State machine events - used conditionally based on LLM responses"
)]
pub enum AppModeEvent {
    /// User submitted a query that requires LLM
    QueryLLM,
    /// LLM returned and requires command approval
    LLMRequestsApproval { command: String, message: String },
    /// LLM returned and asks a question
    LLMAsksQuestion {
        question: String,
        options: Option<Vec<String>>,
    },
    /// LLM completed without further interaction
    LLMCompleted,
    /// User approved or rejected command
    UserResponded,
    /// User approved command - start PTY execution
    UserApprovedCommand { command: String },
    /// Command finished executing in PTY
    CommandExecuted,
    /// User answered a question
    UserAnswered,
    /// Cancel current operation (Ctrl+C)
    Cancel,
}

/// Derive AppMode from EngineStatus
///
/// This is the primary way to convert backend state to UI state.
/// Throbber is ON when `AppMode::WaitingLLM` (i.e., `EngineStatus::Thinking`).
impl From<EngineStatus> for AppMode {
    fn from(status: EngineStatus) -> Self {
        match status {
            EngineStatus::Ready => Self::Normal,
            EngineStatus::Thinking => Self::WaitingLLM,
            EngineStatus::Interrupted(interrupt) => match interrupt {
                Interrupt::CommandApproval { command, message, .. } => {
                    Self::AwaitingApproval { command, message }
                }
                Interrupt::Question { question, options } => {
                    Self::AwaitingAnswer { question, options }
                }
            },
        }
    }
}

/// Tracks LLM agent stream timing for timeout detection.
///
/// Note: `stream_active` was removed as it's now redundant with
/// `EngineStatus::Thinking`. The throbber is controlled directly
/// by `AppMode::WaitingLLM`.
#[derive(Debug, Clone, Default)]
pub struct AgentState {
    /// Timestamp when the stream started (for timeout detection).
    pub stream_started: Option<std::time::Instant>,
}

impl AgentState {
    /// Create a new agent state with default values.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Mark the stream as started.
    pub fn start_stream(&mut self) {
        self.stream_started = Some(std::time::Instant::now());
    }

    /// Mark the stream as ended.
    pub fn end_stream(&mut self) {
        self.stream_started = None;
    }

    /// Check if the stream has timed out.
    #[must_use]
    #[expect(dead_code, reason = "Reserved for future timeout detection")]
    pub fn is_timed_out(&self, timeout: std::time::Duration) -> bool {
        self.stream_started
            .map(|started| started.elapsed() > timeout)
            .unwrap_or(false)
    }
}

#[allow(dead_code)] // State machine API used when LLM integration is active
impl AppMode {
    /// Get the name of the current state (for logging).
    #[must_use]
    pub fn name(&self) -> &'static str {
        match self {
            Self::Normal => "Normal",
            Self::WaitingLLM => "WaitingLLM",
            Self::AwaitingApproval { .. } => "AwaitingApproval",
            Self::AwaitingAnswer { .. } => "AwaitingAnswer",
            Self::ExecutingCommand { .. } => "ExecutingCommand",
        }
    }

    /// Check if a transition to the target state is valid.
    ///
    /// Valid transitions:
    /// - Normal → WaitingLLM (user query)
    /// - WaitingLLM → Normal (LLM completed)
    /// - WaitingLLM → AwaitingApproval (LLM requests approval)
    /// - WaitingLLM → AwaitingAnswer (LLM asks question)
    /// - AwaitingApproval → Normal (user rejected)
    /// - AwaitingApproval → ExecutingCommand (user approved, command sent to PTY)
    /// - AwaitingApproval → WaitingLLM (legacy: resume after approval)
    /// - AwaitingAnswer → Normal (user answered)
    /// - AwaitingAnswer → WaitingLLM (resume with answer)
    /// - ExecutingCommand → WaitingLLM (command finished, output sent to backend)
    /// - ExecutingCommand → Normal (user cancelled)
    /// - Any → Normal (cancel)
    #[must_use]
    pub fn can_transition_to(&self, target: &Self) -> bool {
        match (self, target) {
            // From Normal
            (Self::Normal, Self::WaitingLLM) => true,

            // From WaitingLLM
            (Self::WaitingLLM, Self::Normal) => true,
            (Self::WaitingLLM, Self::AwaitingApproval { .. }) => true,
            (Self::WaitingLLM, Self::AwaitingAnswer { .. }) => true,

            // From AwaitingApproval
            (Self::AwaitingApproval { .. }, Self::Normal) => true,
            (Self::AwaitingApproval { .. }, Self::WaitingLLM) => true,
            (Self::AwaitingApproval { .. }, Self::ExecutingCommand { .. }) => true,

            // From AwaitingAnswer
            (Self::AwaitingAnswer { .. }, Self::Normal) => true,
            (Self::AwaitingAnswer { .. }, Self::WaitingLLM) => true,

            // From ExecutingCommand
            (Self::ExecutingCommand { .. }, Self::WaitingLLM) => true,
            (Self::ExecutingCommand { .. }, Self::Normal) => true,

            // Same state (idempotent transitions are valid)
            (Self::Normal, Self::Normal)
            | (Self::WaitingLLM, Self::WaitingLLM)
            | (Self::AwaitingApproval { .. }, Self::AwaitingApproval { .. })
            | (Self::AwaitingAnswer { .. }, Self::AwaitingAnswer { .. })
            | (Self::ExecutingCommand { .. }, Self::ExecutingCommand { .. }) => true,

            // All others invalid
            _ => false,
        }
    }

    /// Attempt to transition to a new state based on an event.
    ///
    /// Consumes both self and event to avoid unnecessary cloning.
    /// Returns the new state if the transition is valid, or an error otherwise.
    #[must_use = "state transitions must be handled - ignoring may cause state desynchronization"]
    pub fn transition(self, event: AppModeEvent) -> Result<Self> {
        let from_name = self.name();

        let new_state = match (self, event) {
            // Normal state transitions
            (Self::Normal, AppModeEvent::QueryLLM) => Self::WaitingLLM,

            // WaitingLLM state transitions
            (Self::WaitingLLM, AppModeEvent::LLMCompleted) => Self::Normal,
            (Self::WaitingLLM, AppModeEvent::LLMRequestsApproval { command, message }) => {
                Self::AwaitingApproval { command, message }
            }
            (Self::WaitingLLM, AppModeEvent::LLMAsksQuestion { question, options }) => {
                Self::AwaitingAnswer { question, options }
            }

            // AwaitingApproval state transitions
            (Self::AwaitingApproval { .. }, AppModeEvent::UserResponded) => Self::Normal,
            (Self::AwaitingApproval { .. }, AppModeEvent::UserApprovedCommand { command }) => {
                Self::ExecutingCommand { command }
            }

            // ExecutingCommand state transitions
            (Self::ExecutingCommand { .. }, AppModeEvent::CommandExecuted) => Self::WaitingLLM,

            // AwaitingAnswer state transitions
            (Self::AwaitingAnswer { .. }, AppModeEvent::UserAnswered) => Self::Normal,

            // Cancel from any state
            (_, AppModeEvent::Cancel) => Self::Normal,

            // Invalid transition
            (state, event) => {
                bail!("Invalid state transition: {} + {:?}", state.name(), event);
            }
        };

        log::debug!("State transition: {} -> {}", from_name, new_state.name());

        Ok(new_state)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_state() {
        assert_eq!(AppMode::default(), AppMode::Normal);
    }

    #[test]
    fn test_valid_transitions() {
        // Normal → WaitingLLM
        let state = AppMode::Normal;
        assert!(state.can_transition_to(&AppMode::WaitingLLM));

        // WaitingLLM → Normal
        let state = AppMode::WaitingLLM;
        assert!(state.can_transition_to(&AppMode::Normal));

        // WaitingLLM → AwaitingApproval
        assert!(state.can_transition_to(&AppMode::AwaitingApproval {
            command: "test".to_string(),
            message: "msg".to_string(),
        }));

        // AwaitingApproval → Normal
        let state = AppMode::AwaitingApproval {
            command: "test".to_string(),
            message: "msg".to_string(),
        };
        assert!(state.can_transition_to(&AppMode::Normal));
    }

    #[test]
    fn test_invalid_transitions() {
        // Normal → AwaitingApproval (must go through WaitingLLM)
        let state = AppMode::Normal;
        assert!(!state.can_transition_to(&AppMode::AwaitingApproval {
            command: "test".to_string(),
            message: "msg".to_string(),
        }));

        // Normal → AwaitingAnswer (must go through WaitingLLM)
        assert!(!state.can_transition_to(&AppMode::AwaitingAnswer {
            question: "test?".to_string(),
            options: None,
        }));
    }

    #[test]
    fn test_transition_with_event() {
        let state = AppMode::Normal;

        // Valid transition (clone state for second test)
        let new_state = state.clone().transition(AppModeEvent::QueryLLM).unwrap();
        assert_eq!(new_state, AppMode::WaitingLLM);

        // Invalid transition (Normal + UserResponded)
        let result = state.transition(AppModeEvent::UserResponded);
        assert!(result.is_err());
    }

    #[test]
    fn test_cancel_from_any_state() {
        // Cancel from WaitingLLM
        let state = AppMode::WaitingLLM;
        let new_state = state.transition(AppModeEvent::Cancel).unwrap();
        assert_eq!(new_state, AppMode::Normal);

        // Cancel from AwaitingApproval
        let state = AppMode::AwaitingApproval {
            command: "test".to_string(),
            message: "msg".to_string(),
        };
        let new_state = state.transition(AppModeEvent::Cancel).unwrap();
        assert_eq!(new_state, AppMode::Normal);
    }

    #[test]
    fn test_state_names() {
        assert_eq!(AppMode::Normal.name(), "Normal");
        assert_eq!(AppMode::WaitingLLM.name(), "WaitingLLM");
        assert_eq!(
            AppMode::AwaitingApproval {
                command: "test".to_string(),
                message: "msg".to_string()
            }
            .name(),
            "AwaitingApproval"
        );
    }

    #[test]
    fn test_transition_moves_data() {
        // Test that event data is moved, not cloned
        let state = AppMode::WaitingLLM;
        let event = AppModeEvent::LLMRequestsApproval {
            command: "rm -rf /".to_string(),
            message: "Are you sure?".to_string(),
        };

        let new_state = state.transition(event).unwrap();

        match new_state {
            AppMode::AwaitingApproval { command, message } => {
                assert_eq!(command, "rm -rf /");
                assert_eq!(message, "Are you sure?");
            }
            _ => panic!("Expected AwaitingApproval state"),
        }
    }

    // Tests for From<EngineStatus> implementation

    #[test]
    fn test_from_engine_status_ready() {
        let status = EngineStatus::Ready;
        let mode: AppMode = status.into();
        assert_eq!(mode, AppMode::Normal);
    }

    #[test]
    fn test_from_engine_status_thinking() {
        let status = EngineStatus::Thinking;
        let mode: AppMode = status.into();
        assert_eq!(mode, AppMode::WaitingLLM);
    }

    #[test]
    fn test_from_engine_status_interrupted_command() {
        let status = EngineStatus::Interrupted(Interrupt::CommandApproval {
            command: "ls -la".to_string(),
            message: "List files".to_string(),
            needs_continuation: false,
        });
        let mode: AppMode = status.into();
        assert_eq!(
            mode,
            AppMode::AwaitingApproval {
                command: "ls -la".to_string(),
                message: "List files".to_string(),
            }
        );
    }

    #[test]
    fn test_from_engine_status_interrupted_question() {
        let status = EngineStatus::Interrupted(Interrupt::Question {
            question: "Which env?".to_string(),
            options: Some(vec!["dev".to_string(), "prod".to_string()]),
        });
        let mode: AppMode = status.into();
        assert_eq!(
            mode,
            AppMode::AwaitingAnswer {
                question: "Which env?".to_string(),
                options: Some(vec!["dev".to_string(), "prod".to_string()]),
            }
        );
    }

    #[test]
    fn test_from_engine_status_question_no_options() {
        let status = EngineStatus::Interrupted(Interrupt::Question {
            question: "What name?".to_string(),
            options: None,
        });
        let mode: AppMode = status.into();
        assert_eq!(
            mode,
            AppMode::AwaitingAnswer {
                question: "What name?".to_string(),
                options: None,
            }
        );
    }
}
