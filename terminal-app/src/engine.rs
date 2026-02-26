//! Engine module — re-exports from infraware-engine for terminal use.

pub use infraware_engine::adapters::MockEngine;
#[cfg(feature = "rig")]
pub use infraware_engine::adapters::RigEngine;
pub use infraware_engine::{
    AgentEvent, AgenticEngine, EngineStatus, EventStream, IncidentPhase, Interrupt, ResumeResponse,
    RunInput, ThreadId,
};
