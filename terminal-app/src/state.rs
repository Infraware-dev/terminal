//! Application state management.

/// Application mode states.
///
/// Note: Some variants are currently unused but will be used in Phase 4 (State Machine).
#[derive(Debug, Clone, PartialEq)]
#[allow(dead_code)]
pub enum AppMode {
    /// Normal operation - waiting for user input
    Normal,
    /// Waiting for LLM response after "command not found"
    WaitingLLM,
    /// LLM requested command approval (y/n)
    AwaitingApproval {
        command: String,
        message: String,
    },
    /// LLM asked a question (free-text answer)
    AwaitingAnswer {
        question: String,
        options: Option<Vec<String>>,
    },
}

impl Default for AppMode {
    fn default() -> Self {
        Self::Normal
    }
}
