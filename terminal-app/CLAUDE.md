# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Infraware Terminal** is a hybrid command interpreter with AI assistance for DevOps operations. It's NOT a traditional terminal emulator - it intelligently routes user input to either shell command execution or an LLM backend for natural language queries.

**Current Status**: M1 (Month 1) - Terminal Core MVP
**Tech Stack**: Rust + TUI (ratatui/crossterm)
**Target Users**: DevOps engineers working with cloud environments (AWS/Azure)

**Prerequisites**:
- Linux systems require OpenSSL development libraries: `sudo apt update && sudo apt install -y pkg-config libssl-dev`
- Coverage reporting requires `cargo-llvm-cov`: Install with `cargo install cargo-llvm-cov`

## Commands

### Build and Run
```bash
# Build the project
cargo build

# Build release version
cargo build --release

# Run the application
cargo run

# Run with cargo watch for development
cargo watch -x run
```

### Benchmarking
```bash
# Run performance benchmarks
cargo bench

# Run specific benchmark
cargo bench scan_
```

### Testing
```bash
# Run all tests
cargo test

# Run specific test file
cargo test --test classifier_tests
cargo test --test executor_tests
cargo test --test integration_tests

# Run tests with output
cargo test -- --nocapture

# Run tests for a specific module
cargo test classifier
cargo test executor
```

### Development
```bash
# Check code without building
cargo check

# Format code
cargo fmt

# Run linter (run before commits)
cargo clippy

# Fix clippy warnings automatically where possible
cargo clippy --fix

# Run code coverage
cargo llvm-cov --all-features --workspace --lcov --output-path lcov.info

# Clean build artifacts
cargo clean
```

## Architecture

### Core Flow
```
User Input → InputClassifier → [Command Path | Natural Language Path]
              ↓                           ↓
         CommandExecutor             LLMClient
              ↓                           ↓
         Shell Output              ResponseRenderer
```

### Module Structure

**`terminal/`** - TUI rendering and state management
- `tui.rs`: ratatui rendering logic
- `state.rs`: Terminal state composition with buffer components
- `buffers.rs`: **SRP-compliant buffer components** (OutputBuffer, InputBuffer, CommandHistory)
- `events.rs`: Keyboard event handling

**`input/`** - Input classification and parsing (**SCAN Algorithm** - Shell-Command And Natural-language)
- `classifier.rs`: Main InputClassifier coordinating the 7-handler chain
- `handler.rs`: **Chain of Responsibility** implementation with 7 handlers:
  1. EmptyInputHandler - Fast path for empty/whitespace input
  2. PathCommandHandler - Executable paths (./script.sh, /usr/bin/cmd) with platform-specific checks
  3. KnownCommandHandler - DevOps commands whitelist (60+) with PATH existence verification
  4. CommandSyntaxHandler - Detects command syntax (flags, pipes, redirects, env vars, subshells)
  5. TypoDetectionHandler - Levenshtein distance ≤2 for typo detection (prevents LLM false positives)
  6. NaturalLanguageHandler - English patterns with precompiled regex (multilingual delegated to LLM)
  7. DefaultHandler - Fallback to natural language (guarantees a result)
- `patterns.rs`: **Precompiled RegexSet patterns** using `once_cell::Lazy` (10-100x faster)
- `discovery.rs`: **PATH-aware command discovery** with thread-safe `RwLock<CommandCache>`
- `typo_detection.rs`: **Levenshtein distance** typo detection with `strsim` crate
- `parser.rs`: Shell command parsing with `shell-words` crate (handles quotes, escapes)

**`executor/`** - Command execution (uses Facade and Strategy patterns)
- `command.rs`: Async command execution with stdout/stderr capture
- `install.rs`: Auto-install workflow
- `package_manager.rs`: **Strategy pattern** for package managers (apt, yum, dnf, pacman, brew, choco, winget)
- `facade.rs`: **Facade pattern** - simplified interface for command execution with auto-install
- `completion.rs`: Tab completion for commands and file paths

**`orchestrators/`** - Workflow coordination (uses Single Responsibility Principle)
- `command.rs`: CommandOrchestrator handles command execution workflow
- `natural_language.rs`: NaturalLanguageOrchestrator handles LLM query workflow
- `tab_completion.rs`: TabCompletionHandler handles tab completion workflow

**`llm/`** - LLM integration
- `client.rs`: LLM API client (MockLLMClient for testing, HttpLLMClient for production)
- `renderer.rs`: Markdown response formatting with syntax highlighting

**`utils/`** - Shared utilities
- `ansi.rs`: ANSI color utilities
- `errors.rs`: Error types
- `message.rs`: Message formatting helpers

### Key Design Decisions

1. **Design Patterns Used**:
   - **Chain of Responsibility**: Input classification (`input/handler.rs`)
   - **Strategy Pattern**: Package managers (`executor/package_manager.rs`)
   - **Facade Pattern**: Command execution interface (`executor/facade.rs`)
   - **Builder Pattern**: Terminal construction (`main.rs` InfrawareTerminalBuilder)
   - **Single Responsibility Principle**: Orchestrators, buffer components

2. **SCAN Algorithm** (Shell-Command And Natural-language): Production-ready Chain of Responsibility with 7 optimized handlers executing in strict order (<100μs average):
   1. **EmptyInputHandler**: Fast path for empty/whitespace input (<1μs)
   2. **PathCommandHandler**: Executable paths with platform-specific checks - Unix: executable bit check, Windows: .exe/.bat/.cmd extensions (~10μs)
   3. **KnownCommandHandler**: Whitelist of 60+ DevOps commands + cached PATH verification (<1μs cache hit, 1-5ms cache miss)
   4. **CommandSyntaxHandler**: Shell syntax detection - flags (--/-), pipes (|), redirects (>/</>>), logical operators (&&/||), env vars ($VAR), subshells ($()/ backticks) (~10μs)
   5. **TypoDetectionHandler**: Levenshtein distance ≤2 typo detection with `strsim` crate - prevents expensive LLM calls for "dokcer" → "docker" (~100μs)
   6. **NaturalLanguageHandler**: English-only patterns (question words, articles, polite phrases) using precompiled regex - delegates multilingual to LLM (~5μs)
   7. **DefaultHandler**: Fallback to natural language - guarantees result, never panics (<1μs)

   **Performance Optimizations** (see `benches/scan_benchmark.rs`):
   - **Precompiled RegexSet**: `once_cell::Lazy<CompiledPatterns>` compiles patterns once at startup (10-100x speedup)
   - **Thread-safe cache**: `RwLock<CommandCache>` for PATH lookups (99% read-heavy workload, <1μs cache hit)
   - **Handler ordering**: Fast paths first (70% of inputs hit KnownCommandHandler cache)
   - **Zero-cost abstractions**: Static dispatch for patterns, minimal allocations

   **Design Rationale**: English-first fast path (70-80% of queries) with LLM fallback for universal language support (100+ languages). Non-English queries pass through to DefaultHandler and reach LLM with negligible overhead (~1μs vs 100-500ms LLM latency).

3. **Async Execution**: Uses tokio for non-blocking command execution to keep TUI responsive

4. **Cross-Platform Package Management**: Strategy pattern supports 7 package managers:
   - Linux: apt-get, yum, dnf, pacman
   - macOS: brew (highest priority)
   - Windows: choco, winget (winget preferred over choco)

5. **M1 Rendering Limits**: Basic markdown only - code blocks with syntax highlighting (rust, python, bash, json), simple inline formatting. Tables, images, and complex markdown deferred to M2/M3.

## Important Constraints

### CI/CD
- GitHub Actions workflow runs on all PRs and pushes to main
- **Format check**: `cargo fmt --all --check` must pass
- **Clippy**: `cargo clippy --all-targets --all-features -- -D warnings` must pass (warnings treated as errors)
- **Test coverage**: Minimum 75% coverage threshold enforced
- **Multi-platform builds**: Tests run on Ubuntu, Windows, and macOS

### Git Commits
- **NEVER include Co-Authored-By in commit messages** (user preference)
- **ALWAYS run `cargo fmt` before committing** (user preference)
- Keep commit descriptions brief and concise
- Follow repository's existing commit message style (check git log)

### Scope Limitations (M1 Only)
DO NOT implement these yet (deferred to M2/M3):
- Advanced markdown rendering (tables, images)
- Full bash/zsh completion integration
- Multi-shell support (Zsh, Fish)
- Telemetry and analytics
- Performance optimization
- Complex credential management

### Testing Requirements
- All new utilities must have unit tests
- Input classifier changes require comprehensive test coverage
- Integration tests for command execution flow
- Use `tokio-test` for async test utilities

## Development Guidelines

### Working with SCAN Algorithm

The **SCAN Algorithm** (Shell-Command And Natural-language) is the core input classification system. When modifying:

**Adding Commands**:
1. Add to `KnownCommandHandler::default_known_commands()` in `input/handler.rs`
2. Commands are automatically verified against PATH (cached for performance)
3. Add test cases to verify classification behavior
4. Consider auto-install support via package managers

**Adding Handlers**:
1. Implement the `InputHandler` trait in `input/handler.rs`
2. Add to the chain in `InputClassifier::new()` in the correct order
3. Order matters: fast paths first, expensive operations later
4. Add comprehensive test coverage

**Typo Detection**:
- Levenshtein distance threshold: max_distance = 2
- Only checks first word of input against known commands
- Filters out natural language via `looks_like_command()` heuristic
- Returns `InputType::CommandTypo` with suggestion and distance

**Performance Considerations**:
- **Always use precompiled patterns** in `input/patterns.rs` - NEVER compile regex in handlers
- **Leverage CommandCache** via `discovery.rs` for PATH lookups (thread-safe RwLock, <1μs reads)
- **Handler chain order is critical** - fast paths first, expensive operations last
- **Profile changes** with `cargo bench` - SCAN benchmarks in `benches/scan_benchmark.rs`
- **Target**: Average classification <100μs, known commands <1μs (cache hit)

### Working with LLM Integration
- Two client implementations: `MockLLMClient` (testing) and `HttpLLMClient` (production)
- LLM client is injected via Builder pattern for testability
- Real LLM backend integration pending (endpoint/auth TBD)
- When implementing real client, ensure proper error handling for network timeouts
- LLM workflow handled by `NaturalLanguageOrchestrator` in `orchestrators/natural_language.rs`

### TUI State Management
- Terminal state lives in `TerminalState` struct (in `terminal/state.rs`)
- State is composed of three SRP-compliant buffer components (`terminal/buffers.rs`):
  - `OutputBuffer`: scrollable output with auto-trim (max 10,000 lines)
  - `InputBuffer`: text input with cursor positioning (handles Unicode correctly)
  - `CommandHistory`: history navigation
- Use `TerminalMode` enum to track current state (Normal, ExecutingCommand, WaitingLLM, PromptingInstall)
- Always render after state changes
- Handle terminal resize events properly

### Working with Orchestrators
- Orchestrators separate workflow logic from the main event loop
- `CommandOrchestrator`: handles command execution + auto-install prompts
- `NaturalLanguageOrchestrator`: handles LLM queries + response rendering
- `TabCompletionHandler`: handles tab completion
- When adding new workflows, create a new orchestrator instead of adding to main loop

### Error Handling
- Use `anyhow::Result` for application errors
- Use `thiserror` for custom error types
- Provide user-friendly error messages in TUI output
- Don't crash on command failures - display error and continue

## Common Patterns

### Adding a New TerminalEvent
1. Add variant to `TerminalEvent` enum in `terminal/events.rs`
2. Handle event in `EventHandler::poll_event()`
3. Implement handler in `InfrawareTerminal::handle_event()` in `main.rs`
4. Update TUI rendering if needed

### Modifying Input Classification
1. **Add/modify handlers** in `input/handler.rs` - implement `InputHandler` trait
2. **Update chain order** in `InputClassifier::new()` - ORDER MATTERS! Fast paths first
3. **Use precompiled patterns** from `patterns.rs` - NEVER compile regex in handlers
4. **Add comprehensive test cases** in `tests/classifier_tests.rs` and handler tests
5. **Test edge cases**: typos, multilingual input, command-like natural language ("run the tests")
6. **Run benchmarks** with `cargo bench` to verify performance hasn't regressed
7. **Run integration tests** to ensure no classification regression

**Critical Design Constraint**: The classifier uses **English-only patterns** for fast path optimization (70-80% of queries). Multilingual queries (Italian, Spanish, French, German, etc.) are handled by the LLM backend via DefaultHandler fallback. This is by design - LLM provides better accuracy and flexibility than hardcoded regex for 100+ languages.

**InputType Enum** (`input/classifier.rs`):
- `Command { command, args, original_input }` - Shell operators preserved in `original_input`
- `NaturalLanguage(String)` - Sent to LLM (handles all languages)
- `Empty` - Ignored
- `CommandTypo { input, suggestion, distance }` - Shows suggestion to user

### Adding a New Package Manager
1. Create a new struct implementing the `PackageManager` trait in `executor/package_manager.rs`
2. Implement required methods: `name()`, `is_available()`, `install()`, `priority()`
3. Add the manager to `PackageInstaller::detect_package_manager()` in `executor/install.rs`
4. Add test cases for availability check and priority
5. Consider platform-specific behavior (Windows vs Linux vs macOS)

### Adding Syntax Highlighting
1. Update `ResponseRenderer::highlight_code()` in `llm/renderer.rs`
2. Use `syntect` crate with appropriate syntax set
3. Test with code samples in different languages
4. Ensure ANSI escape codes render correctly in TUI

## Implementation Status & Known Limitations

### ✅ Completed (Production-Ready)
- **SCAN Algorithm**: All 7 handlers implemented with performance optimizations
- **Typo Detection**: Levenshtein distance-based suggestion system
- **Shell Operator Support**: Pipes, redirects, logical operators, subshells
- **Command Caching**: Thread-safe PATH verification with RwLock
- **Precompiled Patterns**: Zero runtime regex compilation overhead
- **Cross-Platform**: Windows/macOS/Linux support with platform-specific handlers
- **Benchmarking**: Performance benchmarks in `benches/scan_benchmark.rs`
- **Test Coverage**: 157 tests passing, 0 clippy warnings

### ⚠️ Known Limitations (Deferred to M2/M3)
- **Auto-install**: Framework exists, prompts user but doesn't execute installation
- **LLM Backend**: `HttpLLMClient` exists but needs real endpoint/auth integration
- **Tab Completion**: Basic file/command completion only - no bash/zsh integration
- **Configuration**: No config file support - uses hardcoded defaults
- **Command History**: Session-only persistence - not saved to disk
- **Advanced Markdown**: Basic rendering only - tables/images deferred to M2/M3

## Windows-Specific Considerations

**Fixed: Double Input Issue** - On Windows, `crossterm` generates multiple events per keystroke (Press, Repeat, Release). This was causing duplicate character input. **Solution implemented**: Filter events to only process `KeyEventKind::Press` in `terminal/events.rs:41`. This ensures each keystroke is processed exactly once.

## Performance Benchmarking

Run benchmarks to verify performance targets:

```bash
# Run all benchmarks
cargo bench

# Run specific SCAN benchmarks
cargo bench scan_

# View benchmark results
open target/criterion/report/index.html  # macOS
xdg-open target/criterion/report/index.html  # Linux
```

**Performance Targets**:
- Average classification: <100μs
- Known command (cache hit): <1μs
- Typo detection: <100μs
- Natural language: <5μs
- PATH lookup (cache miss): 1-5ms (cached for subsequent calls)

## Documentation & References

### Internal Documentation
- **Project Brief**: `infraware_terminal_project_brief.md`
- **SCAN Architecture**: `docs/SCAN_ARCHITECTURE.md` (comprehensive SCAN algorithm reference)
- **Implementation Plan**: `docs/SCAN_IMPLEMENTATION_PLAN.md` (SCAN implementation phases)
- **README**: `README.md` (user-facing documentation)

### External References
- **ratatui**: https://ratatui.rs/ (TUI framework)
- **crossterm**: https://docs.rs/crossterm/latest/crossterm/ (terminal control)
- **tokio**: https://docs.rs/tokio/latest/tokio/ (async runtime)
- **regex**: https://docs.rs/regex/latest/regex/ (pattern matching)
- **which**: https://docs.rs/which/latest/which/ (command discovery)
- **strsim**: https://docs.rs/strsim/latest/strsim/ (Levenshtein distance)