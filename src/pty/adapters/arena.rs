//! Arena scenario types for incident investigation challenges.
//!
//! The PTY session itself is handled by [`crate::pty::docker::DockerExecSession`];
//! this module provides the scenario manifest parsing and prompt formatting.

mod scenario;

pub use self::scenario::ScenarioManifest;
