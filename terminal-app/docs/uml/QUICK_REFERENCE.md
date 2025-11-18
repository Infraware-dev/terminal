# Infraware Terminal UML Diagrams - Quick Reference

## Quick Navigation

### For System Overview
Start with: **01-architecture-overview.puml**
- Shows all major components
- Shows how components interact
- Good for onboarding

### For Understanding SCAN Algorithm
Read: **02-scan-algorithm.puml**
- 7 handlers in chain order
- Handler responsibilities
- Performance optimizations
- Levenshtein distance details

### For Understanding Command Execution
Read: **03-executor-module.puml**
- Facade pattern (simplified interface)
- Strategy pattern (7 package managers)
- Error handling paths
- Cross-platform support

### For Input Details
Read: **04-input-module-detailed.puml**
- Input classification flow
- CompiledPatterns (lazy singleton)
- CommandCache (thread-safe)
- Typo detection algorithm

### For Orchestrators & State
Read: **05-orchestrators.puml**
- Terminal state composition
- Three orchestrators (Command, NL, Completion)
- Event loop flow
- Buffer components (OutputBuffer, InputBuffer, CommandHistory)

### For LLM Integration
Read: **06-llm-integration.puml**
- LLMClientTrait abstraction
- HttpLLMClient vs MockLLMClient
- Response rendering pipeline
- Markdown formatting (M1 scope)

### For Complete Picture
Read: **07-complete-system-class-diagram.puml**
- All classes and relationships
- Full integration view
- Design patterns used
- Package organization

---

## Key Design Patterns

### 1. Chain of Responsibility (SCAN Algorithm)
**File**: 02-scan-algorithm.puml

7 handlers in sequence:
```
Empty? → Path? → Known? → Syntax? → Typo? → NL? → Default
```

Each returns `Some(InputType)` or `None` to pass to next.

### 2. Facade Pattern (Command Execution)
**File**: 03-executor-module.puml

```
CommandExecutionFacade
├── Hides: CommandExecutor + PackageInstaller complexity
└── Provides: execute_with_fallback(), execute_or_install()
```

### 3. Strategy Pattern (Package Managers)
**File**: 03-executor-module.puml

```
PackageManager trait
├── AptPackageManager (priority=80)
├── YumPackageManager (priority=80)
├── DnfPackageManager (priority=80)
├── PacmanPackageManager (priority=80)
├── BrewPackageManager (priority=90) ← Highest on macOS
├── ChocoPackageManager (priority=70)
└── WingetPackageManager (priority=85)
```

### 4. Lazy Singleton (Performance)
**File**: 04-input-module-detailed.puml

```
CompiledPatterns (once_cell::Lazy)
├── Compiled once at startup
├── 10-100x faster than repeated compilation
└── Thread-safe for concurrent access

CommandCache (once_cell::Lazy + RwLock)
├── Global static COMMAND_CACHE
├── Read lock for hits (fast path)
├── Write lock for misses (slow path)
└── 99% read-heavy workload
```

### 5. Trait Abstraction (Testability)
**File**: 06-llm-integration.puml

```
LLMClientTrait
├── HttpLLMClient (production)
└── MockLLMClient (testing)
```

Allows swapping implementations without changing code.

### 6. Composition over Inheritance
**File**: 05-orchestrators.puml

```
TerminalState (composition)
├── OutputBuffer (not inherited, composed)
├── InputBuffer
├── CommandHistory
└── TerminalMode
```

---

## SCAN Algorithm Summary

### Handler Order (Optimized for Performance)

| # | Handler | Pattern | Cost | When to Use |
|---|---------|---------|------|------------|
| 1 | EmptyInputHandler | Fast check | O(1) | Empty/whitespace input |
| 2 | PathCommandHandler | / ./ ../ | O(1) | Executable path detected |
| 3 | KnownCommandHandler | Whitelist | O(1) cached | Known DevOps command |
| 4 | CommandSyntaxHandler | Flags, pipes | O(1) | Command-like syntax |
| 5 | TypoDetectionHandler | Levenshtein | O(n) | Likely typo (dist≤2) |
| 6 | NaturalLanguageHandler | Regex | O(1) | English/multilingual |
| 7 | DefaultHandler | Fallback | O(1) | Anything else |

### Known Commands (60+ DevOps)
- **Shell**: ls, cd, pwd, cat, echo, grep, find, mkdir, rm, cp, mv, touch, chmod, chown
- **Text**: sed, awk, sort, uniq, wc, head, tail, cut, paste, tr
- **Process**: ps, top, htop, kill, killall, pkill, jobs, bg, fg
- **Network**: curl, wget, ping, netstat, ss, ip, ifconfig, dig, nslookup, ssh, scp, rsync
- **System**: uname, hostname, whoami, uptime, free, df, du
- **Docker**: docker, docker-compose, docker-machine
- **K8s**: kubectl, helm, minikube, k9s
- **Cloud**: aws, az, gcloud, terraform, terragrunt, pulumi
- **VCS**: git, svn, hg
- **Build**: make, cmake, cargo, npm, yarn, pip, maven, gradle, ant
- **Monitoring**: prometheus, grafana, datadog
- **DevOps**: ansible, vagrant, packer, consul, vault

### Multilingual Support
- **English**: how, what, why, when, where, who, which
- **Italian**: come, cosa, perché, quando, dove, chi, quale
- **Spanish**: cómo, qué, cuándo, dónde, quién, cuál
- **French**: comment, quoi, pourquoi, quand, où, qui, quel
- **German**: wie, was, warum, wann, wo, wer, welche

---

## Package Management (Strategy Pattern)

### Priority Order
1. **brew** (macOS, priority=90)
2. **winget** (Windows, priority=85)
3. **apt-get** (Debian/Ubuntu, priority=80)
4. **dnf** (Fedora, priority=80)
5. **yum** (RHEL/CentOS, priority=80)
6. **pacman** (Arch, priority=80)
7. **choco** (Windows fallback, priority=70)

### Detection Logic
```
PackageInstaller.detect_package_manager()
├── Platform detection (Linux, macOS, Windows)
├── Check each in priority order
├── Use is_available() check
└── Select highest available
```

---

## LLM Integration

### Abstraction Pattern
```
LLMClientTrait (interface)
├── query(text): Result<String>
├── query_with_context(text, context): Result<String>
└── query_with_history(text, history): Result<String>
```

### Implementations
- **HttpLLMClient**: Production REST client (30s timeout)
- **MockLLMClient**: Testing with predictable responses

### Response Rendering (M1)
```
markdown response
  ↓
parse code blocks
  ↓
apply syntax highlighting (rust, python, bash, json, yaml, js, html)
  ↓
format inline (bold, italic, code)
  ↓
convert to ANSI colors
  ↓
display in terminal
```

---

## Terminal State Management

### TerminalState Composition
```
TerminalState
├── OutputBuffer
│   ├── lines: Vec<String>
│   ├── scroll_offset: usize
│   └── max_lines: 10,000
├── InputBuffer
│   ├── text: String
│   ├── cursor_pos: usize
│   └── methods: insert, delete, move_cursor
├── CommandHistory
│   ├── entries: Vec<String>
│   ├── position: Option<usize>
│   └── methods: previous, next, add
└── TerminalMode
    ├── Normal
    ├── ExecutingCommand
    ├── WaitingLLM
    └── PromptingInstall
```

### Event Loop
```
poll_event()
  ↓
classify_input(InputClassifier)
  ↓
route to orchestrator
  ├── Command → CommandOrchestrator
  ├── NaturalLanguage → NaturalLanguageOrchestrator
  ├── CommandTypo → CommandOrchestrator (with suggestion)
  └── Empty → (do nothing)
  ↓
update state
  ↓
render(TerminalTUI)
```

---

## File Size & Complexity

| Diagram | Size | Complexity | Best For |
|---------|------|-----------|----------|
| 01-architecture-overview | 4.8K | Medium | System overview |
| 02-scan-algorithm | 5.3K | High | SCAN algorithm |
| 03-executor-module | 5.8K | High | Execution patterns |
| 04-input-module-detailed | 6.3K | Very High | Input details |
| 05-orchestrators | 6.3K | High | State & workflows |
| 06-llm-integration | 6.2K | Medium | LLM abstraction |
| 07-complete-system-class | 8.5K | Very High | Full system |

---

## How to Render

### Online (Easiest)
1. Go to https://www.plantuml.com/plantuml/uml/
2. Paste content from any .puml file
3. View rendered diagram

### Local (Java Required)
```bash
# Install PlantUML
brew install plantuml  # macOS
# or download jar from https://plantuml.com/download

# Render to PNG
plantuml docs/uml/01-architecture-overview.puml

# Render to SVG
plantuml -tsvg docs/uml/01-architecture-overview.puml
```

### VS Code (Recommended)
1. Install "PlantUML" extension
2. Open .puml file
3. Alt+D to preview
4. Right-click → Export to PNG/SVG

---

## Code-to-Diagram Mapping

### Input Module
- **02-scan-algorithm.puml** maps to `/src/input/`
- **04-input-module-detailed.puml** maps to `/src/input/`

### Executor Module
- **03-executor-module.puml** maps to `/src/executor/`

### Orchestrators
- **05-orchestrators.puml** maps to `/src/orchestrators/`
- Terminal state maps to `/src/terminal/state.rs`
- Buffers map to `/src/terminal/buffers.rs`

### LLM
- **06-llm-integration.puml** maps to `/src/llm/`

### Complete View
- **07-complete-system-class-diagram.puml** maps entire `/src/` tree

---

## Troubleshooting

### Diagram Won't Render
- Check PlantUML syntax (matching curly braces, quotes)
- Verify all classes have correct notation: `..|>` or `--|>`
- Check for special characters in names

### Want to Modify?
1. Edit the .puml file directly
2. Update mapping comments
3. Re-render using PlantUML tool
4. Verify code matches diagram

### Need to Update?
1. Make code changes
2. Update relevant .puml file(s)
3. Update README_DIAGRAMS.md
4. Keep diagrams in sync with source

---

## Related Resources

- **Source Code**: `/home/crist/infraware-terminal/terminal-app/src/`
- **Documentation**: `CLAUDE.md`, `SCAN_ARCHITECTURE.md`
- **Tests**: `/tests/` directory
- **Benchmarks**: `/benches/` directory

---

**Last Updated**: 2025-11-18
**Format**: PlantUML 1.2024.x
**Viewer**: Any PlantUML renderer
