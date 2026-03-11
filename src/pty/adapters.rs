//! PTY session adapters for different transport layers.

#[cfg(feature = "arena")]
mod arena;
mod local;

#[cfg(feature = "arena")]
pub use self::arena::ScenarioManifest;
pub use self::local::LocalPtySession;
