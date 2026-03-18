# Contributing to Infraware Terminal

Thank you for your interest in contributing to Infraware Terminal! This document provides guidelines
for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/<your-username>/infraware-terminal.git`
3. Create a feature branch: `git checkout -b feat/my-feature`
4. Make your changes
5. Submit a pull request

## Prerequisites

- **Rust** 1.88+ (edition 2024)
- **Nightly toolchain** for formatting: `rustup toolchain install nightly`
- **Linux**: `sudo apt install -y pkg-config libssl-dev libxcb-shape0-dev libxcb-xfixes0-dev`
- **Docker** (optional, for test container and arena features)

## Development Workflow

### Build and Test

```bash
cargo build                          # Build
cargo test                           # Run all tests
cargo test -- test_name              # Run a specific test
cargo test -- --nocapture            # With stdout output
```

### Code Quality

CI enforces both formatting and linting. Run these before submitting a PR:

```bash
cargo +nightly fmt --all             # Format (nightly required for rustfmt.toml rules)
cargo clippy -- -D warnings          # Lint (warnings treated as errors)
```

### Test Coverage

CI enforces a 50% minimum coverage threshold (excluding UI/PTY/VTE modules):

```bash
cargo llvm-cov --all-features --summary-only   # Quick summary
cargo llvm-cov --all-features --lcov --output-path lcov.info  # Full LCOV report
```

## Code Style

### Rust Guidelines

- All public types must implement `Debug` (custom impl for sensitive data)
- Use `#[expect]` instead of `#[allow]` when lint suppression should be revisited
- Panic for programming errors, `Result` for expected failures
- Use `anyhow::Result` for application code, `thiserror` for library error types
- Safe indexing: `.first()`, `.get()` instead of `[0]`

### Commit Messages

- Format: `<type>: <description>` (max 50 chars, imperative mood)
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `style`
- No emojis or AI attribution

### Pull Requests

- Include how to test (commands and expected outcome)
- Include screenshots or recordings for UI changes
- Link related issues if applicable
- Keep PRs focused — one logical change per PR

## Project Structure

See [docs/architecture.md](docs/architecture.md) for a detailed module overview.

Key extension points:

| Task | Location |
|------|----------|
| Add a PTY backend | `src/pty/adapters/` — implement the `PtySession` trait |
| Add an engine adapter | `src/engine/adapters/` — implement the `AgenticEngine` trait |
| Add a keyboard shortcut | `src/input/keyboard.rs` |
| Modify terminal rendering | `src/app/terminal_renderer.rs` |
| Change theme colors | `src/ui/theme.rs` |

## Reporting Issues

- Use [GitHub Issues](https://github.com/Infraware-dev/infraware-terminal/issues)
- Include steps to reproduce, expected vs actual behavior, and your environment (OS, Rust version)

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE).
