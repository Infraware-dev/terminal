# Background Processes Quick Reference

## Key Concepts

### What are Background Processes?

Long-running tasks spawned with the `&` operator that don't block the terminal:

```bash
# Foreground (blocks terminal)
docker build .

# Background (returns immediately)
docker build . &
[1] docker build . & (PID: 12345)
```

## Usage

### Spawn a Background Process

```bash
# Simple background task
sleep 300 &

# Pipe with background
cat large_file.txt | gzip > file.gz &

# Multiple commands
echo "Starting..." && sleep 60 && echo "Done" &
```

### List Background Jobs

```bash
jobs
[1] Running sleep 300 & (PID: 12345)
[2] Done (exit: 0) docker build . & (PID: 12346)
[3] Terminated my_app & (PID: 12347)
```

### Job Status States

| Status | Meaning |
|--------|---------|
| Running | Process is actively executing |
| Done (exit: N) | Process completed with exit code N |
| Terminated | Process was terminated (by signal, etc.) |

## Architecture

### Core Types

```rust
// Job status lifecycle
enum JobStatus {
    Running,           // Process active
    Done(i32),         // Completed with exit code
    Terminated,        // Terminated by signal
}

// Public job information (safe to clone)
struct JobInfo {
    id: usize,         // 1-based job ID (bash-style)
    pid: u32,          // Process ID
    command: String,   // Original command with "&"
    status: JobStatus, // Current status
    start_time: Instant, // When spawned
}

// Thread-safe shared manager
type SharedJobManager = Arc<RwLock<JobManager>>;
```

### JobManager Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `new()` | Create fresh manager | Self |
| `add_job(cmd, pid, child)` | Register new job | job_id |
| `list_jobs()` | Get all jobs | Vec<JobInfo> |
| `check_completed()` | Poll for completions | Vec<JobInfo> (completed) |
| `job_count()` | Count active jobs | usize |
| `has_running_jobs()` | Any jobs running? | bool |

### CommandExecutor Background Methods

| Method | Purpose |
|--------|---------|
| `is_background_command(input: &str)` | Detect trailing `&` |
| `execute_background(cmd, job_manager)` | Spawn background process |

## Execution Flow

```
User Input: "sleep 30 &"
         ↓
InputClassifier.classify()
         ↓
InputType::Command {
  cmd: "sleep",
  args: ["30"],
  original_input: "sleep 30 &"
}
         ↓
CommandOrchestrator.handle_command()
         ↓
is_background_command("sleep 30 &") → true
         ↓
execute_background_and_display()
         ↓
CommandExecutor.execute_background()
  1. Strip "&": "sleep 30 &" → "sleep 30"
  2. Spawn: TokioCommand::new("bash")
           .arg("-c")
           .arg("sleep 30")
           .spawn()
  3. Get PID
  4. Add to JobManager
         ↓
Return (job_id=1, pid=12345)
         ↓
Display: "[1] sleep 30 & (PID: 12345)"
         ↓
User prompt returns immediately
```

## Monitoring Flow

```
Event Loop (each iteration)
         ↓
check_completed_jobs()
         ↓
JobManager.check_completed()
  For each job:
    - try_wait() [non-blocking]
    - If exited: update status
    - If completed: add to return vec
    - Remove completed jobs
         ↓
Return Vec<JobInfo> (newly completed)
         ↓
Display notifications for completed jobs
         ↓
Render UI
```

## Design Patterns

### 1. RAII (Resource Acquisition Is Initialization)

Child process is automatically cleaned when dropped:

```rust
// JobEntry dropped → Child dropped → process resources freed
self.jobs.remove(&id);  // Auto cleanup
```

### 2. Non-Blocking Status Checking

```rust
// try_wait() never blocks the event loop
match entry.child.try_wait() {
    Ok(Some(status)) => { /* exited */ }
    Ok(None) => { /* still running */ }
    Err(e) => { /* error */ }
}
```

### 3. Lock-Free Display Pattern

```rust
// Hold lock only for cloning
let jobs = {
    let mgr = job_manager.read()?;
    mgr.list_jobs()  // Clone data
};
// Lock released

// Display without holding lock
for job in jobs { /* display */ }
```

### 4. 1-Based Job IDs

Like bash, job IDs start at 1:

```rust
let id = self.next_id;  // 1, 2, 3, ...
self.next_id += 1;
```

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| add_job() | <1μs | HashMap insert |
| list_jobs() | <10μs per job | Cloning JobInfo |
| check_completed() | <1μs per job | try_wait() only |
| try_wait() | <1μs | Non-blocking |

**Event Loop Impact**: Negligible for typical workloads (1-10 jobs).

## Thread Safety

```rust
type SharedJobManager = Arc<RwLock<JobManager>>;

// Multiple readers (list_jobs)
{
    let mgr = job_manager.read()?;
    let jobs = mgr.list_jobs();  // All can read concurrently
}

// Exclusive writer (add_job, check_completed)
{
    let mut mgr = job_manager.write()?;
    mgr.add_job(...);            // Only one writer
}
```

## Error Handling

### Poisoned Lock

If a panic occurs during write:

```rust
match job_manager.write() {
    Ok(guard) => { /* normal */ }
    Err(poisoned) => {
        log::error!("Lock poisoned, recovering...");
        poisoned.into_inner()  // Recover from panic
    }
}
```

### try_wait() Errors

```rust
match entry.child.try_wait() {
    Err(e) => {
        // Log error, assume terminated
        log::warn!("try_wait failed: {}", e);
        entry.info.status = JobStatus::Terminated;
    }
}
```

## Implementation Details

### Why Strip the `&`?

Command line with `&`:
```bash
bash -c "sleep 30 &"
→ bash forks internally
→ bash returns
→ we only track bash (already done)
→ can't monitor sleep
```

Command without `&`:
```bash
bash -c "sleep 30"
→ bash runs sleep synchronously
→ bash waits for sleep
→ we own the sleep process
→ can monitor with try_wait()
```

### Why Stdio::null()?

Background processes don't capture output:

```rust
.stdout(Stdio::null())   // Output goes to terminal
.stderr(Stdio::null())   // Not buffered
```

Advantages:
- No buffering delays
- Real-time output visibility
- User sees output immediately
- Lower memory usage

### Background Command Detection

Valid patterns:
```bash
sleep 10 &              # Simple
cmd1; cmd2 &            # Multiple commands
cat file | gzip &       # Pipes
$(echo test) &          # Subshells
```

Invalid patterns:
```bash
cmd1 && cmd2            # Logical AND (not background)
echo "a & b"            # Quoted ampersand
echo hello \\&          # Escaped ampersand
```

## Code Examples

### Checking for Background Command

```rust
if CommandExecutor::is_background_command("sleep 10 &") {
    // Spawn background process
    let (job_id, pid) = CommandExecutor::execute_background(
        "sleep 10 &",
        &job_manager
    ).await?;

    println!("[{}] {} (PID: {})", job_id, "sleep 10 &", pid);
}
```

### Listing Jobs

```rust
let jobs = {
    let mgr = job_manager.read()?;
    mgr.list_jobs()
};

for job in jobs {
    println!("[{}] {} {} (PID: {})",
        job.id,
        job.status,
        job.command,
        job.pid
    );
}
```

### Checking Job Completion

```rust
let completed = {
    let mut mgr = job_manager.write()?;
    mgr.check_completed()
};

for job in completed {
    println!("Job [{}] {} (exit: {:?})", job.id, job.command, job.status);
}
```

## Related Diagrams

1. **08-job-manager-class-diagram.puml** - JobManager architecture
2. **09-background-command-execution-sequence.puml** - Execution flow
3. **10-executor-module-with-background-support.puml** - Integration
4. **00-main-application-architecture.puml** - System overview

## Testing

Test background commands:

```bash
# Create test background processes
sleep 10 & sleep 20 & sleep 30 &

# Check job listing
jobs

# Run other commands while jobs run
ls -la

# Check jobs again
jobs

# Wait for completion (watch jobs list)
jobs
```

## Limitations & Future Work

**Current (M2)**:
- Fire-and-forget execution
- Job listing and status checking
- Non-blocking monitoring

**Future (M3+)**:
- `fg` - Move job to foreground
- `bg` - Resume suspended job
- `kill` - Terminate job
- `wait` - Wait for specific job
- Job suspension/resumption
- Better signal handling

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Process not showing in jobs | Check if it has completed (status shows Done/Terminated) |
| High CPU from monitoring | Increase polling interval (currently per event loop iteration) |
| Lock contention | Reduce frequency of list_jobs() calls |
| Zombie processes | Ensure try_wait() is called regularly |
