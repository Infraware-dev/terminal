# Infraware Terminal Documentation Index

## Documentation Structure

```
docs/
├── INDEX.md                              # This file - navigation guide
├── SUPPORTED_COMMANDS.md                 # All commands with test references
├── SCAN_ARCHITECTURE.md                  # SCAN algorithm deep dive
├── SCAN_IMPLEMENTATION_PLAN.md           # Implementation phases
├── INTERACTIVE_COMMANDS_ARCHITECTURE.md  # Interactive command handling
├── INTERACTIVE_COMMANDS_PLAN.md          # Interactive commands planning
├── SCROLLING_ARCHITECTURE.md             # Output scrolling implementation
├── QUICK_REFERENCE_SCROLLING.md          # Scrolling quick reference
├── design-patterns.md                    # Design patterns deep dive
├── design-patterns/                      # Design pattern examples
│   └── chain-of-responsibility.md
└── uml/                                  # All UML diagrams
    ├── README.md                         # UML documentation index
    └── *.puml                            # PlantUML diagram files
```

## Quick Navigation

### Understanding the System
1. Start with `uml/DIAGRAM_QUICK_REFERENCE.md`
2. View `uml/00-main-application-architecture.puml`
3. View `uml/07-data-flow-pipeline.puml`
4. Choose a module diagram

### Core Documentation

| Document | Description |
|----------|-------------|
| [SUPPORTED_COMMANDS.md](SUPPORTED_COMMANDS.md) | All supported commands with test references |
| [SCAN_ARCHITECTURE.md](SCAN_ARCHITECTURE.md) | Complete SCAN algorithm explanation |
| [INTERACTIVE_COMMANDS_ARCHITECTURE.md](INTERACTIVE_COMMANDS_ARCHITECTURE.md) | TUI suspend/resume for interactive commands |
| [SCROLLING_ARCHITECTURE.md](SCROLLING_ARCHITECTURE.md) | Output buffer scrolling implementation |
| [design-patterns.md](design-patterns.md) | Design patterns used in the codebase |

### UML Diagrams

All PlantUML diagrams are in the `uml/` subdirectory. See [uml/README.md](uml/README.md) for:
- Complete diagram index
- How to view diagrams
- Task-based diagram selection

### Key Diagrams

| Diagram | Purpose |
|---------|---------|
| `uml/00-main-application-architecture.puml` | System overview |
| `uml/01-scan-algorithm-10-handlers.puml` | SCAN classification chain |
| `uml/03-executor-module.puml` | Command execution |
| `uml/04-terminal-state-and-buffers.puml` | TUI state management |
| `uml/05-orchestrators.puml` | Workflow coordination |
| `uml/06-complete-class-diagram.puml` | Full class diagram |

## How to View Diagrams

### Option 1: Online Editor (Easiest)
1. Visit https://www.plantuml.com/plantuml/uml/
2. Copy contents of any `.puml` file
3. Paste into editor and view

### Option 2: VS Code Extension
```bash
code --install-extension jebbs.plantuml
# Open any .puml file, press Alt+D to preview
```

### Option 3: Local Installation
```bash
# Linux
sudo apt install plantuml

# Generate SVG
plantuml -tsvg docs/uml/00-main-application-architecture.puml
```

## By Topic

### SCAN Algorithm
1. Read `SCAN_ARCHITECTURE.md`
2. View `uml/01-scan-algorithm-10-handlers.puml`
3. Study `src/input/handler.rs`

### Command Execution
1. View `uml/03-executor-module.puml`
2. View `uml/10-executor-module-with-background-support.puml`
3. Study `src/executor/command.rs`

### Interactive Commands
1. Read `INTERACTIVE_COMMANDS_ARCHITECTURE.md`
2. View `uml/interactive_command_flow.puml`
3. Study `src/terminal/tui.rs` (suspend/resume)

### Background Processes
1. View `uml/08-job-manager-class-diagram.puml`
2. View `uml/09-background-command-execution-sequence.puml`
3. Study `src/executor/job_manager.rs`

### UI State Management
1. View `uml/04-terminal-state-and-buffers.puml`
2. Read `SCROLLING_ARCHITECTURE.md`
3. Study `src/terminal/buffers.rs`

### Design Patterns
1. Read `design-patterns.md`
2. View `uml/design_patterns.puml`
3. See `design-patterns/chain-of-responsibility.md`
