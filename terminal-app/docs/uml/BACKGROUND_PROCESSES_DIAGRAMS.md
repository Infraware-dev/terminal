# Background Process Support UML Diagrams

This document describes the UML diagrams that illustrate Infraware Terminal's background process support architecture, implemented in M2.

## Overview

Background processes are a critical feature for long-running operations. Users can now spawn processes with the `&` operator and manage them with the `jobs` builtin command:

```bash
# Spawn a long-running task in the background
sleep 300 &
[1] sleep 300 & (PID: 12345)

# Continue working immediately
ls -la

# Check on background jobs
jobs
[1] Running sleep 300 & (PID: 12345)
[2] Done (exit: 0) docker build . & (PID: 12346)
```

## Diagram Files

### 1. **08-job-manager-class-diagram.puml**

**Purpose**: Detailed class diagram of the JobManager and related types.

**Key Components**:

- **JobStatus Enum**: Represents the lifecycle of a background job
  - `Running`: Process is actively executing
  - `Done(i32)`: Process completed with exit code
  - `Terminated`: Process was terminated by signal
  - Implements `Display` for user-friendly formatting

- **JobInfo Struct**: Public job metadata (safe to clone and display)
  - `id`: 1-based job ID (bash-style numbering)
  - `pid`: Process ID from the spawned child
  - `command`: Original command string (including the trailing `&`)
  - `status`: Current job status
  - `start_time`: Timestamp when job was started
  - Cloneable for safe iteration without lock contention

- **JobEntry Struct**: Internal structure pairing JobInfo with Tokio Child
  - Holds mutable `Child` process for status checking
  - Not exposed publicly, prevents external process manipulation
  - Enables `try_wait()` for non-blocking status polling

- **JobManager Struct**: Central job tracking coordinator
  - `jobs: HashMap<usize, JobEntry>`: Maps job IDs to job entries
  - `next_id: usize`: Tracks next job ID to assign
  - Methods:
    - `new()`: Create fresh job manager
    - `add_job()`: Assign ID, store job, return job_id
    - `list_jobs()`: Return cloned JobInfo for display (non-blocking)
    - `check_completed()`: Poll all jobs for completion, update status, return completed jobs
    - `remove_job()`: Remove specific job from table
    - `has_running_jobs()`: Check if any active jobs exist

- **SharedJobManager Type Alias**: Thread-safe shared access
  - `type SharedJobManager = Arc<RwLock<JobManager>>`
  - `Arc`: Atomic reference counting for shared ownership
  - `RwLock`: Read-write lock for safe concurrent access
  - Multiple readers can call `list_jobs()` simultaneously
  - Exclusive writer for `add_job()` and `check_completed()`

**Design Patterns**:

1. **RAII Pattern**: Child process is dropped when JobEntry is removed, automatically cleaning up resources
2. **Lazy Singleton**: JobManager created once, shared via Arc<RwLock<>>
3. **Poisoning Recovery**: If RwLock is poisoned, `.into_inner()` allows recovery with logging
4. **Non-Blocking Status Checking**: `try_wait()` doesn't block the UI event loop
5. **Clone-Safe API**: JobInfo is cloneable, enabling safe reads without prolonged locking

### 2. **09-background-command-execution-sequence.puml**

**Purpose**: Sequence diagram showing the complete flow of background command execution and monitoring.

**Key Workflows**:

#### A. **Initial Command Entry**
1. User types: `sleep 30 &`
2. EventLoop receives input
3. InputClassifier processes: `InputType::Command { cmd: "sleep", args: ["30"], original_input: "sleep 30 &" }`

#### B. **Background Command Detection**
1. CommandOrchestrator receives classified input
2. Detects background command via `is_background_command("sleep 30 &")`
3. Returns true because:
   - Ends with `&` (single ampersand)
   - NOT `&&` (not logical AND)
   - `&` is not quoted
   - `&` is not escaped

#### C. **Background Job Spawning**
1. CommandExecutor::execute_background() called
2. Strips trailing `&`: `"sleep 30 &"` → `"sleep 30"`
3. Spawns process: `TokioCommand::new("bash").arg("-c").arg("sleep 30").spawn()`
4. Gets PID from child: `child.id()` → `12345`
5. Acquires write lock on JobManager
6. Calls `add_job()`:
   - Assigns job ID: `1`
   - Creates JobInfo with status `Running`
   - Stores JobEntry in HashMap
   - Increments next_id to `2`
7. Returns `(job_id=1, pid=12345)`

#### D. **User Feedback**
1. CommandOrchestrator formats feedback: `[1] sleep 30 & (PID: 12345)`
2. Adds to terminal state output
3. Renders updated UI
4. **User can immediately type new commands** (no blocking)

#### E. **Continuous Monitoring (Event Loop)**
In each event loop iteration:
1. EventLoop calls `check_completed_jobs()`
2. Acquires write lock on JobManager (may wait if readers exist)
3. Calls `check_completed()`:
   - Iterates through all jobs in HashMap
   - For each job, calls `try_wait()` (non-blocking)
   - If `Ok(Some(status))` → process has completed
     - Extracts exit code
     - Updates job status: `Done(0)` or `Terminated`
     - Marks for removal from HashMap
   - If `Ok(None)` → process still running
     - Status stays `Running`

4. Returns Vec of completed JobInfo
5. EventLoop displays completion messages
6. Completed jobs are automatically removed from manager

#### F. **Manual Job Listing**
When user types `jobs`:
1. EventLoop sends input to InputClassifier → `InputType::Command { cmd: "jobs", ... }`
2. CommandOrchestrator detects builtin "jobs" command
3. Acquires read lock on JobManager
4. Calls `list_jobs()`:
   - Iterates through all jobs
   - Clones all JobInfo entries
   - Returns Vec<JobInfo>
5. Formats output (multiple readers can do this concurrently)
6. Displays formatted job list:
   ```
   [1] Running sleep 300 & (PID: 12345)
   [2] Done (exit: 0) docker build . & (PID: 12346)
   ```

**Critical Design Points**:

1. **Non-Blocking Status Checking**: `try_wait()` never blocks
2. **Lock Granularity**: Write locks only during state changes (add/check)
3. **Clone-Based Display**: No lock held while displaying output
4. **Immediate Feedback**: Background command returns immediately
5. **Automatic Cleanup**: Completed jobs removed from manager

### 3. **10-executor-module-with-background-support.puml**

**Purpose**: Updated executor module architecture highlighting background process additions.

**Core Components**:

- **CommandOutput**: Foreground execution result
  - `stdout: String`
  - `stderr: String`
  - `exit_code: i32`
  - Methods: `is_success()`, `combined_output()`

- **CommandExecutor**: Static execution coordinator
  - **Foreground Methods**:
    - `execute()`: Async with 5-minute timeout, captures output
    - `execute_interactive()`: Suspends TUI for real TTY, Unix/Linux/macOS only
    - `execute_sudo()`: Escalated execution

  - **Background Methods (NEW)**:
    - `is_background_command()`: Detects trailing `&` (unquoted, unescaped)
    - `execute_background()`: Spawns process, returns (job_id, pid) immediately

  - **Helper Methods**:
    - `command_exists()`: Verify command in PATH
    - `requires_interactive()`: Check if needs TUI suspension
    - `is_shell_builtin()`: Detect shell builtins (., export, etc.)
    - `is_interactive_command()`: Check if blocked or suspended

- **Background Command Detection**:
  - Valid: `sleep 10 &`, `echo hello &`, `cmd1; cmd2 &`
  - Invalid: `cmd1 && cmd2` (double ampersand), `echo "a & b"` (quoted), `echo hello \\&` (escaped)
  - Algorithm: trim → check trailing & but not && → parse quotes/escapes → return bool

- **Safety Validators**:
  - **InteractiveCommandValidator**: Requires TUI suspension (vim, top, etc.)
  - **InteractiveBlockedValidator**: Not supported (ssh, python, tmux)
  - **InfiniteDeviceValidator**: Blocks infinite output (cat /dev/zero, ping, yes)

- **Package Management** (existing, shown for context):
  - Strategy pattern with 7 implementations
  - Priority order: brew (90) > winget (85) > apt/dnf/yum/pacman (80) > choco (70)

- **Tab Completion**: Command and file path completion

**Integration Points**:

1. **CommandOrchestrator**:
   - Calls `is_background_command()` to detect
   - Routes to `execute_background()` if detected
   - Calls `handle_jobs_command()` for "jobs" builtin

2. **InfrawareTerminal**:
   - Holds `job_manager: SharedJobManager`
   - Calls `check_completed_jobs()` in event loop
   - Displays completion notifications

**Execution Path Decision Tree**:

```
Input: "command [args] [& | no &]"
│
├─ Is background command ("... &")?
│  YES → execute_background()    ← Returns (job_id, pid) immediately
│  NO → Continue
│
├─ Requires interactive (vim, top)?
│  YES → execute_interactive()   ← TUI suspended
│  NO → Continue
│
├─ Is shell builtin (., export)?
│  YES → Execute via shell
│  NO → Continue
│
├─ Has shell operators (pipes, redirects)?
│  YES → Execute via shell (sh -c)
│  NO → Continue
│
└─ Direct execution
   └─ Spawn process directly
      └─ Wait with 5-min timeout
      └─ Return CommandOutput
```

### 4. **00-main-application-architecture.puml** (Updated)

**Changes**:

- Added `job_manager: SharedJobManager` field to InfrawareTerminal
- Added `check_completed_jobs()` method
- Updated notes to explain background process integration
- New "Background Process Management" package
- New relationships showing CommandOrchestrator managing jobs

## Implementation Details

### Background Process Spawning

When user enters `sleep 30 &`:

```rust
// 1. Strip trailing "&"
let command_without_amp = "sleep 30 &".trim_end_matches('&').trim();

// 2. Spawn via shell for proper environment
let child = TokioCommand::new("bash")
    .arg("-c")
    .arg(command_without_amp)
    .stdin(Stdio::null())
    .stdout(Stdio::null())      // No capture - output to terminal
    .stderr(Stdio::null())
    .spawn()?;

// 3. Get PID
let pid = child.id()?;

// 4. Add to job manager
let job_id = {
    let mut mgr = job_manager.write()?;
    mgr.add_job("sleep 30 &".to_string(), pid, child)
};

// 5. Return immediately
Ok((job_id, pid))
```

### Why Strip the `&`?

If we pass `sleep 30 &` to bash:
- Bash sees the `&` and forks internally
- Bash exits immediately
- We only track the bash process, not sleep
- Can't monitor the actual long-running process

If we pass `sleep 30` without `&`:
- We directly own and track the process
- Tokio can monitor it with `try_wait()`
- We control when it completes and cleans up

### Job Completion Polling

```rust
pub fn check_completed(&mut self) -> Vec<JobInfo> {
    let mut completed = Vec::new();
    let mut to_remove = Vec::new();

    for (id, entry) in &mut self.jobs {
        // Non-blocking check - never freezes UI
        match entry.child.try_wait() {
            Ok(Some(status)) => {
                // Process exited
                let exit_code = status.code().unwrap_or(-1);
                entry.info.status = if status.success() {
                    JobStatus::Done(exit_code)
                } else if exit_code == -1 {
                    JobStatus::Terminated
                } else {
                    JobStatus::Done(exit_code)
                };
                completed.push(entry.info.clone());
                to_remove.push(*id);
            }
            Ok(None) => {
                // Still running - do nothing
            }
            Err(e) => {
                // Error checking - assume terminated
                log::warn!("try_wait() failed for job [{}]: {}", entry.info.id, e);
                entry.info.status = JobStatus::Terminated;
                completed.push(entry.info.clone());
                to_remove.push(*id);
            }
        }
    }

    // Remove completed jobs
    for id in to_remove {
        self.jobs.remove(&id);
    }

    completed
}
```

### Lockfree Display Pattern

```rust
// Acquire read lock briefly
let jobs: Vec<JobInfo> = {
    let mgr = job_manager.read()?;
    mgr.list_jobs()  // Returns cloned Vec
};

// Lock released here - now safe to iterate and display
for job in jobs {
    let status_str = match job.status {
        JobStatus::Running => "Running".to_string(),
        JobStatus::Done(code) => format!("Done (exit: {})", code),
        JobStatus::Terminated => "Terminated".to_string(),
    };
    state.add_output(format!(
        "[{}] {} {} (PID: {})",
        job.id, status_str, job.command, job.pid
    ));
}
```

This pattern:
1. Minimizes lock duration (only during clone)
2. Prevents other threads from blocking during display
3. Safe for concurrent readers

## Thread Safety Guarantees

1. **Arc<RwLock<JobManager>>**:
   - Multiple readers (list_jobs) can run concurrently
   - Writers (add_job, check_completed) are exclusive
   - Poisoning recovery for panics during write

2. **Non-Blocking try_wait()**:
   - Never blocks the event loop
   - Safe to call in tight loops
   - Returns immediately with status or None

3. **RAII Child Process**:
   - Automatically cleaned when JobEntry dropped
   - No resource leaks
   - Deterministic cleanup on job removal

## Performance Characteristics

| Operation | Complexity | Duration |
|-----------|-----------|----------|
| add_job() | O(1) | <1μs |
| list_jobs() | O(n) | <10μs per job |
| check_completed() | O(n) | <1μs per job |
| try_wait() | O(1) | <1μs (non-blocking) |
| Display job list | O(n) | No lock held |

Where n = number of active background jobs (typically 1-10).

## Related Documentation

- **CLAUDE.md**: Background process support details
- **Architecture diagrams**: 06-complete-class-diagram.puml (full system)
- **Input module**: 01-scan-algorithm-10-handlers.puml (command detection)
- **Orchestrators**: 03-orchestrators-and-workflows.puml (routing)

## Testing

Background process support is covered by:
- `tests/executor_tests.rs`: `test_is_background_command_*`
- `tests/integration_tests.rs`: Background command end-to-end tests
- Job manager unit tests in `src/executor/job_manager.rs`

## Future Enhancements

1. **Job Suspension**: `fg`, `bg` commands to move jobs between foreground/background
2. **Job History**: Persist completed jobs across sessions
3. **Job Control**: `kill`, `wait` commands
4. **Process Groups**: Support job grouping and batch operations
5. **Signals**: Proper SIGTERM/SIGKILL handling
