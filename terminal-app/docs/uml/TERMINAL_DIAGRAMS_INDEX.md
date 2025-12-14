# Terminal Module Diagrams - Quick Index

## Overview

This directory contains 5 comprehensive PlantUML diagrams documenting the terminal module architecture, along with detailed documentation. The diagrams reflect the latest code structure as of **2025-12-14** and cover all major components.

---

## Diagram Summary Table

| Diagram | File | Lines | Focus | Key Classes |
|---------|------|-------|-------|------------|
| **Module Overview** | `terminal-module-overview.puml` | 343 | Architecture & relationships | TerminalUI, TerminalState, OutputBuffer, InputBuffer, CommandHistory, ThrobberAnimator, EventHandler |
| **TUI Rendering Flow** | `terminal-tui-rendering-flow.puml` | 305 | Render pipeline | TerminalUI, render_frame, render_unified_content, 5 rendering phases |
| **State Management** | `terminal-state-management.puml` | 312 | State machine & HITL | TerminalMode transitions, PendingInteraction, ConfirmationType, ScrollbarInfo |
| **Event Handling** | `terminal-event-handling.puml` | 363 | Event processing | EventHandler, TerminalEvent, key/mouse mappings, context-aware handling |
| **Buffer Components** | `terminal-buffer-components.puml` | 429 | SRP design & implementation | OutputBuffer, InputBuffer, CommandHistory, ThrobberAnimator, composition |

**Total Documentation:** 2,123 lines of PlantUML + markdown

---

## Reading Guide

### For Beginners (Architecture Overview)
Start with these in order:
1. **terminal-module-overview.puml** - See all components and how they connect
2. **TERMINAL_MODULE_DIAGRAMS.md** - Read the overview section
3. **terminal-state-management.puml** - Understand the mode state machine

### For Understanding Data Flow
Follow this sequence:
1. **terminal-event-handling.puml** - See how input enters the system
2. **terminal-tui-rendering-flow.puml** - See how content is displayed
3. **terminal-buffer-components.puml** - See how buffers store and manage data

### For Implementation Details
Deep dive into:
1. **terminal-buffer-components.puml** - Understand SRP design
2. **terminal-tui-rendering-flow.puml** - Rendering mechanics (5 phases)
3. **terminal-state-management.puml** - HITL flow and mode transitions
4. **terminal-event-handling.puml** - Event mapping and Windows compatibility

### For Testing
Reference:
1. **terminal-buffer-components.puml** - Testing strategy section
2. **TERMINAL_MODULE_DIAGRAMS.md** - Testing Strategy section
3. Source code in `src/terminal/buffers.rs` for test examples

---

## Component Relationships

```
EventHandler
    ↓ (produces)
TerminalEvent
    ↓ (main.rs processes)
TerminalState (composite)
    ├─ OutputBuffer (scrolling)
    ├─ InputBuffer (user input)
    ├─ CommandHistory (navigation)
    └─ ThrobberAnimator (animation)
    ↓ (state updated)
TerminalUI (facade)
    ↓ (renders via)
render_frame()
    → render_unified_content()
    ↓ (5 phases)
    → Ratatui Widgets (Paragraph, Scrollbar)
```

---

## Key Architectural Concepts

### 1. Facade Pattern (TerminalUI)
Hides ratatui complexity behind simple API:
- `new()` - Initialize terminal
- `render()` - Draw frame
- `cleanup()` - Clean up on exit
- `suspend()` / `resume()` - For interactive commands

### 2. Composite Pattern (TerminalState)
Composes focused buffer components:
- Delegates input to InputBuffer
- Delegates output to OutputBuffer
- Delegates history to CommandHistory
- Delegates animation to ThrobberAnimator

### 3. State Machine (TerminalMode)
7 distinct modes with clear transitions:
- Normal → ExecutingCommand → Normal
- Normal → WaitingLLM → AwaitingApproval/Answer
- Normal → AwaitingMoreInput → Normal (multiline)

### 4. Single Responsibility Principle (SRP)
Each component has one job:
- **OutputBuffer**: Scrolling + buffering
- **InputBuffer**: User input editing
- **CommandHistory**: Navigation
- **ThrobberAnimator**: Loading animation

---

## Quick Facts

### Code Coverage
- Terminal module files: 7 files (tui.rs, state.rs, buffers.rs, events.rs, throbber.rs, splash.rs, mod.rs)
- Total lines of code: ~1,400 LOC
- Test coverage: 75%+ (M1 requirement met)

### Performance Targets
- ANSI parsing: Done once, cached (O(1) rendering)
- OutputBuffer trim: 10K max lines, trim 1K at a time
- Throbber animation: 10 FPS (100ms interval)
- Auto-scroll: Only if user at bottom
- Scroll calculations: O(1) via OutputBuffer

### Design Highlights
- Unified content rendering (output + prompt same area)
- Smart auto-scroll (preserves position if scrolled up)
- Event polling pause during interactive commands
- Unicode-safe input cursor (characters, not bytes)
- Thread-safe animation via Arc<Atomic>

---

## File Locations

All diagrams and documentation:
```
/home/crist/infraware-terminal/terminal-app/docs/uml/
├── terminal-module-overview.puml
├── terminal-tui-rendering-flow.puml
├── terminal-state-management.puml
├── terminal-event-handling.puml
├── terminal-buffer-components.puml
├── TERMINAL_MODULE_DIAGRAMS.md          (main documentation)
└── TERMINAL_DIAGRAMS_INDEX.md           (this file)
```

Source code:
```
/home/crist/infraware-terminal/terminal-app/src/terminal/
├── mod.rs                  (module exports)
├── tui.rs                  (TerminalUI - facade)
├── state.rs                (TerminalState - composite)
├── buffers.rs              (Output/Input/History buffers - SRP)
├── events.rs               (EventHandler + TerminalEvent)
├── throbber.rs             (ThrobberAnimator - animation)
└── splash.rs               (SplashScreen)
```

---

## Viewing the Diagrams

### Online
1. Visit http://www.plantuml.com/plantuml/uml/
2. Copy contents of .puml file
3. Paste into editor
4. View rendered diagram

### VS Code
1. Install "PlantUML" extension
2. Open .puml file
3. Right-click → "Preview Current Diagram"

### IntelliJ IDEA
1. Install "PlantUML Integration" plugin
2. Open .puml file
3. View panel shows diagram live

### Command Line
```bash
# Install plantuml (macOS)
brew install plantuml

# Generate PNG from PUML
plantuml terminal-module-overview.puml

# View PNG
open terminal-module-overview.png
```

---

## Documentation Structure

### Primary Documentation
- **TERMINAL_MODULE_DIAGRAMS.md** (371 lines)
  - Comprehensive reference guide
  - Each diagram explained in detail
  - Design patterns documented
  - SOLID principles applied
  - Testing strategy
  - Architecture decisions

### This Index
- **TERMINAL_DIAGRAMS_INDEX.md** (this file)
  - Quick reference guide
  - Reading guides for different audiences
  - Component relationships
  - Key facts and highlights

### Diagrams
- 5 PlantUML files, 1,752 lines total
- Each with detailed inline notes
- Color-coded boxes
- Clear relationships and dependencies

---

## How to Use These Diagrams

### For Code Review
1. Open `terminal-module-overview.puml`
2. Verify new code aligns with diagram
3. Check component responsibilities
4. Ensure no responsibility crossing (SRP)

### For Onboarding
1. Start with `terminal-module-overview.puml`
2. Read `TERMINAL_MODULE_DIAGRAMS.md` overview
3. Study `terminal-state-management.puml` for modes
4. Review `terminal-buffer-components.puml` for design

### For Debugging
1. `terminal-tui-rendering-flow.puml` - rendering issues
2. `terminal-event-handling.puml` - input issues
3. `terminal-buffer-components.puml` - data structure issues
4. `terminal-state-management.puml` - mode/state issues

### For Refactoring
1. `terminal-buffer-components.puml` - SRP guide
2. `terminal-module-overview.puml` - relationships
3. SOLID principles section in documentation

---

## Related Documentation

- **docs/CLAUDE.md** - Project guidelines and quick reference
- **docs/SCROLLING_ARCHITECTURE.md** - Detailed scrolling design
- **docs/INTERACTIVE_COMMANDS_ARCHITECTURE.md** - Suspend/resume design
- **src/terminal/buffers.rs** - Detailed code comments
- **src/terminal/state.rs** - State management implementation
- **src/terminal/tui.rs** - Rendering implementation

---

## Maintenance

### When Code Changes
1. Update the corresponding .puml file
2. Verify PlantUML syntax
3. Update TERMINAL_MODULE_DIAGRAMS.md if needed
4. Commit diagrams with code changes

### Keeping Diagrams Current
- Review diagrams monthly
- Update when major refactoring occurs
- Verify alignment with actual code
- Keep inline notes accurate

### Review Checklist
- [ ] All public types documented
- [ ] All relationships shown
- [ ] Design patterns labeled
- [ ] SOLID principles evident
- [ ] Notes match implementation

---

## Key Takeaways

1. **Clean Architecture**: TerminalUI uses Facade + TerminalState uses Composite
2. **Separation of Concerns**: 4 independent buffer components (SRP)
3. **State Machine**: Clear, documented mode transitions
4. **Event-Driven**: Clean event abstraction from crossterm
5. **Thread-Safe**: Atomic operations for animation
6. **Performance**: ANSI parsing cached, O(1) rendering
7. **Unicode-Safe**: Character-based cursor, not byte-based
8. **Windows Compatible**: Special handling for key event kinds
9. **Testable**: SRP design enables focused unit tests
10. **Maintainable**: Clear responsibilities, SOLID principles

---

## Quick Links

- [PlantUML Documentation](http://plantuml.com/guide.html)
- [UML Class Diagram Guide](https://www.uml-diagrams.org/class-diagrams-overview.html)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Ratatui Documentation](https://docs.rs/ratatui/latest/ratatui/)
- [Crossterm Documentation](https://docs.rs/crossterm/latest/crossterm/)

---

**Last Updated:** 2025-12-14
**Diagram Version:** 1.0
**Code Version:** Latest (feature/new-terminal branch)
