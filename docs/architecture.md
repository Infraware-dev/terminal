# Architecture

Infraware Terminal is a single-crate Rust application that combines a GPU-accelerated terminal emulator
with an in-process agentic LLM engine for DevOps assistance.

## High-Level Overview

```
+---------------------------------------------------+
| infraware-terminal (single binary)                |
|                                                   |
|  +-------------+     +------------------------+  |
|  | Terminal UI  |     | AgenticEngine (trait)  |  |
|  | (egui/eframe)|<-->| +--------+ +---------+ |  |
|  +------+------+     | | Mock   | | Rig     | |  |
|         |            | | Engine | | Engine  | |  |
|    +----v----+       | +--------+ +----+----+ |  |
|    |   PTY   |       +----------------+-------+  |
|    | Manager |                        |           |
|    |(dyn Pty |                        |           |
|    | Session)|                        |           |
|    +----+----+                        |           |
|         |                             |           |
|    +----v----+                 +------v------+    |
|    |  VTE    |                 | Anthropic   |    |
|    | Parser  |                 | API         |    |
|    +----+----+                 +-------------+    |
|         |                                         |
|    +----v----+          PTY Adapters:             |
|    |Terminal |    - LocalPtySession (default)     |
|    |  Grid   |    - DockerExecSession             |
|    +---------+      (test container / arena)      |
+---------------------------------------------------+
```

## Module Map

```
src/
+-- main.rs                # Entry point
+-- app.rs                 # InfrawareApp struct, eframe::App impl
+-- app/                   # App submodules (handler pattern)
|   +-- input_handler.rs   # Keyboard input processing
|   +-- hitl_handler.rs    # Human-in-the-loop approval/answer flows
|   +-- llm_controller.rs  # LLM query management, background event dispatch
|   +-- llm_event_handler.rs  # Engine event stream handling
|   +-- session_manager.rs # Session lifecycle (create, close, init)
|   +-- tiles_manager.rs   # Split view and tab management (egui_tiles)
|   +-- clipboard.rs       # Copy/paste operations
|   +-- render.rs          # Terminal rendering state and helpers
|   +-- terminal_renderer.rs  # Pure rendering (cell painting, cursor)
|   +-- behavior.rs        # egui_tiles Behavior trait impl
|   +-- state.rs           # Core application state struct
+-- state.rs               # AppMode state machine, AgentState
+-- session.rs             # TerminalSession (PTY + VTE + state per tab)
+-- config.rs              # Constants (timing, rendering, sizes)
+-- engine.rs              # Engine module root (re-exports)
+-- engine/                # AgenticEngine trait + adapters
|   +-- traits.rs          # AgenticEngine trait, EventStream type
|   +-- error.rs           # EngineError type
|   +-- types.rs           # HealthStatus, ResumeResponse
|   +-- shared/            # Shared types
|   |   +-- events.rs      # AgentEvent enum
|   |   +-- models.rs      # Message, ThreadId, RunInput, etc.
|   +-- adapters/
|       +-- mock/          # MockEngine (testing, no external deps)
|       +-- rig/           # RigEngine (Anthropic Claude, default)
+-- terminal/              # VTE parser, grid, cell attributes
+-- pty/                   # PTY session trait, adapters, async I/O
|   +-- adapters/
|   |   +-- local.rs       # LocalPtySession (host shell)
|   |   +-- arena/         # Arena scenario mode
|   +-- docker/            # Shared Docker container primitives
|       +-- container.rs   # Container lifecycle, ContainerConfig
|       +-- shared.rs      # SharedContainer (Arc, exec_session)
|       +-- exec_session.rs # DockerExecSession (PtySession impl)
+-- llm/                   # Markdown-to-ANSI renderer (syntect)
+-- input/                 # Keyboard mapping, text selection, command classification
+-- orchestrators/         # hitl.rs utility (parse_approval)
+-- ui/                    # egui helpers, theme, scrollbar
```

## Core Components

### Terminal UI (egui/eframe)

The application uses `egui` (via `eframe`) for rendering. The main `InfrawareApp` struct implements
`eframe::App` and delegates to focused handler modules following a handler pattern:

- **InputHandler** processes keyboard events and classifies user input
- **HitlHandler** manages human-in-the-loop flows (command approval, question answering)
- **LlmController** drives agent queries and dispatches background events
- **LlmEventHandler** processes the engine's event stream
- **SessionManager** manages session lifecycle across tabs
- **TilesManager** handles tab and split-pane layout via `egui_tiles`

### State Machine

Each terminal session tracks its own mode via `AppMode`:

```
Normal
  |
  +--(? query)--> WaitingLLM --+--> AwaitingApproval (y/n for commands)
                               |       | (approve) --> ExecutingCommand
                               |       |                    |
                               |       |                    +--> WaitingLLM (needs_continuation=true)
                               |       |                    |
                               |       |                    +--> Normal (needs_continuation=false)
                               |       |
                               |       +--> Normal (reject)
                               |
                               +--> AwaitingAnswer (free-text questions)
                               |       +--> WaitingLLM (resume with answer)
                               |
                               +--> Normal (complete)
```

The `needs_continuation` flag on `ExecutingCommand` distinguishes between commands whose output IS the
answer (e.g., `ls`) and commands whose output is INPUT for further agent reasoning (e.g., `uname -s` to
determine OS-specific instructions).

### AgenticEngine

The `AgenticEngine` trait abstracts over LLM backends:

```rust
#[async_trait]
pub trait AgenticEngine: Send + Sync + Debug {
    async fn create_thread(&self, metadata: Option<Value>) -> Result<ThreadId, EngineError>;
    async fn stream_run(&self, thread_id: &ThreadId, input: RunInput) -> Result<EventStream, EngineError>;
    async fn resume_run(&self, thread_id: &ThreadId, response: ResumeResponse) -> Result<EventStream, EngineError>;
    async fn health_check(&self) -> Result<HealthStatus, EngineError>;
}
```

Two implementations are provided:

- **RigEngine** (default) -- native Rust agent using `rig-rs` with Anthropic Claude. Supports function
  calling (shell commands, ask user, diagnostics, incident investigation), human-in-the-loop approval via
  `PromptHook`, and persistent/session memory.
- **MockEngine** -- in-memory workflow-based matching for testing without external dependencies.

### PTY System

The PTY layer is pluggable via the `PtySession` trait. Each `TerminalSession` owns a PTY backend:

- **LocalPtySession** (default) -- spawns a host shell process via `portable-pty`
- **DockerExecSession** -- runs inside a Docker container, shared by both the test container and arena backends

All backends provide `take_reader()`, `take_writer()`, `resize()`, and `send_sigint()`.

For details, see [pty-backends.md](pty-backends.md).

### VTE Terminal Emulation

The `terminal/` module implements a VTE (Virtual Terminal Emulator) parser that processes ANSI escape
sequences and maintains a character grid. The parser handles:

- CSI sequences (cursor movement, scrolling, text attributes)
- OSC sequences (window title, hyperlinks)
- SGR attributes (colors, bold, italic, underline)

### Memory System

The Rig engine includes two complementary memory systems:

- **Persistent memory** -- user facts stored across sessions in a JSON file (preferences, workflows, restrictions)
- **Session context** -- ephemeral facts discovered during the current session (OS info, service state)

Both are injected into the agent's system prompt and exposed as LLM-callable tools.

For details, see [memory-system.md](memory-system.md).

### Incident Investigation Pipeline

A multi-phase pipeline for production incident investigation:

1. **Investigation** -- scoping questions + diagnostic commands (HITL)
2. **Analysis** -- structured root cause analysis (pure LLM)
3. **Reporting** -- post-mortem report saved to disk
4. **Planning** -- remediation plan with review loop
5. **Execution** -- step-by-step plan execution (HITL)

For details, see [incident-investigation.md](incident-investigation.md).

## Key Dependencies

| Category | Crate | Purpose |
|----------|-------|---------|
| GUI | `egui`, `eframe`, `egui_tiles` | Terminal UI, window management |
| Terminal | `portable-pty`, `vte` | PTY management, escape sequence parsing |
| Async | `tokio`, `async-trait`, `futures` | Async runtime |
| AI | `rig-core` | Anthropic Claude agent framework |
| Docker | `bollard` | Docker API (optional) |
| Serialization | `serde`, `serde_json` | Data serialization |
| Error handling | `anyhow`, `thiserror` | Error types |
| Logging | `tracing`, `tracing-subscriber` | Structured logging |
| CLI | `clap` | Command-line argument parsing |

## Feature Flags

| Feature | Dependencies | Description |
|---------|-------------|-------------|
| `rig` *(default)* | `rig-core`, `chrono`, `schemars` | Anthropic Claude agent |
| `docker` | `bollard` | Base Docker support |
| `pty-test_container` | `docker` | Docker container PTY sandbox |
| `arena` | `docker` | Arena incident investigation challenges |
