# Infraware Terminal UML Diagrams - Complete Index

## Navigation Guide

This document provides a complete index of all UML diagrams generated for the Infraware Terminal project.

---

## Primary Diagrams (Recommended Reading Order)

### For Quick Overview (Start Here)
1. **01-architecture-overview.puml** (198 lines)
   - High-level system architecture
   - All major components and interactions
   - Perfect entry point for understanding the system
   - Shows: Terminal, Input, Execution, NL, Package Management

### For Core Algorithm Understanding
2. **02-scan-algorithm.puml** (222 lines)
   - SCAN (Shell-Command And Natural-language) Algorithm
   - Chain of Responsibility pattern with 7 handlers
   - Handler responsibilities and order
   - Performance optimization techniques
   - Levenshtein distance typo detection

### For Command Execution
3. **03-executor-module.puml** (231 lines)
   - Command execution with Facade pattern
   - Package management with Strategy pattern
   - 7 package managers implementation
   - Cross-platform support (Linux, macOS, Windows)
   - Error handling and installation fallback

### For Input Details
4. **04-input-module-detailed.puml** (246 lines)
   - Input classification system architecture
   - CompiledPatterns (Lazy Singleton)
   - CommandCache (Thread-safe RwLock)
   - Typo detection with Levenshtein distance
   - Input flow diagram showing classification path

### For State and Orchestrators
5. **05-orchestrators.puml** (260 lines)
   - TerminalState composition pattern
   - Three orchestrators (Command, NL, Completion)
   - Buffer components (OutputBuffer, InputBuffer, CommandHistory)
   - Event loop flow and state transitions
   - Single Responsibility Principle application

### For LLM Integration
6. **06-llm-integration.puml** (255 lines)
   - LLMClientTrait abstraction
   - HttpLLMClient (production) and MockLLMClient (testing)
   - Response rendering pipeline
   - Syntax highlighting and markdown formatting (M1 scope)
   - Future extensions for M2/M3

### For Complete System View
7. **07-complete-system-class-diagram.puml** (350 lines)
   - Integrated class diagram of entire system
   - All packages and their relationships
   - Design patterns used throughout
   - Cross-module dependencies
   - Best for print/presentation

---

## Supporting Documentation

### Quick Reference
- **QUICK_REFERENCE.md** (9K)
  - Design patterns summary table
  - SCAN algorithm handler table
  - Package manager priority order
  - Handler cost comparison
  - Rendering options
  - Code-to-diagram mapping

### Comprehensive Guide
- **README_DIAGRAMS.md** (12K)
  - Detailed description of each diagram
  - Component relationships
  - Architecture principles
  - SCAN algorithm highlights
  - Future enhancements (M2/M3)
  - Contributing guidelines

### This Index
- **INDEX.md** (this file)
  - Complete file listing
  - Reading order recommendations
  - File sizes and complexity
  - Content summaries

---

## Legacy/Additional Diagrams (Pre-Generation)

The following diagrams were in the docs/uml/ directory before generation:

- **class-diagram.puml** (567 lines) - Comprehensive class diagram
- **executor.puml** (192 lines) - Executor module details
- **input.puml** (228 lines) - Input module details
- **llm.puml** (190 lines) - LLM module details
- **main-application.puml** (109 lines) - Main application structure
- **orchestrators.puml** (120 lines) - Orchestrators layout
- **terminal.puml** (228 lines) - Terminal module structure
- **utils.puml** (238 lines) - Utilities module

These provide additional perspectives and can be used for reference.

---

## File Organization

### Total Content
- **7 primary diagrams**: 1,662 lines of PlantUML
- **8 legacy diagrams**: 1,972 lines of PlantUML
- **Documentation**: 30+ KB of markdown guides
- **Total UML code**: 3,634 lines

### File Locations
All files are in: `/home/crist/infraware-terminal/terminal-app/docs/uml/`

### Directory Structure
```
docs/
├── uml/
│   ├── 01-architecture-overview.puml
│   ├── 02-scan-algorithm.puml
│   ├── 03-executor-module.puml
│   ├── 04-input-module-detailed.puml
│   ├── 05-orchestrators.puml
│   ├── 06-llm-integration.puml
│   ├── 07-complete-system-class-diagram.puml
│   ├── README_DIAGRAMS.md
│   ├── QUICK_REFERENCE.md
│   ├── INDEX.md (this file)
│   └── [legacy diagrams...]
├── SCAN_ARCHITECTURE.md
└── [other docs...]
```

---

## Complexity & Reading Guide

| Diagram | Lines | Complexity | Best For | Read Time |
|---------|-------|-----------|----------|-----------|
| 01-architecture | 198 | Medium | System overview | 5 min |
| 02-scan | 222 | High | Algorithm details | 10 min |
| 03-executor | 231 | High | Execution patterns | 10 min |
| 04-input | 246 | Very High | Input details | 15 min |
| 05-orchestrators | 260 | High | State & workflows | 10 min |
| 06-llm | 255 | Medium | LLM abstraction | 8 min |
| 07-complete | 350 | Very High | Full system | 20 min |

**Total recommended reading time**: 60-70 minutes for complete understanding.

---

## Key Architectural Components Covered

### Input Classification (SCAN Algorithm)
- **Diagram**: 02-scan-algorithm.puml
- **Code**: `/src/input/`
- **Files**:
  - handler.rs (7 handlers)
  - classifier.rs (orchestrator)
  - typo_detection.rs (Levenshtein)
  - patterns.rs (precompiled regex)
  - discovery.rs (command cache)

### Command Execution
- **Diagram**: 03-executor-module.puml
- **Code**: `/src/executor/`
- **Files**:
  - command.rs (async execution)
  - facade.rs (Facade pattern)
  - package_manager.rs (Strategy pattern)
  - install.rs (package installation)

### Orchestrators
- **Diagram**: 05-orchestrators.puml
- **Code**: `/src/orchestrators/`
- **Files**:
  - command.rs (command workflow)
  - natural_language.rs (NL workflow)
  - tab_completion.rs (completion)

### LLM Integration
- **Diagram**: 06-llm-integration.puml
- **Code**: `/src/llm/`
- **Files**:
  - client.rs (trait + implementations)
  - renderer.rs (markdown rendering)

### Terminal State
- **Diagram**: 05-orchestrators.puml
- **Code**: `/src/terminal/`
- **Files**:
  - state.rs (TerminalState)
  - buffers.rs (OutputBuffer, InputBuffer, CommandHistory)
  - events.rs (event handling)

---

## Design Patterns Documented

### 1. Chain of Responsibility
- **Diagram**: 02-scan-algorithm.puml
- **Implementation**: 7-handler chain for input classification
- **Code**: `/src/input/handler.rs`

### 2. Facade Pattern
- **Diagram**: 03-executor-module.puml
- **Implementation**: CommandExecutionFacade
- **Code**: `/src/executor/facade.rs`

### 3. Strategy Pattern
- **Diagram**: 03-executor-module.puml
- **Implementation**: 7 PackageManager implementations
- **Code**: `/src/executor/package_manager.rs`

### 4. Lazy Singleton
- **Diagram**: 04-input-module-detailed.puml
- **Implementation**: CompiledPatterns, CommandCache
- **Code**: `/src/input/patterns.rs`, `/src/input/discovery.rs`

### 5. Trait Abstraction
- **Diagram**: 06-llm-integration.puml
- **Implementation**: LLMClientTrait
- **Code**: `/src/llm/client.rs`

### 6. Composition over Inheritance
- **Diagram**: 05-orchestrators.puml
- **Implementation**: TerminalState composition
- **Code**: `/src/terminal/state.rs`, `/src/terminal/buffers.rs`

### 7. Dependency Injection
- **Diagram**: 01-architecture-overview.puml
- **Implementation**: Orchestrator dependencies
- **Code**: `/src/orchestrators/`, `/src/main.rs`

### 8. Builder Pattern
- **Diagram**: 01-architecture-overview.puml
- **Implementation**: Terminal/application construction
- **Code**: `/src/main.rs`

### 9. Event-Driven Architecture
- **Diagram**: 05-orchestrators.puml
- **Implementation**: Main event loop
- **Code**: `/src/main.rs`, `/src/terminal/events.rs`

---

## Rendering the Diagrams

### Option 1: Online PlantUML Editor (Recommended for Quick View)
1. Visit https://www.plantuml.com/plantuml/uml/
2. Copy-paste content from any .puml file
3. View rendered diagram instantly
4. Export as PNG, SVG, or PDF

### Option 2: Local PlantUML (For Batch Processing)
```bash
# Install PlantUML (macOS)
brew install plantuml

# Or download jar from https://plantuml.com/download

# Render single file
plantuml /home/crist/infraware-terminal/terminal-app/docs/uml/01-architecture-overview.puml

# Render all .puml files in directory
plantuml /home/crist/infraware-terminal/terminal-app/docs/uml/*.puml

# Render to SVG (better for web)
plantuml -tsvg /home/crist/infraware-terminal/terminal-app/docs/uml/01-architecture-overview.puml
```

### Option 3: VS Code Extension (Best for Development)
1. Install "PlantUML" extension by jebbs
2. Open any .puml file
3. Press `Alt+D` to preview
4. Right-click preview → Export PNG/SVG/PDF

### Option 4: IDE Integration (For Developers)
- **IntelliJ IDEA**: Built-in PlantUML support
- **VS Code**: PlantUML extension
- **Visual Studio**: PlantUML extension available

---

## SCAN Algorithm Summary

### 7-Handler Chain (Optimized Order)
1. **EmptyInputHandler** → Empty/whitespace check (O(1))
2. **PathCommandHandler** → /path, ./ checks (O(1))
3. **KnownCommandHandler** → 60+ command whitelist + cache (O(1))
4. **CommandSyntaxHandler** → Flags, pipes, redirects (O(1))
5. **TypoDetectionHandler** → Levenshtein distance ≤2 (O(n))
6. **NaturalLanguageHandler** → Precompiled patterns (O(1))
7. **DefaultHandler** → Fallback to NL (O(1))

### Performance Optimizations
- Precompiled RegexSet patterns (once_cell::Lazy)
- Thread-safe CommandCache (RwLock, 99% reads)
- Fast paths first, expensive operations last
- Short-circuit evaluation in chain

### 60+ Known Commands
Including: shell, text processing, system info, networking, Docker, Kubernetes, cloud tools, VCS, build tools, monitoring, DevOps tools.

### Multilingual Support
English, Italian, Spanish, French, German patterns.

---

## Package Management (Strategy Pattern)

### 7 Implementations (Priority Order)
1. **brew** - macOS (priority=90)
2. **winget** - Windows (priority=85)
3. **apt-get** - Debian/Ubuntu (priority=80)
4. **dnf** - Fedora (priority=80)
5. **yum** - RHEL/CentOS (priority=80)
6. **pacman** - Arch (priority=80)
7. **choco** - Windows fallback (priority=70)

---

## LLM Integration Features

### M1 (Current)
- Basic markdown rendering
- Code blocks with syntax highlighting
- Inline formatting (bold, italic)
- ANSI color output
- 9+ supported languages

### M2/M3 (Planned)
- Tables and images
- Advanced markdown features
- Multiple LLM backends
- Streaming responses
- Context-aware queries
- Custom system prompts

---

## Testing & Validation

### Diagram Validation
All diagrams have been validated to:
- Contain proper PlantUML syntax
- Accurately reflect source code structure
- Show correct design patterns
- Maintain consistency across diagrams

### Code Accuracy
Each diagram maps to actual source files:
- All classes match implemented code
- All relationships documented in code
- All patterns verified in implementation
- Comments added for clarification

---

## Documentation Map

### For Different Audiences

**Project Managers / Decision Makers**
- Start with: 01-architecture-overview.puml
- Read: QUICK_REFERENCE.md (patterns section)

**New Developers**
- Start with: 01-architecture-overview.puml
- Then: 02-scan-algorithm.puml, 05-orchestrators.puml
- Refer to: QUICK_REFERENCE.md for patterns

**Algorithm Specialists**
- Primary: 02-scan-algorithm.puml
- Supporting: 04-input-module-detailed.puml
- Reference: CLAUDE.md (SCAN section)

**Backend Developers**
- Start with: 03-executor-module.puml
- Then: 04-input-module-detailed.puml
- Refer to: 05-orchestrators.puml

**System Architects**
- Study: 07-complete-system-class-diagram.puml
- Review: All supporting diagrams
- Reference: SCAN_ARCHITECTURE.md

---

## Maintenance & Updates

### When Code Changes
1. Identify affected diagram(s)
2. Update .puml file(s) to match
3. Update documentation comments
4. Validate PlantUML syntax
5. Test rendering (online tool recommended)

### Keeping Diagrams Synchronized
- Review diagrams in code reviews
- Update diagrams before merging
- Use comments for design decisions
- Document design patterns used

### Version Control
- Keep diagrams in `/docs/uml/`
- Track diagram changes in git
- Include diagram updates in commits
- Document major architecture changes

---

## Related Resources

### In This Repository
- **CLAUDE.md**: Development guidelines (SCAN details)
- **SCAN_ARCHITECTURE.md**: Detailed SCAN design document
- **SCAN_IMPLEMENTATION_PLAN.md**: Implementation roadmap
- **README.md**: Project overview
- **Cargo.toml**: Dependencies and project config

### Source Code
- `/src/input/`: SCAN algorithm implementation
- `/src/executor/`: Command execution
- `/src/orchestrators/`: Workflow coordination
- `/src/llm/`: LLM integration
- `/src/terminal/`: TUI and state
- `/tests/`: Test suite

### External References
- PlantUML: https://plantuml.com/
- Ratatui (TUI): https://ratatui.rs/
- Crossterm: https://github.com/crossterm-rs/crossterm

---

## Quick Links

| Need | Resource |
|------|----------|
| System overview | 01-architecture-overview.puml |
| SCAN algorithm | 02-scan-algorithm.puml |
| Execution details | 03-executor-module.puml |
| Input details | 04-input-module-detailed.puml |
| State management | 05-orchestrators.puml |
| LLM abstraction | 06-llm-integration.puml |
| Complete view | 07-complete-system-class-diagram.puml |
| Quick lookup | QUICK_REFERENCE.md |
| Full guide | README_DIAGRAMS.md |
| Architecture | CLAUDE.md or SCAN_ARCHITECTURE.md |

---

## Summary

This UML diagram collection provides comprehensive documentation of the Infraware Terminal architecture including:

- **7 primary diagrams** (1,662 lines of PlantUML)
- **Complete pattern documentation** (9 design patterns)
- **SCAN algorithm details** (7-handler chain)
- **Package management** (7 implementations)
- **LLM integration** (abstraction + implementations)
- **State management** (composition-based)
- **Supporting documentation** (guides, references, index)

All diagrams are synchronized with the source code and validated for accuracy.

---

**Last Updated**: 2025-11-18
**Total Lines of UML**: 3,634 across 15 files
**Primary Diagrams**: 7 (recommended reading order)
**Documentation Pages**: 3
**Design Patterns**: 9
**Status**: Complete and documented
