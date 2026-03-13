# Plan & Execute Phases Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the incident investigation pipeline with Planning and Execution phases after the report is written.

**Architecture:** Two new LLM agents (PlannerAgent, ExecutorAgent) chained after the existing ReporterAgent via HITL gates. Reuses the existing HitlHook/PromptHook interception pattern with new ResumeContext variants. A review loop lets the user iterate on the plan before execution.

**Tech Stack:** Rust, rig-rs, async-stream, tokio, serde/schemars

**Spec:** `docs/superpowers/specs/2026-03-13-plan-and-execute-design.md`

**Conventions:** @rust-conventions, @cargo-toml-conventions

---

## Chunk 1: Foundation — Phases, State, and SavePlanTool

### Task 1: Add new IncidentPhase variants

**Files:**
- Modify: `src/agent/shared/events.rs:10-15`

- [ ] **Step 1: Add `Planning` and `Executing` to `IncidentPhase` enum**

Add two new variants after `Reporting`:

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IncidentPhase {
    Investigating,
    Analyzing,
    Reporting,
    Planning,
    Executing,
    Completed,
}
```

- [ ] **Step 2: Run tests to verify nothing breaks**

Run: `cargo test --lib agent::shared::events`
Expected: All existing tests pass (serde roundtrip, etc.)

- [ ] **Step 3: Commit**

```bash
git add src/agent/shared/events.rs
git commit -m "feat(incident): add Planning and Executing incident phases"
```

### Task 2: Add new ResumeContext variants and PendingInterrupt constructors

**Files:**
- Modify: `src/agent/adapters/rig/state.rs:252-297` (ResumeContext enum)
- Modify: `src/agent/adapters/rig/state.rs:158-248` (PendingInterrupt impl)

- [ ] **Step 1: Add 5 new ResumeContext variants**

Add after the existing `IncidentQuestion` variant:

```rust
/// Waiting for operator to confirm creating a remediation plan
IncidentPlanConfirmation {
    /// Accumulated investigation context
    context: IncidentContext,
    /// Analysis text from AnalystAgent
    analysis_text: String,
    /// Path to the saved report file
    report_path: String,
},
/// Waiting for operator to answer a planner scoping/review question
IncidentPlannerQuestion {
    /// The question asked
    question: String,
    /// Predefined answer choices (if any)
    options: Option<Vec<String>>,
    /// Accumulated investigation context
    context: IncidentContext,
    /// Analysis text from AnalystAgent
    analysis_text: String,
    /// Current revision round (0-indexed, max 10)
    revision_round: usize,
    /// Whether this is a review loop question (true) or a scoping question (false)
    is_review: bool,
    /// Plan content (present when `is_review` is true)
    plan_content: Option<String>,
    /// Plan file path (present when `is_review` is true)
    plan_path: Option<String>,
},
/// Waiting for operator to confirm executing the remediation plan
IncidentExecutionConfirmation {
    /// Accumulated investigation context
    context: IncidentContext,
    /// Full content of the saved plan
    plan_content: String,
    /// Path to the saved plan file
    plan_path: String,
},
/// Waiting for operator to approve a remediation command during plan execution
IncidentPlanCommand {
    /// The command to execute
    command: String,
    /// Why this command is needed
    motivation: String,
    /// Whether the ExecutorAgent needs to process the output
    needs_continuation: bool,
    /// Risk level declared by the agent
    risk_level: RiskLevel,
    /// Expected diagnostic value
    expected_diagnostic_value: String,
    /// Full content of the plan being executed
    plan_content: String,
    /// Path to the plan file
    plan_path: String,
},
/// Waiting for operator to answer an executor question (e.g., rollback/skip/abort)
IncidentExecutorQuestion {
    /// The question asked
    question: String,
    /// Predefined answer choices (if any)
    options: Option<Vec<String>>,
    /// Full content of the plan being executed
    plan_content: String,
    /// Path to the plan file
    plan_path: String,
},
```

- [ ] **Step 2: Add PendingInterrupt constructors for each new variant**

Add these methods to the `impl PendingInterrupt` block:

```rust
/// Create an incident plan confirmation interrupt (y/n to start planning)
pub fn incident_plan_confirmation(
    context: IncidentContext,
    analysis_text: String,
    report_path: String,
) -> Self {
    Self {
        resume_context: ResumeContext::IncidentPlanConfirmation {
            context,
            analysis_text,
            report_path,
        },
        tool_call_id: None,
        tool_args: None,
    }
}

/// Create an incident planner question interrupt
#[expect(
    clippy::too_many_arguments,
    reason = "All fields required for planner question context"
)]
pub fn incident_planner_question(
    question: String,
    options: Option<Vec<String>>,
    context: IncidentContext,
    analysis_text: String,
    revision_round: usize,
    is_review: bool,
    plan_content: Option<String>,
    plan_path: Option<String>,
    tool_call_id: Option<String>,
    tool_args: Option<serde_json::Value>,
) -> Self {
    Self {
        resume_context: ResumeContext::IncidentPlannerQuestion {
            question,
            options,
            context,
            analysis_text,
            revision_round,
            is_review,
            plan_content,
            plan_path,
        },
        tool_call_id,
        tool_args,
    }
}

/// Create an incident execution confirmation interrupt (y/n to start execution)
pub fn incident_execution_confirmation(
    context: IncidentContext,
    plan_content: String,
    plan_path: String,
) -> Self {
    Self {
        resume_context: ResumeContext::IncidentExecutionConfirmation {
            context,
            plan_content,
            plan_path,
        },
        tool_call_id: None,
        tool_args: None,
    }
}

/// Create an incident plan command interrupt (operator approves remediation command)
#[expect(
    clippy::too_many_arguments,
    reason = "All fields required for plan execution context"
)]
pub fn incident_plan_command(
    command: String,
    motivation: String,
    needs_continuation: bool,
    risk_level: RiskLevel,
    expected_diagnostic_value: String,
    plan_content: String,
    plan_path: String,
    tool_call_id: Option<String>,
    tool_args: Option<serde_json::Value>,
) -> Self {
    Self {
        resume_context: ResumeContext::IncidentPlanCommand {
            command,
            motivation,
            needs_continuation,
            risk_level,
            expected_diagnostic_value,
            plan_content,
            plan_path,
        },
        tool_call_id,
        tool_args,
    }
}

/// Create an incident executor question interrupt (e.g., rollback/skip/abort)
pub fn incident_executor_question(
    question: String,
    options: Option<Vec<String>>,
    plan_content: String,
    plan_path: String,
    tool_call_id: Option<String>,
    tool_args: Option<serde_json::Value>,
) -> Self {
    Self {
        resume_context: ResumeContext::IncidentExecutorQuestion {
            question,
            options,
            plan_content,
            plan_path,
        },
        tool_call_id,
        tool_args,
    }
}
```

- [ ] **Step 3: Add unit tests for new constructors**

Add to the existing `#[cfg(test)] mod tests` block:

```rust
#[test]
fn test_pending_interrupt_plan_confirmation() {
    let ctx = IncidentContext::new("test incident");
    let interrupt = PendingInterrupt::incident_plan_confirmation(
        ctx,
        "analysis text".to_string(),
        ".infraware/incidents/test.md".to_string(),
    );
    match interrupt.resume_context {
        ResumeContext::IncidentPlanConfirmation { report_path, .. } => {
            assert_eq!(report_path, ".infraware/incidents/test.md");
        }
        _ => panic!("Expected IncidentPlanConfirmation"),
    }
}

#[test]
fn test_pending_interrupt_planner_question() {
    let ctx = IncidentContext::new("test incident");
    let interrupt = PendingInterrupt::incident_planner_question(
        "Which approach?".to_string(),
        Some(vec!["A".to_string(), "B".to_string()]),
        ctx,
        "analysis".to_string(),
        0,
        false, // is_review
        None,  // plan_content
        None,  // plan_path
        None,
        None,
    );
    match interrupt.resume_context {
        ResumeContext::IncidentPlannerQuestion { question, revision_round, is_review, .. } => {
            assert_eq!(question, "Which approach?");
            assert_eq!(revision_round, 0);
            assert!(!is_review);
        }
        _ => panic!("Expected IncidentPlannerQuestion"),
    }
}

#[test]
fn test_pending_interrupt_execution_confirmation() {
    let ctx = IncidentContext::new("test incident");
    let interrupt = PendingInterrupt::incident_execution_confirmation(
        ctx,
        "# Plan\n1. Fix config".to_string(),
        ".infraware/plans/test.md".to_string(),
    );
    match interrupt.resume_context {
        ResumeContext::IncidentExecutionConfirmation { plan_path, .. } => {
            assert_eq!(plan_path, ".infraware/plans/test.md");
        }
        _ => panic!("Expected IncidentExecutionConfirmation"),
    }
}

#[test]
fn test_pending_interrupt_plan_command() {
    let interrupt = PendingInterrupt::incident_plan_command(
        "systemctl restart nginx".to_string(),
        "Restart nginx after config fix".to_string(),
        true,
        RiskLevel::Medium,
        "Service should come back up".to_string(),
        "# Plan content".to_string(),
        ".infraware/plans/test.md".to_string(),
        None,
        None,
    );
    match interrupt.resume_context {
        ResumeContext::IncidentPlanCommand { command, risk_level, .. } => {
            assert_eq!(command, "systemctl restart nginx");
            assert_eq!(risk_level, RiskLevel::Medium);
        }
        _ => panic!("Expected IncidentPlanCommand"),
    }
}

#[test]
fn test_pending_interrupt_executor_question() {
    let interrupt = PendingInterrupt::incident_executor_question(
        "Step failed. What to do?".to_string(),
        Some(vec!["Rollback".to_string(), "Skip".to_string(), "Abort".to_string()]),
        "# Plan".to_string(),
        ".infraware/plans/test.md".to_string(),
        None,
        None,
    );
    match interrupt.resume_context {
        ResumeContext::IncidentExecutorQuestion { question, options, .. } => {
            assert_eq!(question, "Step failed. What to do?");
            assert_eq!(options.unwrap().len(), 3);
        }
        _ => panic!("Expected IncidentExecutorQuestion"),
    }
}
```

- [ ] **Step 4: Run tests**

Run: `cargo test --lib agent::adapters::rig::state`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/agent/adapters/rig/state.rs
git commit -m "feat(incident): add ResumeContext variants for plan and execute phases"
```

### Task 3: Add SavePlanTool

**Files:**
- Modify: `src/agent/adapters/rig/incident/agents.rs`

- [ ] **Step 1: Write tests for SavePlanTool**

Add to the existing `#[cfg(test)] mod tests` block in `agents.rs`:

```rust
#[test]
fn test_save_plan_tool_name() {
    assert_eq!(SavePlanTool::NAME, "save_remediation_plan");
}

#[tokio::test]
async fn test_save_plan_tool_definition() {
    let tool = SavePlanTool;
    let def = tool.definition(String::new()).await;
    assert_eq!(def.name, "save_remediation_plan");
    assert!(def.parameters.is_object());
}

#[tokio::test]
async fn test_save_plan_writes_file() {
    use std::fs;

    let tool = SavePlanTool;
    let args = SavePlanArgs {
        slug: "test-plan".to_string(),
        content: "# Remediation Plan\n\n1. Fix config".to_string(),
    };

    let result = tool.call(args).await.unwrap();
    assert!(result.saved);
    assert!(result.path.contains("test-plan"));
    assert!(result.path.contains(".infraware/plans/"));
    assert!(result.path.ends_with(".md"));

    // Cleanup
    let _ = fs::remove_file(&result.path);
}

#[tokio::test]
async fn test_save_plan_rejects_empty_slug() {
    let tool = SavePlanTool;
    let args = SavePlanArgs {
        slug: "../../..".to_string(),
        content: "# Plan".to_string(),
    };

    let result = tool.call(args).await;
    assert!(result.is_err(), "Slug with only path-traversal chars should fail");
}

#[tokio::test]
async fn test_save_plan_sanitizes_slug() {
    use std::fs;

    let tool = SavePlanTool;
    let args = SavePlanArgs {
        slug: "../../my-plan/../../hack".to_string(),
        content: "# Plan".to_string(),
    };

    let result = tool.call(args).await.unwrap();
    assert!(result.saved);
    assert!(!result.path.contains(".."), "Path should not contain traversal: {}", result.path);
    assert!(result.path.contains("my-planhack"));

    // Cleanup
    let _ = fs::remove_file(&result.path);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cargo test --lib agent::adapters::rig::incident::agents::tests::test_save_plan`
Expected: FAIL — `SavePlanTool` not defined

- [ ] **Step 3: Implement SavePlanTool**

Add after the existing `SaveReportTool` implementation in `agents.rs`, following the same structure:

```rust
// ---------------------------------------------------------------------------
// SavePlanTool
// ---------------------------------------------------------------------------

/// Arguments the LLM supplies when saving the remediation plan.
#[derive(Debug, Deserialize, Serialize, JsonSchema)]
pub struct SavePlanArgs {
    /// Filename slug (e.g. "nginx-config-fix") — will be combined with date.
    pub slug: String,
    /// Full Markdown content of the remediation plan.
    pub content: String,
}

/// Result returned after the plan is written.
#[derive(Debug, Serialize)]
pub struct SavePlanResult {
    /// Whether the file was saved successfully.
    pub saved: bool,
    /// Absolute path of the saved file.
    pub path: String,
    /// Human-readable message.
    pub message: String,
}

/// Error type for the plan-save tool.
#[derive(Debug, thiserror::Error)]
pub enum SavePlanError {
    #[error("Failed to write plan: {0}")]
    Io(String),
}

/// Rig Tool that writes the remediation plan Markdown to `.infraware/plans/`.
#[derive(Debug, Clone, Default)]
pub struct SavePlanTool;

impl Tool for SavePlanTool {
    const NAME: &'static str = "save_remediation_plan";

    type Error = SavePlanError;
    type Args = SavePlanArgs;
    type Output = SavePlanResult;

    #[expect(
        clippy::manual_async_fn,
        reason = "rig-rs Tool trait requires impl Future return type"
    )]
    fn definition(&self, _prompt: String) -> impl Future<Output = ToolDefinition> + Send + Sync {
        async {
            ToolDefinition {
                name: Self::NAME.to_string(),
                description: "Save the completed remediation plan as a Markdown file under \
                    .infraware/plans/. Call this exactly once when the plan is ready. \
                    Provide a short slug (e.g. 'nginx-config-fix') and the full Markdown content."
                    .to_string(),
                parameters: serde_json::to_value(schema_for!(SavePlanArgs))
                    .expect("Failed to generate JSON schema for SavePlanArgs"),
            }
        }
    }

    #[expect(
        clippy::manual_async_fn,
        reason = "rig-rs Tool trait requires impl Future return type"
    )]
    fn call(
        &self,
        args: Self::Args,
    ) -> impl Future<Output = Result<Self::Output, Self::Error>> + Send {
        async move {
            use tokio::fs;

            let today = chrono::Utc::now().format("%Y-%m-%d");
            let sanitized_slug: String = args
                .slug
                .trim()
                .replace(' ', "-")
                .chars()
                .filter(|c| c.is_alphanumeric() || *c == '-' || *c == '_')
                .collect();
            if sanitized_slug.is_empty() {
                return Err(SavePlanError::Io(
                    "slug is empty after sanitization".to_string(),
                ));
            }
            let filename = format!("{today}-{sanitized_slug}.md");
            let dir = ".infraware/plans";

            fs::create_dir_all(dir)
                .await
                .map_err(|e| SavePlanError::Io(e.to_string()))?;

            let path = format!("{dir}/{filename}");
            fs::write(&path, &args.content)
                .await
                .map_err(|e| SavePlanError::Io(e.to_string()))?;

            Ok(SavePlanResult {
                saved: true,
                path: path.clone(),
                message: format!("Remediation plan saved to {path}"),
            })
        }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cargo test --lib agent::adapters::rig::incident::agents`
Expected: All tests pass (old + new)

- [ ] **Step 5: Commit**

```bash
git add src/agent/adapters/rig/incident/agents.rs
git commit -m "feat(incident): add SavePlanTool for remediation plans"
```

### Task 4: Add PlannerAgent and ExecutorAgent builders + prompts

**Files:**
- Modify: `src/agent/adapters/rig/incident/agents.rs`

- [ ] **Step 1: Add PLANNER_PROMPT constant**

Add after the existing `REPORTER_PROMPT` constant:

```rust
const PLANNER_PROMPT: &str = "\
You are a senior SRE creating a remediation plan for a production incident.

## Your Mission
Based on the root-cause analysis, create a detailed, step-by-step remediation plan \
that an operator can follow to fix the issue. The plan must be safe, reversible where \
possible, and include verification steps.

## Plan Format
Write a Markdown document with this structure:

# Remediation Plan: <incident title>

**Date:** YYYY-MM-DD
**Risk Level:** Low / Medium / High (overall)

## Prerequisites
- List any prerequisites (backups, maintenance windows, etc.)

## Steps

### Step 1: <description>
- **Command:** `<exact shell command>`
- **Risk:** Low / Medium / High
- **Expected outcome:** <what should happen>
- **Rollback:** `<command to undo this step>`

### Step 2: ...
(continue for all steps)

## Verification

### Verify 1: <what to verify>
- **Command:** `<verification command>`
- **Expected outcome:** <success criteria>

## Guidelines
- Ask the operator clarifying questions using `ask_user` before finalizing the plan. \
For example, ask about maintenance windows, backup preferences, or which approach \
they prefer when multiple options exist.
- Order steps from least risky to most risky when possible.
- Always include rollback commands for medium and high risk steps.
- The final steps MUST be verification commands that confirm the fix is working.
- Prefer read-only verification (curl, status checks) over mutations.
- Save the plan using `save_remediation_plan` when complete.
";

const EXECUTOR_PROMPT: &str = "\
You are a senior SRE executing a remediation plan for a production incident.

## Your Mission
Execute the remediation plan step by step. For each step, use \
`execute_diagnostic_command` to run the command. Follow the plan order exactly.

## Rules
- Execute ONE step at a time using `execute_diagnostic_command`.
- After each command output, assess whether the step succeeded or failed.
- If a step succeeds, move to the next step.
- If a step fails, use `ask_user` to ask the operator whether to:
  1. Execute the rollback command and retry
  2. Skip this step and continue
  3. Abort the plan execution
- Set `needs_continuation=true` for every command so you can assess the output.
- Set appropriate `risk_level` and `motivation` matching the plan step.
- After executing all steps (including verification), provide a summary of:
  - Steps executed successfully
  - Steps that failed and what action was taken
  - Verification results
  - Overall status (fully resolved / partially resolved / failed)

## Important
- Do NOT skip verification steps.
- Do NOT reorder steps unless a previous step failed and the operator chose to skip.
- Do NOT invent commands not in the plan. Follow the plan exactly.
- When all steps are complete, respond with your summary text (do NOT call any tool).
";
```

- [ ] **Step 2: Add `build_planner` function**

Add after `build_reporter`:

```rust
/// Build the `PlannerAgent`.
///
/// Equipped with `AskUserTool` for clarifying questions and `SavePlanTool`
/// to persist the remediation plan. Memory tools are also included.
pub fn build_planner(
    client: &anthropic::Client,
    config: &RigAgentConfig,
    context: &IncidentContext,
    analysis_text: &str,
    memory_ctx: &MemoryContext,
    preambles: &Preambles,
) -> RigAgent {
    let system_prompt = format!(
        "{}\n\n## Incident Context\n\n{}\n\n## Analysis\n\n{}",
        PLANNER_PROMPT,
        context.to_prompt_json(),
        analysis_text
    );

    client
        .agent(&config.model)
        .preamble(&system_prompt)
        .append_preamble(&preambles.memory)
        .append_preamble(&preambles.session)
        .max_tokens(config.max_tokens as u64)
        .temperature(f64::from(config.temperature))
        .tool(AskUserTool::new())
        .tool(SavePlanTool)
        .tool(SaveMemoryTool::new(Arc::clone(&memory_ctx.memory_store)))
        .tool(SaveSessionContextTool::new(Arc::clone(
            &memory_ctx.session_context_store,
        )))
        .build()
}

/// Build the `ExecutorAgent`.
///
/// Equipped with `DiagnosticCommandTool` for executing plan commands (HITL on each)
/// and `AskUserTool` for failure-handling decisions. Memory tools are also included.
pub fn build_executor(
    client: &anthropic::Client,
    config: &RigAgentConfig,
    plan_content: &str,
    memory_ctx: &MemoryContext,
    preambles: &Preambles,
) -> RigAgent {
    let system_prompt = format!(
        "{}\n\n## Remediation Plan\n\n{}",
        EXECUTOR_PROMPT,
        plan_content
    );

    client
        .agent(&config.model)
        .preamble(&system_prompt)
        .append_preamble(&preambles.memory)
        .append_preamble(&preambles.session)
        .max_tokens(config.max_tokens as u64)
        .temperature(f64::from(config.temperature))
        .tool(DiagnosticCommandTool)
        .tool(AskUserTool::new())
        .tool(SaveMemoryTool::new(Arc::clone(&memory_ctx.memory_store)))
        .tool(SaveSessionContextTool::new(Arc::clone(
            &memory_ctx.session_context_store,
        )))
        .build()
}
```

- [ ] **Step 3: Add tests for new prompts and builders**

```rust
#[test]
fn test_planner_prompt_mentions_key_tools() {
    assert!(PLANNER_PROMPT.contains("ask_user"));
    assert!(PLANNER_PROMPT.contains("save_remediation_plan"));
}

#[test]
fn test_executor_prompt_mentions_key_tools() {
    assert!(EXECUTOR_PROMPT.contains("execute_diagnostic_command"));
    assert!(EXECUTOR_PROMPT.contains("ask_user"));
}

#[test]
fn test_planner_prompt_mentions_verification() {
    assert!(PLANNER_PROMPT.contains("verification"));
    assert!(PLANNER_PROMPT.contains("Verification"));
}

#[test]
fn test_executor_prompt_mentions_rollback() {
    assert!(EXECUTOR_PROMPT.contains("rollback"));
    assert!(EXECUTOR_PROMPT.contains("Abort"));
}
```

- [ ] **Step 4: Run tests**

Run: `cargo test --lib agent::adapters::rig::incident::agents`
Expected: All tests pass

- [ ] **Step 5: Run clippy**

Run: `cargo clippy --all-targets --all-features -- -D warnings`
Expected: No warnings

- [ ] **Step 6: Commit**

```bash
git add src/agent/adapters/rig/incident/agents.rs
git commit -m "feat(incident): add PlannerAgent and ExecutorAgent builders"
```

## Chunk 2: Pipeline Orchestration — Planning Phase

### Task 5: Add planning entry points to `incident.rs`

**Files:**
- Modify: `src/agent/adapters/rig/incident.rs`

- [ ] **Step 1: Add constants and imports**

Add at the top of `incident.rs`, alongside existing imports and constants:

```rust
/// Safety guard to avoid endless plan revision loops.
const MAX_PLAN_REVISIONS: usize = 10;
```

- [ ] **Step 2: Add `start_planning` function**

Add as a new public function after `resume_investigation_question`:

```rust
/// Start the planning phase (Phase 4: Planning).
///
/// Called by `create_resume_stream` when the operator confirms plan creation
/// at the `IncidentPlanConfirmation` gate.
pub fn start_planning(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    context: IncidentContext,
    analysis_text: String,
    run_id: String,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        yield Ok(AgentEvent::phase(IncidentPhase::Planning));

        let prompt = "Create a detailed remediation plan based on the incident analysis. \
                      Start by asking the operator any clarifying questions you need, \
                      then write and save the plan.";

        let events = run_planning_step(
            Arc::clone(&client),
            Arc::clone(&config),
            Arc::clone(&state),
            thread_id.clone(),
            context,
            analysis_text,
            prompt.to_string(),
            0, // revision_round
            run_id.clone(),
            memory_ctx.clone(),
        );

        for await event in events {
            yield event;
        }
    })
}
```

- [ ] **Step 3: Add `resume_planning_question` function**

```rust
/// Resume planning after the operator answered a planner question.
///
/// Called by `create_resume_stream` when the operator answers an
/// `IncidentPlannerQuestion` interrupt.
#[expect(
    clippy::too_many_arguments,
    reason = "All fields restored from stored interrupt context"
)]
pub fn resume_planning_question(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    question: String,
    answer: String,
    context: IncidentContext,
    analysis_text: String,
    revision_round: usize,
    run_id: String,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        let prompt = format!(
            "You asked the operator: \"{}\"\n\
             The operator answered: \"{}\"\n\n\
             Continue creating the remediation plan based on this information. \
             If you need more clarification, use ask_user. \
             When the plan is ready, save it using save_remediation_plan.",
            question, answer
        );

        let events = run_planning_step(
            Arc::clone(&client),
            Arc::clone(&config),
            Arc::clone(&state),
            thread_id.clone(),
            context,
            analysis_text,
            prompt,
            revision_round,
            run_id.clone(),
            memory_ctx.clone(),
        );

        for await event in events {
            yield event;
        }
    })
}
```

- [ ] **Step 4: Add `run_planning_step` internal helper**

```rust
/// Run a single planning turn with the PlannerAgent.
///
/// If the agent calls `ask_user`, intercepts it and stores an
/// `IncidentPlannerQuestion` interrupt, then returns.
/// If the agent calls `save_remediation_plan`, it executes (not intercepted),
/// then chains to the review loop.
/// If the agent returns text without a tool call, it means the plan was saved
/// and we proceed to the review loop.
#[expect(
    clippy::too_many_arguments,
    reason = "All fields required to drive planner agent + state + memory"
)]
fn run_planning_step(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    context: IncidentContext,
    analysis_text: String,
    prompt: String,
    revision_round: usize,
    run_id: String,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        let (tx, mut rx) = mpsc::unbounded_channel::<InterceptedToolCall>();
        let hook = HitlHook { tool_call_tx: tx };

        let preambles = memory_ctx.build_preambles().await;
        let agent = agents::build_planner(
            &client, &config, &context, &analysis_text, &memory_ctx, &preambles,
        );

        tracing::info!(
            thread_id = %thread_id,
            run_id = %run_id,
            revision_round,
            "Running PlannerAgent turn"
        );

        let result = agent
            .prompt(&prompt)
            .max_turns(3) // Allow save_remediation_plan tool to execute
            .with_hook(hook)
            .await;

        // Check if ask_user was intercepted
        if let Ok(intercepted) = rx.try_recv() {
            if intercepted.tool_name == "ask_user" {
                if let Ok(args) = serde_json::from_str::<AskUserArgs>(&intercepted.args) {
                    let pending = PendingInterrupt::incident_planner_question(
                        args.question.clone(),
                        args.options.clone(),
                        context,
                        analysis_text,
                        revision_round,
                        false, // is_review (scoping question from PlannerAgent)
                        None,  // plan_content
                        None,  // plan_path
                        intercepted.tool_call_id,
                        serde_json::from_str(&intercepted.args).ok(),
                    );
                    let _ = state.store_interrupt(&thread_id, pending).await;

                    yield Ok(AgentEvent::updates_with_interrupt(
                        HitlMarker::Question {
                            question: args.question,
                            options: args.options,
                        }
                        .into(),
                    ));
                    return;
                }
            }
            tracing::warn!(
                tool = %intercepted.tool_name,
                "Unexpected tool intercepted in planner"
            );
        }

        // No tool intercepted — plan should have been saved
        match result {
            Ok(response) => {
                tracing::info!(run_id = %run_id, "PlannerAgent finished");

                // Extract plan path from response
                let plan_path = response
                    .lines()
                    .find(|l| l.contains(".infraware/plans/"))
                    .map(|l| {
                        l.trim()
                            .trim_start_matches("Remediation plan saved to ")
                            .trim()
                            .to_string()
                    })
                    .unwrap_or_default();

                if plan_path.is_empty() {
                    tracing::error!(run_id = %run_id, "PlannerAgent did not return plan path");
                    yield Err(AgentError::Other(anyhow::anyhow!(
                        "Planner did not save the plan"
                    )));
                    return;
                }

                // Read the plan from disk for the review loop
                match tokio::fs::read_to_string(&plan_path).await {
                    Ok(plan_content) => {
                        for await event in start_plan_review(
                            Arc::clone(&client),
                            Arc::clone(&config),
                            Arc::clone(&state),
                            thread_id.clone(),
                            context,
                            plan_content,
                            plan_path,
                            analysis_text,
                            revision_round,
                            run_id.clone(),
                            memory_ctx.clone(),
                        ) {
                            yield event;
                        }
                    }
                    Err(e) => {
                        tracing::error!(run_id = %run_id, error = ?e, "Failed to read plan file");
                        yield Err(AgentError::Other(anyhow::anyhow!(
                            "Failed to read plan: {}", e
                        )));
                    }
                }
            }
            Err(e) => {
                tracing::error!(run_id = %run_id, error = ?e, "PlannerAgent failed");
                yield Err(AgentError::Other(anyhow::anyhow!("Planner error: {}", e)));
            }
        }
    })
}
```

- [ ] **Step 5: Add `start_plan_review` function**

```rust
/// Show the plan to the operator and ask for changes.
///
/// Part of the review loop: shows plan content, asks if changes are needed.
/// If yes, re-runs the PlannerAgent with feedback. If no, proceeds to
/// execution confirmation.
#[expect(
    clippy::too_many_arguments,
    reason = "All fields required for review loop context"
)]
pub fn start_plan_review(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    context: IncidentContext,
    plan_content: String,
    plan_path: String,
    analysis_text: String,
    revision_round: usize,
    run_id: String,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        // Show plan content to operator
        let plan_message = format!(
            "**Remediation plan saved to `{}`:**\n\n{}",
            plan_path, plan_content
        );
        yield Ok(AgentEvent::Message(MessageEvent::assistant(&plan_message)));

        if revision_round >= MAX_PLAN_REVISIONS {
            tracing::warn!(
                run_id = %run_id,
                revision_round,
                "Max plan revisions reached, proceeding to execution confirmation"
            );
            yield Ok(AgentEvent::Message(MessageEvent::assistant(
                "Maximum revision rounds reached. Proceeding to execution confirmation."
            )));
        }

        // Ask if changes are needed
        let question = if revision_round >= MAX_PLAN_REVISIONS {
            "Do you want to execute this plan?".to_string()
        } else {
            "Would you like to change anything in the plan?".to_string()
        };

        let options = if revision_round >= MAX_PLAN_REVISIONS {
            vec!["Yes, execute the plan".to_string(), "No, skip execution".to_string()]
        } else {
            vec!["Yes, I want changes".to_string(), "No, proceed to execution".to_string()]
        };

        if revision_round >= MAX_PLAN_REVISIONS {
            // Max revisions — go directly to execution confirmation
            let pending = PendingInterrupt::incident_execution_confirmation(
                context,
                plan_content,
                plan_path,
            );
            let _ = state.store_interrupt(&thread_id, pending).await;

            yield Ok(AgentEvent::updates_with_interrupt(
                HitlMarker::Question {
                    question,
                    options: Some(options),
                }
                .into(),
            ));
        } else {
            // Normal review — ask for changes (carry plan content for the orchestrator)
            let pending = PendingInterrupt::incident_planner_question(
                question.clone(),
                Some(options.clone()),
                context,
                analysis_text,
                revision_round,
                true, // is_review
                Some(plan_content),
                Some(plan_path),
                None,
                None,
            );
            let _ = state.store_interrupt(&thread_id, pending).await;

            yield Ok(AgentEvent::updates_with_interrupt(
                HitlMarker::Question {
                    question,
                    options: Some(options),
                }
                .into(),
            ));
        }
    })
}
```

- [ ] **Step 6: Run clippy and format**

Run: `cargo +nightly fmt --all && cargo clippy --all-targets --all-features -- -D warnings`
Expected: No errors or warnings

- [ ] **Step 7: Commit**

```bash
git add src/agent/adapters/rig/incident.rs
git commit -m "feat(incident): add planning phase entry points and review loop"
```

## Chunk 3: Pipeline Orchestration — Execution Phase

### Task 6: Add execution entry points to `incident.rs`

**Files:**
- Modify: `src/agent/adapters/rig/incident.rs`

- [ ] **Step 1: Add `start_execution` function**

```rust
/// Start the execution phase (Phase 5: Executing).
///
/// Called by `create_resume_stream` when the operator confirms plan execution
/// at the `IncidentExecutionConfirmation` gate.
pub fn start_execution(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    plan_content: String,
    plan_path: String,
    run_id: String,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        yield Ok(AgentEvent::phase(IncidentPhase::Executing));

        let prompt = "Execute the remediation plan step by step. Start with step 1.";

        let events = run_execution_step(
            Arc::clone(&client),
            Arc::clone(&config),
            Arc::clone(&state),
            thread_id.clone(),
            plan_content,
            plan_path,
            prompt.to_string(),
            run_id.clone(),
            memory_ctx.clone(),
        );

        for await event in events {
            yield event;
        }
    })
}
```

- [ ] **Step 2: Add `resume_execution_command` function**

```rust
/// Resume execution after a remediation command was approved and executed.
///
/// Called by `create_resume_stream` when the operator approves an
/// `IncidentPlanCommand` interrupt.
#[expect(
    clippy::too_many_arguments,
    reason = "All fields restored from stored interrupt context"
)]
pub fn resume_execution_command(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    command: String,
    motivation: String,
    needs_continuation: bool,
    plan_content: String,
    plan_path: String,
    run_id: String,
    timeout_secs: u64,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        let raw = super::shell::spawn_command(&command, timeout_secs).await;
        let output = if raw.trim().is_empty() {
            "(no output — command produced no stdout/stderr)".to_string()
        } else {
            raw
        };

        let output_block = format!("```\n$ {}\n{}\n```", command, output.trim());
        yield Ok(AgentEvent::Message(MessageEvent::assistant(&output_block)));

        if !needs_continuation {
            yield Ok(AgentEvent::end());
            return;
        }

        let prompt = format!(
            "You are executing a remediation plan.\n\n\
             The command `{}` (motivation: {}) produced this output:\n{}\n\n\
             Assess whether this step succeeded. If it did, continue to the next step. \
             If it failed, use ask_user to ask the operator what to do.",
            command, motivation, output.trim()
        );

        let events = run_execution_step(
            Arc::clone(&client),
            Arc::clone(&config),
            Arc::clone(&state),
            thread_id.clone(),
            plan_content,
            plan_path,
            prompt,
            run_id.clone(),
            memory_ctx.clone(),
        );

        for await event in events {
            yield event;
        }
    })
}
```

- [ ] **Step 3: Add `resume_execution_with_output` function**

```rust
/// Resume execution with pre-provided command output from the terminal PTY.
///
/// Identical to `resume_execution_command` but skips `spawn_command`.
#[expect(
    clippy::too_many_arguments,
    reason = "All fields restored from stored interrupt context"
)]
pub fn resume_execution_with_output(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    command: String,
    motivation: String,
    needs_continuation: bool,
    plan_content: String,
    plan_path: String,
    run_id: String,
    output: String,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        let output = if output.trim().is_empty() {
            "(no output — command produced no stdout/stderr)".to_string()
        } else {
            output
        };

        let output_block = format!("```\n$ {}\n{}\n```", command, output.trim());
        yield Ok(AgentEvent::Message(MessageEvent::assistant(&output_block)));

        if !needs_continuation {
            yield Ok(AgentEvent::end());
            return;
        }

        let prompt = format!(
            "You are executing a remediation plan.\n\n\
             The command `{}` (motivation: {}) produced this output:\n{}\n\n\
             Assess whether this step succeeded. If it did, continue to the next step. \
             If it failed, use ask_user to ask the operator what to do.",
            command, motivation, output.trim()
        );

        let events = run_execution_step(
            Arc::clone(&client),
            Arc::clone(&config),
            Arc::clone(&state),
            thread_id.clone(),
            plan_content,
            plan_path,
            prompt,
            run_id.clone(),
            memory_ctx.clone(),
        );

        for await event in events {
            yield event;
        }
    })
}
```

- [ ] **Step 4: Add `resume_execution_question` function**

```rust
/// Resume execution after the operator answered a question (e.g., rollback/skip/abort).
///
/// Called by `create_resume_stream` when the operator answers an
/// `IncidentExecutorQuestion` interrupt.
#[expect(
    clippy::too_many_arguments,
    reason = "All fields restored from stored interrupt context"
)]
pub fn resume_execution_question(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    question: String,
    answer: String,
    plan_content: String,
    plan_path: String,
    run_id: String,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        let prompt = format!(
            "You are executing a remediation plan.\n\n\
             You asked the operator: \"{}\"\n\
             The operator answered: \"{}\"\n\n\
             Continue executing the plan based on this response.",
            question, answer
        );

        let events = run_execution_step(
            Arc::clone(&client),
            Arc::clone(&config),
            Arc::clone(&state),
            thread_id.clone(),
            plan_content,
            plan_path,
            prompt,
            run_id.clone(),
            memory_ctx.clone(),
        );

        for await event in events {
            yield event;
        }
    })
}
```

- [ ] **Step 5: Add `run_execution_step` internal helper**

```rust
/// Run a single execution turn with the ExecutorAgent.
///
/// If the agent calls `execute_diagnostic_command`, intercepts it and stores
/// an `IncidentPlanCommand` interrupt, then returns.
/// If the agent calls `ask_user`, intercepts it and stores an
/// `IncidentExecutorQuestion` interrupt, then returns.
/// If the agent returns text (no tool call), execution is complete.
#[expect(
    clippy::too_many_arguments,
    reason = "All fields required to drive executor agent + state + memory"
)]
fn run_execution_step(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    plan_content: String,
    plan_path: String,
    prompt: String,
    run_id: String,
    memory_ctx: MemoryContext,
) -> EventStream {
    Box::pin(stream! {
        let (tx, mut rx) = mpsc::unbounded_channel::<InterceptedToolCall>();
        let hook = HitlHook { tool_call_tx: tx };

        let preambles = memory_ctx.build_preambles().await;
        let agent = agents::build_executor(
            &client, &config, &plan_content, &memory_ctx, &preambles,
        );

        tracing::info!(
            thread_id = %thread_id,
            run_id = %run_id,
            "Running ExecutorAgent turn"
        );

        let result = agent
            .prompt(&prompt)
            .max_turns(1)
            .with_hook(hook)
            .await;

        // Check if a tool call was intercepted
        if let Ok(intercepted) = rx.try_recv() {
            match intercepted.tool_name.as_str() {
                "execute_diagnostic_command" => {
                    if let Ok(args) = serde_json::from_str::<DiagnosticCommandArgs>(
                        &intercepted.args,
                    ) {
                        let hitl_message = format_hitl_message(&args);
                        let pending = PendingInterrupt::incident_plan_command(
                            args.command.clone(),
                            args.motivation.clone(),
                            args.needs_continuation,
                            args.risk_level,
                            args.expected_diagnostic_value.clone(),
                            plan_content,
                            plan_path,
                            intercepted.tool_call_id,
                            serde_json::from_str(&intercepted.args).ok(),
                        );
                        let _ = state.store_interrupt(&thread_id, pending).await;

                        yield Ok(AgentEvent::updates_with_interrupt(
                            HitlMarker::CommandApproval {
                                command: args.command,
                                message: hitl_message,
                                needs_continuation: args.needs_continuation,
                            }
                            .into(),
                        ));
                        return;
                    }
                }
                "ask_user" => {
                    if let Ok(args) = serde_json::from_str::<AskUserArgs>(&intercepted.args) {
                        let pending = PendingInterrupt::incident_executor_question(
                            args.question.clone(),
                            args.options.clone(),
                            plan_content,
                            plan_path,
                            intercepted.tool_call_id,
                            serde_json::from_str(&intercepted.args).ok(),
                        );
                        let _ = state.store_interrupt(&thread_id, pending).await;

                        yield Ok(AgentEvent::updates_with_interrupt(
                            HitlMarker::Question {
                                question: args.question,
                                options: args.options,
                            }
                            .into(),
                        ));
                        return;
                    }
                }
                _ => {}
            }
            tracing::warn!(
                tool = %intercepted.tool_name,
                "Unexpected tool intercepted in executor"
            );
        }

        // No tool intercepted — execution complete
        match result {
            Ok(summary) => {
                tracing::info!(run_id = %run_id, "ExecutorAgent finished");

                if !summary.trim().is_empty() {
                    yield Ok(AgentEvent::Message(MessageEvent::assistant(&summary)));
                }

                yield Ok(AgentEvent::phase(IncidentPhase::Completed));
                yield Ok(AgentEvent::end());
            }
            Err(e) => {
                tracing::error!(run_id = %run_id, error = ?e, "ExecutorAgent failed");
                yield Err(AgentError::Other(anyhow::anyhow!("Executor error: {}", e)));
            }
        }
    })
}
```

- [ ] **Step 6: Run clippy and format**

Run: `cargo +nightly fmt --all && cargo clippy --all-targets --all-features -- -D warnings`
Expected: No errors or warnings

- [ ] **Step 7: Commit**

```bash
git add src/agent/adapters/rig/incident.rs
git commit -m "feat(incident): add execution phase entry points"
```

## Chunk 4: Wiring — Reporter Transition and Orchestrator Match Arms

### Task 7: Modify `run_analysis_and_report` to chain plan confirmation

**Files:**
- Modify: `src/agent/adapters/rig/incident.rs:487-568` (the `run_analysis_and_report` function)

- [ ] **Step 1: Update the function signature**

Add `state: Arc<StateStore>` and `thread_id: ThreadId` parameters to `run_analysis_and_report` since it now needs to store an interrupt:

```rust
fn run_analysis_and_report(
    client: Arc<anthropic::Client>,
    config: Arc<RigAgentConfig>,
    state: Arc<StateStore>,
    thread_id: crate::agent::shared::ThreadId,
    context: IncidentContext,
    investigation_findings: String,
    run_id: String,
    memory_ctx: MemoryContext,
) -> EventStream {
```

- [ ] **Step 2: Update all call sites of `run_analysis_and_report`**

There are 3 call sites in `run_investigation_step` (lines ~369, ~395, ~468). Pass `Arc::clone(&state)` and `thread_id.clone()` to each.

- [ ] **Step 3: Replace the reporter completion logic**

Replace the block at the end of `run_analysis_and_report` that currently emits `Completed` + `end()` (lines 545-566) with plan confirmation logic:

```rust
match report_result {
    Ok(response) => {
        tracing::info!(run_id = %run_id, "ReporterAgent finished");

        // Extract report path from response
        let report_path = response
            .lines()
            .find(|l| l.contains(".infraware/incidents/"))
            .map(|l| l.trim().to_string())
            .unwrap_or_default();

        if !report_path.is_empty() {
            yield Ok(AgentEvent::Message(MessageEvent::assistant(
                report_path.trim(),
            )));
        }

        // Instead of completing, ask if the user wants to create a plan
        let question = "Would you like to create a remediation plan to fix this issue?".to_string();
        let options = vec![
            "Yes, create plan".to_string(),
            "No, skip".to_string(),
        ];

        let pending = PendingInterrupt::incident_plan_confirmation(
            context,
            analysis_text.clone(),
            report_path,
        );
        let _ = state.store_interrupt(&thread_id, pending).await;

        yield Ok(AgentEvent::updates_with_interrupt(
            HitlMarker::Question {
                question,
                options: Some(options),
            }
            .into(),
        ));
    }
    Err(e) => {
        tracing::error!(run_id = %run_id, error = ?e, "ReporterAgent failed");
        yield Err(AgentError::Other(anyhow::anyhow!("Reporter error: {}", e)));
    }
}
```

- [ ] **Step 4: Run clippy and format**

Run: `cargo +nightly fmt --all && cargo clippy --all-targets --all-features -- -D warnings`
Expected: No errors or warnings

- [ ] **Step 5: Commit**

```bash
git add src/agent/adapters/rig/incident.rs
git commit -m "feat(incident): chain plan confirmation after report phase"
```

### Task 8: Add orchestrator match arms in `create_resume_stream`

**Files:**
- Modify: `src/agent/adapters/rig/orchestrator.rs:571-743` (the match block in `create_resume_stream`)

- [ ] **Step 1: Add match arm for `IncidentPlanConfirmation`**

Add before the final `_ =>` catch-all arm:

```rust
// Operator confirms/rejects creating a remediation plan
(ResumeResponse::Answer { text }, ResumeContext::IncidentPlanConfirmation { context, analysis_text, .. }) => {
    let is_affirmative = classify_user_response(
        &client,
        &config,
        "Would you like to create a remediation plan to fix this issue?",
        &["Yes, create plan", "No, skip"],
        text,
    ).await;
    if !is_affirmative {
        let msg = "Remediation planning skipped.";
        yield Ok(AgentEvent::Message(MessageEvent::assistant(msg)));
        yield Ok(AgentEvent::phase(IncidentPhase::Completed));
        yield Ok(AgentEvent::end());
        return;
    }

    let mut stream = incident::start_planning(
        Arc::clone(&client),
        Arc::clone(&config),
        Arc::clone(&state),
        thread_id.clone(),
        context.clone(),
        analysis_text.clone(),
        run_id.clone(),
        memory_ctx.clone(),
    );

    while let Some(event) = stream.next().await {
        yield event;
    }
}
```

- [ ] **Step 2: Add match arm for `IncidentPlannerQuestion`**

```rust
// Operator answered a planner question or review question
(ResumeResponse::Answer { text }, ResumeContext::IncidentPlannerQuestion { question, context, analysis_text, revision_round, is_review, plan_content, plan_path, .. }) => {
    if *is_review {
        // Review loop: classify whether user wants to proceed or make changes
        // Option 1 = "Yes, I want changes" (affirmative = true = wants changes)
        let wants_changes = classify_user_response(
            &client,
            &config,
            &question,
            &["Yes, I want changes", "No, proceed to execution"],
            text,
        ).await;

        if wants_changes {
            let revision_prompt = format!(
                "The operator reviewed the plan and wants changes:\n\"{}\"\n\n\
                 Revise the plan based on this feedback and save the updated version \
                 using save_remediation_plan.",
                text
            );

            let mut stream = incident::run_planning_step(
                Arc::clone(&client),
                Arc::clone(&config),
                Arc::clone(&state),
                thread_id.clone(),
                context.clone(),
                analysis_text.clone(),
                revision_prompt,
                *revision_round + 1,
                run_id.clone(),
                memory_ctx.clone(),
            );

            while let Some(event) = stream.next().await {
                yield event;
            }
        } else {
            // No changes — proceed to execution confirmation
            // plan_content and plan_path are carried in the IncidentPlannerQuestion
            let pc = plan_content.clone().unwrap_or_default();
            let pp = plan_path.clone().unwrap_or_default();

            let pending = PendingInterrupt::incident_execution_confirmation(
                context.clone(),
                pc,
                pp,
            );
            let _ = state.store_interrupt(&thread_id, pending).await;

            let question = "Do you want to execute this plan?".to_string();
            let options = vec![
                "Yes, execute the plan".to_string(),
                "No, skip execution".to_string(),
            ];
            yield Ok(AgentEvent::updates_with_interrupt(
                HitlMarker::Question {
                    question,
                    options: Some(options),
                }
                .into(),
            ));
        }
    } else {
        // Regular planner question (scoping)
        let mut stream = incident::resume_planning_question(
            Arc::clone(&client),
            Arc::clone(&config),
            Arc::clone(&state),
            thread_id.clone(),
            question.clone(),
            text.clone(),
            context.clone(),
            analysis_text.clone(),
            *revision_round,
            run_id.clone(),
            memory_ctx.clone(),
        );

        while let Some(event) = stream.next().await {
            yield event;
        }
    }
}
```

**Note:** This arm references `run_planning_step` which is currently a private function. It will need to be made `pub(super)` so the orchestrator can call it for the review loop revision flow.

- [ ] **Step 3: Add match arm for `IncidentExecutionConfirmation`**

```rust
// Operator confirms/rejects executing the plan
(ResumeResponse::Answer { text }, ResumeContext::IncidentExecutionConfirmation { context: _, plan_content, plan_path }) => {
    let is_affirmative = classify_user_response(
        &client,
        &config,
        "Do you want to execute this plan?",
        &["Yes, execute the plan", "No, skip execution"],
        text,
    ).await;
    if !is_affirmative {
        let msg = "Plan execution skipped.";
        yield Ok(AgentEvent::Message(MessageEvent::assistant(msg)));
        yield Ok(AgentEvent::phase(IncidentPhase::Completed));
        yield Ok(AgentEvent::end());
        return;
    }

    let mut stream = incident::start_execution(
        Arc::clone(&client),
        Arc::clone(&config),
        Arc::clone(&state),
        thread_id.clone(),
        plan_content.clone(),
        plan_path.clone(),
        run_id.clone(),
        memory_ctx.clone(),
    );

    while let Some(event) = stream.next().await {
        yield event;
    }
}
```

- [ ] **Step 4: Add match arms for `IncidentPlanCommand`**

```rust
// Remediation command executed via terminal PTY
(ResumeResponse::CommandOutput { output, .. }, ResumeContext::IncidentPlanCommand { command, motivation, needs_continuation, plan_content, plan_path, .. }) => {
    let mut stream = incident::resume_execution_with_output(
        Arc::clone(&client),
        Arc::clone(&config),
        Arc::clone(&state),
        thread_id.clone(),
        command.clone(),
        motivation.clone(),
        *needs_continuation,
        plan_content.clone(),
        plan_path.clone(),
        run_id.clone(),
        output.clone(),
        memory_ctx.clone(),
    );

    while let Some(event) = stream.next().await {
        yield event;
    }
}

// Operator rejected a remediation command
(ResumeResponse::Rejected, ResumeContext::IncidentPlanCommand { command, .. }) => {
    let msg = format!("Remediation command `{}` rejected. Plan execution stopped.", command);
    yield Ok(AgentEvent::Message(MessageEvent::assistant(&msg)));
    yield Ok(AgentEvent::end());
}

// Operator rejected plan creation
(ResumeResponse::Rejected, ResumeContext::IncidentPlanConfirmation { .. }) => {
    let msg = "Remediation planning skipped.";
    yield Ok(AgentEvent::Message(MessageEvent::assistant(msg)));
    yield Ok(AgentEvent::phase(IncidentPhase::Completed));
    yield Ok(AgentEvent::end());
}

// Operator rejected plan execution
(ResumeResponse::Rejected, ResumeContext::IncidentExecutionConfirmation { .. }) => {
    let msg = "Plan execution skipped.";
    yield Ok(AgentEvent::Message(MessageEvent::assistant(msg)));
    yield Ok(AgentEvent::phase(IncidentPhase::Completed));
    yield Ok(AgentEvent::end());
}
```

- [ ] **Step 5: Add match arm for `IncidentExecutorQuestion`**

```rust
// Operator answered an executor question (rollback/skip/abort)
(ResumeResponse::Answer { text }, ResumeContext::IncidentExecutorQuestion { question, plan_content, plan_path, .. }) => {
    let mut stream = incident::resume_execution_question(
        Arc::clone(&client),
        Arc::clone(&config),
        Arc::clone(&state),
        thread_id.clone(),
        question.clone(),
        text.clone(),
        plan_content.clone(),
        plan_path.clone(),
        run_id.clone(),
        memory_ctx.clone(),
    );

    while let Some(event) = stream.next().await {
        yield event;
    }
}
```

- [ ] **Step 6: Make `run_planning_step` pub(super) in `incident.rs`**

Change `fn run_planning_step(` to `pub(super) fn run_planning_step(` so the orchestrator can call it for revision flows.

- [ ] **Step 7: Run clippy and format**

Run: `cargo +nightly fmt --all && cargo clippy --all-targets --all-features -- -D warnings`
Expected: No errors or warnings

- [ ] **Step 8: Run full test suite**

Run: `cargo test`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add src/agent/adapters/rig/orchestrator.rs src/agent/adapters/rig/incident.rs
git commit -m "feat(incident): wire plan and execute phases in orchestrator"
```

## Chunk 5: Integration Verification

### Task 9: Full build and test verification

**Files:** None (verification only)

- [ ] **Step 1: Run full build with all features**

Run: `cargo build --all-features`
Expected: Build succeeds

- [ ] **Step 2: Run full test suite**

Run: `cargo test`
Expected: All tests pass

- [ ] **Step 3: Run clippy strict mode**

Run: `cargo clippy --all-targets --all-features -- -D warnings`
Expected: No warnings

- [ ] **Step 4: Run format check**

Run: `cargo +nightly fmt --all --check`
Expected: No formatting issues

- [ ] **Step 5: Verify with mock engine smoke test**

Run: `ENGINE_TYPE=mock cargo run`
Expected: App launches and exits cleanly (Ctrl+C)
