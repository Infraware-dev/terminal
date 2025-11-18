# Infraware Terminal - UML Architecture Diagrams

This directory contains comprehensive UML class diagrams documenting the architecture of the Infraware Terminal application. All diagrams are in PlantUML format (.puml files) and can be viewed using PlantUML rendering tools.

## Diagram Overview

### 1. **01-architecture-overview.puml** - High-Level System Architecture
**Purpose**: Provides a bird's-eye view of the entire system and how major components interact.

**Key Components**:
- **Terminal**: State management and TUI rendering
- **Input Classification (SCAN Algorithm)**: InputClassifier with 7-handler chain
- **Command Execution**: CommandExecutor with Facade pattern
- **Natural Language**: LLM integration with response rendering
- **Package Management**: Strategy pattern for 7 package managers

**Key Relationships**:
- User input flows through InputClassifier
- Commands route to CommandOrchestrator
- Natural language queries route to NaturalLanguageOrchestrator
- Both update TerminalState for display

**Patterns Highlighted**:
- Chain of Responsibility (SCAN)
- Facade Pattern (CommandExecutionFacade)
- Strategy Pattern (PackageManager)

---

### 2. **02-scan-algorithm.puml** - SCAN Algorithm Deep Dive
**Purpose**: Details the SCAN (Shell-Command And Natural-language) algorithm and its 7 handlers.

**Handler Chain** (in order, optimized for performance):
1. **EmptyInputHandler** - Fast path for empty/whitespace input
2. **PathCommandHandler** - Detects executable paths (./script.sh, /usr/bin/cmd)
3. **KnownCommandHandler** - 60+ DevOps commands whitelist + PATH verification
4. **CommandSyntaxHandler** - Detects command syntax (flags, pipes, redirects)
5. **TypoDetectionHandler** - Levenshtein distance typo detection (max_distance=2)
6. **NaturalLanguageHandler** - English/multilingual natural language patterns
7. **DefaultHandler** - Fallback to natural language

**Key Features**:
- Chain of Responsibility design pattern
- Each handler returns `Some(InputType)` or `None` to pass to next
- Order optimized for performance and accuracy
- Prevents false LLM calls via typo detection

**Performance Optimizations**:
- Precompiled RegexSet patterns (once_cell::Lazy)
- Thread-safe command cache with RwLock (99% read-heavy)
- Fast paths first (empty, paths)
- Short-circuit evaluation

---

### 3. **03-executor-module.puml** - Command Execution Architecture
**Purpose**: Shows the executor module with Facade and Strategy patterns.

**Facade Pattern** (CommandExecutionFacade):
- Simplifies command execution workflow
- Combines CommandExecutor + PackageInstaller
- Handles installation fallback for missing commands

**Strategy Pattern** (PackageManager):
Supports 7 package managers with priority-based selection:
- **Linux**: apt-get, yum, dnf, pacman
- **macOS**: brew (highest priority)
- **Windows**: winget (preferred), choco (fallback)

**Key Classes**:
- `CommandExecutor`: Async command execution with timeout (5 min)
- `CommandOutput`: stdout, stderr, exit_code
- `ExecutionResult`: Success, CommandNotFound, ExecutionError
- `PackageInstaller`: Detects and uses best package manager
- `TabCompletion`: Command and file completion

**Error Handling**:
- Command not found → suggest install
- Execution error → display error message
- Timeout → notify user

---

### 4. **04-input-module-detailed.puml** - Input Module Architecture
**Purpose**: Detailed view of the input classification system and support components.

**Core Classification**:
- `InputClassifier`: Main entry point
- `InputType`: Enum for classification results
- `ClassifierChain`: Manages handler chain
- `InputHandler`: Trait for all handlers

**Support Systems**:
- **CompiledPatterns**: Precompiled regex patterns for multilingual NL detection
  - Question words, articles, shell operators
  - 10-100x faster than repeated compilation
  - Lazy singleton pattern

- **CommandCache**: Thread-safe PATH lookup cache
  - RwLock for concurrent reads
  - O(1) hit, O(PATH_length) miss
  - Caches both available and unavailable

- **CommandParser**: Shell argument parsing (shell_words crate)

**Typo Detection Detail**:
- Levenshtein distance algorithm
- Max distance = 2 (default)
- Examples: "dokcer" → "docker", "kubeclt" → "kubectl"
- Filters long phrases (> 5 words) to avoid FP

**Input Flow Diagram**:
Shows how input flows through the chain:
1. Check if empty → return Empty
2. Check if path → return Command
3. Check if known command → return Command
4. Check if command syntax → return Command
5. Check if typo → return CommandTypo
6. Check if NL pattern → return NaturalLanguage
7. Default → return NaturalLanguage

---

### 5. **05-orchestrators.puml** - Workflow Coordination
**Purpose**: Shows how orchestrators coordinate workflows and manage state.

**Main Components**:
- **TerminalState**: Composed of buffers (not inheritance)
  - OutputBuffer: scrollable output (max 10,000 lines)
  - InputBuffer: text editing with cursor
  - CommandHistory: navigation
  - TerminalMode: current state

- **CommandOrchestrator**: Executes commands
  1. Check existence
  2. Execute
  3. Handle installation prompt
  4. Return result

- **NaturalLanguageOrchestrator**: Queries LLM
  1. Classify as NL
  2. Query LLM backend
  3. Format markdown
  4. Apply syntax highlighting
  5. Display result

- **TabCompletionHandler**: Provides completions
  - Command completion
  - File completion
  - Per-command flags

**Single Responsibility Principle**:
Each orchestrator has one clear purpose. Each buffer component is focused.

**Event Loop**:
Poll Event → Classify Input → Route to Handler → Update State → Render

---

### 6. **06-llm-integration.puml** - LLM Client Abstraction
**Purpose**: Shows LLM integration with multiple implementations and rendering.

**LLM Client Abstraction** (LLMClientTrait):
- `query()`: Basic query
- `query_with_context()`: With optional context
- `query_with_history()`: With command history

**Implementations**:
- **HttpLLMClient**: Production REST API client
  - 30-second timeout
  - Supports custom timeouts
  - Backend TBD

- **MockLLMClient**: Testing implementation
  - Predictable responses
  - No network calls
  - Fast test execution

**Response Rendering**:
- **ResponseRenderer**: Parses and formats markdown
- **SyntaxHighlighter**: Highlights code blocks

**M1 Scope** (Basic Markdown):
- Code blocks with syntax highlighting
- Inline code formatting
- Bold, italic text
- Lists

**Not Yet** (M2/M3):
- Tables, images
- Complex layouts
- LaTeX math

**Supported Languages**:
- rust, python, bash, json, yaml
- javascript/typescript, html/xml

**Workflow**:
1. Receive NL query
2. Prepare context
3. Query LLM client
4. Parse markdown response
5. Apply syntax highlighting
6. Format for terminal
7. Display to user

---

### 7. **07-complete-system-class-diagram.puml** - Integrated Class Diagram
**Purpose**: Complete system class diagram showing all classes and relationships.

**Package Organization**:
- Input Classification
- Command Execution
- Package Management
- Orchestrators
- LLM Integration
- Terminal State
- TUI Rendering
- Main Application

**Key Relationships**:
- InputClassifier → InputType
- CommandOrchestrator → CommandExecutor
- NaturalLanguageOrchestrator → ResponseRenderer
- CommandExecutionFacade → PackageInstaller
- PackageInstaller → PackageManager (strategy)

**Design Patterns Used**:
1. **Chain of Responsibility**: Handler chain in InputClassifier
2. **Facade Pattern**: CommandExecutionFacade
3. **Strategy Pattern**: PackageManager trait + 7 implementations
4. **Trait Abstraction**: LLMClientTrait for multiple clients
5. **Builder Pattern**: Terminal construction in main.rs
6. **Lazy Singleton**: CompiledPatterns, CommandCache
7. **Async/Await**: Tokio-based execution

---

## Reading the Diagrams

### Notation Legend
- **Classes**: `ClassName`
- **Traits/Interfaces**: `<<interface>>` with dashed lines
- **Enums**: `<<enum>>`
- **Singletons**: `<<(S,#FF7700)>>`
- **Inheritance**: `--|>`
- **Implementation**: `..|>`
- **Composition**: `*--` (strong ownership)
- **Aggregation**: `o--` (weak relationship)
- **Association**: `--` (uses/depends on)

### Rendering

**Option 1: Online PlantUML Editor**
Visit https://www.plantuml.com/plantuml/uml/ and paste the .puml file contents

**Option 2: Local PlantUML**
```bash
# Install PlantUML (requires Java)
# Then render to PNG/SVG:
plantuml 01-architecture-overview.puml -o ../diagrams/
```

**Option 3: VS Code Extension**
Install "PlantUML" extension for preview and export

**Option 4: IDE Integration**
- IntelliJ IDEA: Built-in PlantUML support
- VS Code: PlantUML extension

---

## Architecture Principles

### 1. Single Responsibility Principle
- Each orchestrator handles one workflow
- Each buffer component is focused
- CommandExecutor only executes
- InputClassifier only classifies

### 2. Separation of Concerns
- Classification logic isolated from execution
- State management separate from rendering
- LLM abstraction from implementation

### 3. Composition over Inheritance
- TerminalState composed of buffers
- Traits for abstraction (InputHandler, PackageManager, LLMClientTrait)
- No deep inheritance hierarchies

### 4. Dependency Injection
- Orchestrators receive dependencies
- No hard-coded globals (except cache)
- Testable and mockable

### 5. Event-Driven Architecture
- Main loop: poll → process → render
- Non-blocking operations
- Async execution with tokio
- Responsive UI

---

## SCAN Algorithm Highlights

### Performance Optimizations
- **Precompiled Patterns**: RegexSet compiled once (once_cell::Lazy)
- **Command Cache**: RwLock-protected HashSet for PATH lookups
- **Handler Order**: Fast paths first, expensive operations last
- **Short-Circuit**: Each handler can terminate chain

### 7-Handler Chain
| Handler | Input Type | Cost | Purpose |
|---------|-----------|------|---------|
| Empty | Empty/whitespace | O(1) | Fast path |
| Path | /path, ./script | O(1) | Unambiguous |
| Known | Known commands | O(1) cache | Whitelist + cache |
| Syntax | Flags, pipes | O(1) | Pattern match |
| Typo | Misspelled | O(n) | Levenshtein |
| NL | Natural language | O(1) regex | Precompiled |
| Default | Anything else | O(1) | Fallback |

### Command Whitelist (60+ commands)
Basic shell, text processing, process management, network, system info, Docker, Kubernetes, cloud providers, VCS, build tools, monitoring, DevOps tools.

### Multilingual Support
English, Italian, Spanish, French, German patterns for:
- Question words
- Articles
- Request verbs
- Polite expressions

---

## Future Enhancements (M2/M3)

### Input Module
- Additional language support
- Machine learning-based classification
- User-trained custom handlers

### Execution
- Advanced auto-install with user confirmation
- Command history analysis
- Performance profiling

### LLM Integration
- Streaming responses
- Context-aware queries
- Custom system prompts
- Multiple LLM backends

### Terminal
- Configuration file support
- Theme customization
- Plugin system

---

## Related Documentation

- **SCAN_ARCHITECTURE.md**: Detailed SCAN algorithm design
- **SCAN_IMPLEMENTATION_PLAN.md**: Implementation roadmap
- **README.md**: Project overview
- **CLAUDE.md**: Development guidelines

---

## File Locations

All UML diagrams are located in:
```
/home/crist/infraware-terminal/terminal-app/docs/uml/
```

Source code reference:
```
/home/crist/infraware-terminal/terminal-app/src/
├── input/          # SCAN algorithm
├── executor/       # Command execution
├── orchestrators/  # Workflow coordination
├── llm/           # LLM integration
├── terminal/      # TUI and state
└── main.rs        # Main application
```

---

## Contributing

When modifying the architecture:
1. Update relevant .puml files
2. Keep diagrams synchronized with code
3. Update this README with changes
4. Document design decisions in code comments
5. Add notes to diagrams for complex patterns

---

**Last Updated**: 2025-11-18
**Project Status**: M1 (Terminal Core MVP)
**Rust Version**: 1.70+
