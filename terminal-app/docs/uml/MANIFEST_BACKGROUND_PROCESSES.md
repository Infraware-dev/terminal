# Background Process Support UML Diagrams - Manifest

## Overview

This manifest documents the complete set of UML diagrams for Infraware Terminal's background process support (M2 milestone).

## Diagram Files

### 1. Class Diagrams

#### `08-job-manager-class-diagram.puml` ⭐ START HERE
**Focus**: JobManager and background job tracking architecture

- **Components**:
  - `JobStatus` enum (Running, Done, Terminated)
  - `JobInfo` struct (public job information)
  - `JobEntry` struct (internal job entry with Child process)
  - `JobManager` struct (central coordinator)
  - `SharedJobManager` type alias (Arc<RwLock<JobManager>>)

- **Key Concepts**:
  - Job lifecycle management
  - Non-blocking status checking via try_wait()
  - Thread-safe access patterns
  - RAII-based resource cleanup
  - Clone-safe public API

- **Best For**: Understanding job data structures and manager interface

**File Size**: ~8 KB | **Lines**: ~350

---

#### `10-executor-module-with-background-support.puml`
**Focus**: CommandExecutor enhancements for background processes

- **Components**:
  - `CommandOutput` (foreground execution result)
  - `CommandExecutor` (static execution coordinator)
  - Background command detection logic
  - Safety validators (interactive, infinite devices)
  - Package management (strategy pattern)
  - Tab completion

- **New Methods**:
  - `is_background_command()` - Detect trailing `&`
  - `execute_background()` - Spawn and return immediately
  - Updated `execute()` - Path selection logic

- **Key Concepts**:
  - Foreground vs. background vs. interactive execution
  - Shell operator handling
  - Command validation and safety checks
  - Ampersand detection (quoted, escaped, double)

- **Best For**: Understanding command execution flow and safety validation

**File Size**: ~12 KB | **Lines**: ~400

---

#### `06-complete-class-diagram.puml` (Updated)
**Focus**: Full system class diagram

- **New Sections**:
  - Background job management package
  - JobManager integration with CommandOrchestrator
  - SharedJobManager type alias

- **Includes**:
  - All input handlers (SCAN algorithm)
  - All orchestrators
  - Complete execution pipeline
  - LLM integration

- **Best For**: High-level system architecture overview

**File Size**: ~20 KB | **Lines**: ~500+

---

#### `00-main-application-architecture.puml` (Updated)
**Focus**: Main application structure and dependencies

- **Changes**:
  - Added `job_manager: SharedJobManager` field
  - Added `check_completed_jobs()` method
  - New "Background Process Management" package
  - Updated relationships

- **Key Concepts**:
  - Application-level job coordination
  - Event loop integration
  - Builder pattern with job manager setup

- **Best For**: Understanding how background processes fit into main app

**File Size**: ~6 KB | **Lines**: ~200+

---

### 2. Sequence Diagrams

#### `09-background-command-execution-sequence.puml` ⭐ DETAILED FLOW
**Focus**: Complete workflow of background command execution and monitoring

- **Sequences**:
  1. **Initial Input**: User types `sleep 30 &`
  2. **Classification**: InputClassifier processes command
  3. **Detection**: CommandOrchestrator detects background
  4. **Validation**: is_background_command() logic
  5. **Spawning**: Process creation and JobManager integration
  6. **Display**: User feedback
  7. **Monitoring**: Continuous polling in event loop
  8. **Completion**: Status updates and cleanup
  9. **Listing**: Manual `jobs` command

- **Key Interactions**:
  - EventLoop ↔ InputClassifier
  - CommandOrchestrator ↔ CommandExecutor
  - CommandExecutor ↔ JobManager
  - EventLoop ↔ JobManager (monitoring)

- **Timing Notes**:
  - Background spawn: <1ms total (non-blocking)
  - try_wait() per job: <1μs (non-blocking)
  - Display formatting: No lock held

- **Best For**: Understanding command lifecycle and monitoring

**File Size**: ~15 KB | **Lines**: ~400

---

## Documentation Files

### `BACKGROUND_PROCESSES_DIAGRAMS.md` ⭐ COMPREHENSIVE
Complete technical documentation of background process architecture.

**Sections**:
- Overview and use cases
- Detailed component descriptions
- Design patterns (RAII, Lazy Singleton, Clone-Safe API)
- Implementation details
- Thread safety guarantees
- Performance characteristics
- Integration points
- Testing coverage
- Future enhancements

**Best For**: In-depth understanding of design decisions

**File Size**: ~15 KB

---

### `BACKGROUND_PROCESSES_QUICK_REFERENCE.md` ⭐ PRACTICAL GUIDE
Quick reference for usage, architecture, and implementation details.

**Sections**:
- Key concepts and usage examples
- Architecture overview
- Execution flow diagrams
- Monitoring flow
- Design patterns
- Performance metrics
- Thread safety
- Code examples
- Error handling
- Troubleshooting

**Best For**: Developers implementing or debugging background processes

**File Size**: ~12 KB

---

## Reading Order

### For Quick Understanding (5-10 minutes)
1. `BACKGROUND_PROCESSES_QUICK_REFERENCE.md` - Overview and patterns
2. `08-job-manager-class-diagram.puml` - Data structures
3. `10-executor-module-with-background-support.puml` - Execution flow

### For Complete Understanding (30-45 minutes)
1. `BACKGROUND_PROCESSES_QUICK_REFERENCE.md` - Concepts and usage
2. `08-job-manager-class-diagram.puml` - JobManager details
3. `09-background-command-execution-sequence.puml` - Full workflow
4. `10-executor-module-with-background-support.puml` - Executor details
5. `00-main-application-architecture.puml` - System integration
6. `BACKGROUND_PROCESSES_DIAGRAMS.md` - Deep dive

### For Implementation (reference while coding)
1. `BACKGROUND_PROCESSES_QUICK_REFERENCE.md` - API reference
2. `09-background-command-execution-sequence.puml` - Flow logic
3. `08-job-manager-class-diagram.puml` - Type signatures
4. Source code: `src/executor/job_manager.rs`, `src/executor/command.rs`, `src/orchestrators/command.rs`

## Diagram Statistics

| Diagram | Type | Size | Purpose |
|---------|------|------|---------|
| 08-job-manager-class-diagram.puml | Class | 8 KB | Job tracking |
| 09-background-command-execution-sequence.puml | Sequence | 15 KB | Full workflow |
| 10-executor-module-with-background-support.puml | Class | 12 KB | Execution pipeline |
| 00-main-application-architecture.puml | Class | 6 KB | System overview |
| 06-complete-class-diagram.puml | Class | 20 KB | Complete system |

## Key Design Decisions

### 1. Non-Blocking Status Checking
- Uses `try_wait()` instead of `wait()` or `wait_with_timeout()`
- Never blocks the event loop
- Safe for tight polling (each iteration)
- Returns immediately: Ok(Some(status)), Ok(None), or Err(e)

### 2. Ampersand Stripping
- Input: `"sleep 30 &"`
- Stripped to: `"sleep 30"`
- Passed to shell: `bash -c "sleep 30"`
- Result: We own and track the process (not bash)

### 3. Null Output Handling
- Background process output: stdout/stderr = null
- Output goes directly to terminal
- Not buffered in application
- No capture overhead

### 4. Clone-Safe JobInfo
- JobInfo is cloneable (all fields are Copy or String)
- list_jobs() returns Vec<JobInfo> (cloned data)
- Lock released immediately after clone
- Safe to iterate and display without holding lock

### 5. 1-Based Job IDs
- Job IDs: 1, 2, 3, ... (like bash)
- next_id: usize (starting at 1)
- Bash-compatible numbering
- Consistent with user expectations

### 6. Automatic Cleanup
- Completed jobs removed from HashMap
- Child process dropped → resources freed
- No zombie processes (Tokio handles)
- Memory doesn't grow unbounded

## Integration Points

### InputClassifier
- Produces: `InputType::Command { original_input: "sleep 30 &", ... }`

### CommandOrchestrator
- Detects: `is_background_command(original_input)`
- Routes: `execute_background_and_display()`
- Handles: `"jobs"` builtin command

### CommandExecutor
- Methods: `is_background_command()`, `execute_background()`
- Returns: `(job_id: usize, pid: u32)`
- Adds: Job to SharedJobManager

### TerminalState
- Stores: Output for display
- Messages: Job completion notifications

### InfrawareTerminal (Main App)
- Holds: `job_manager: SharedJobManager`
- Calls: `check_completed_jobs()` in event loop
- Displays: Completion messages

## Testing Coverage

### Unit Tests (src/executor/job_manager.rs)
- JobStatus display formatting
- JobManager creation and initialization
- Job listing (empty manager)
- Shared job manager creation
- (Integration tests cover actual job spawning)

### Integration Tests (tests/*)
- `test_is_background_command_*`: Background detection
- End-to-end background command execution
- Job completion monitoring
- Jobs command listing

## Performance Notes

### Event Loop Impact
- `check_completed_jobs()` per iteration: <1ms for typical workload
- try_wait() per job: <1μs
- Display formatting: No lock held
- Memory: O(n) where n = number of jobs (typically 1-10)

### Lock Contention
- Read lock (list_jobs): Multiple concurrent readers
- Write lock (add_job, check_completed): Exclusive, brief
- Typical hold time: <100μs
- Poisoning recovery: Logged but continues

## Related Documents in Repository

- **CLAUDE.md**: Background process requirements and usage
- **src/executor/job_manager.rs**: Implementation with tests
- **src/executor/command.rs**: execute_background() method
- **src/orchestrators/command.rs**: CommandOrchestrator integration
- **src/main.rs**: InfrawareTerminal integration
- **tests/executor_tests.rs**: Background command tests
- **tests/integration_tests.rs**: End-to-end tests

## Version History

**M2 (Current)**:
- Background process support complete
- execute_background() spawning
- check_completed_jobs() monitoring
- "jobs" builtin command
- Non-blocking polling

**M3+ (Planned)**:
- fg/bg commands (foreground/background movement)
- Job suspension/resumption
- Signal handling (SIGTERM, SIGKILL)
- Process groups
- wait command
- Better error reporting

## PlantUML Rendering Tips

### Online Viewers
- PlantUML Online: http://www.plantuml.com/plantuml/uml/
- Kroki: https://kroki.io/
- VS Code Extension: `jebbs.plantuml`

### Local Tools
```bash
# Install PlantUML
# Ubuntu: sudo apt install plantuml
# macOS: brew install plantuml

# Render to PNG
plantuml 08-job-manager-class-diagram.puml -o ../png/

# Render to SVG
plantuml -tsvg 08-job-manager-class-diagram.puml
```

### VS Code Integration
1. Install "PlantUML" extension by jebbs
2. Right-click diagram → "PlantUML: Preview"
3. Export to PNG/SVG as needed

## Contributing

When updating background process architecture:
1. Update relevant diagram file(s)
2. Update `BACKGROUND_PROCESSES_DIAGRAMS.md` with changes
3. Update `BACKGROUND_PROCESSES_QUICK_REFERENCE.md` if user-facing
4. Run tests: `cargo test --test executor_tests`
5. Run benchmarks: `cargo bench`
6. Update CLAUDE.md if behavior changes

## Questions?

Refer to:
1. Quick reference for usage and concepts
2. Sequence diagram for workflow
3. Class diagrams for structure
4. Source code for implementation details
5. CLAUDE.md for requirements
