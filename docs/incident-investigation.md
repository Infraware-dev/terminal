# Incident Investigation Pipeline

The incident investigation pipeline is a multi-agent system that helps operators investigate production incidents, create remediation plans, and execute fixes. It combines human-in-the-loop (HITL) approval with structured LLM reasoning across five sequential phases.

## How It Works

The pipeline is triggered when the user describes an incident through the normal agent (e.g., `? investigate: our payments API is returning 502 errors`). The normal agent recognizes this as an incident and calls `start_incident_investigation`, which prompts the operator to confirm before launching the pipeline.

The pipeline runs in five sequential phases, with HITL gates between phases 3-4 and 4-5:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       Incident Investigation Pipeline                       │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                        │
│  │  Phase 1:    │  │  Phase 2:    │  │  Phase 3:    │                        │
│  │ Investigator │─►│   Analyst    │─►│  Reporter    │                        │
│  │   (HITL)     │  │ (pure LLM)  │  │ (save tool)  │                        │
│  └──────────────┘  └──────────────┘  └──────┬───────┘                        │
│        │                                    │                                │
│        │  Operator approves each            │ HITL gate: "Create a plan?"    │
│        │  diagnostic command                ▼                                │
│        ▼                             ┌──────────────┐  ┌──────────────┐      │
│  ┌──────────────┐                    │  Phase 4:    │  │  Phase 5:    │      │
│  │  Terminal    │                    │  Planner     │─►│  Executor    │      │
│  │  (PTY exec) │                    │ (HITL + save)│  │   (HITL)     │      │
│  └──────────────┘                    └──────────────┘  └──────────────┘      │
│                                           │                  │               │
│                                           │ Review loop      │ Operator      │
│                                           │ (up to 10        │ approves each │
│                                           │  revisions)      │ command       │
│                                           ▼                  ▼               │
│                                     HITL gate:         ┌──────────────┐      │
│                                     "Execute plan?"    │  Terminal    │      │
│                                                        │  (PTY exec) │      │
│                                                        └──────────────┘      │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Phases

### Phase 1: Investigation (InvestigatorAgent)

The investigator is a senior SRE agent that follows a structured methodology:

**Scoping (mandatory, before any commands):**
The agent first reviews the incident description and asks the operator scoping questions to understand the environment. Key questions include:

- What software/services are involved?
- What is the infrastructure? (bare metal, VM, containers, cloud)
- When did the issue start? Is it intermittent or constant?
- Were there recent changes or deployments?
- What monitoring/observability is in place?
- What has already been tried?

The agent asks at minimum 2-3 questions before running any diagnostic command, skipping questions already answered by the incident description.

**Diagnosis:**
After scoping, the agent runs diagnostic commands with mandatory first steps:

1. **Service status** -- process status, listening ports, health endpoints
2. **Configuration review** -- reads config files, checks for misconfigurations

Then guided investigation based on what was learned during scoping:

- Error logs (service, application, system)
- Upstream/backend health
- Resource utilization (CPU, memory, disk, connections)
- Network and connectivity (firewall, DNS, TLS)
- Recent changes on disk
- Dependency health (databases, caches, queues)

**Proactive questioning:**
During diagnosis, the agent asks the operator whenever it encounters ambiguity -- multiple config files, unexpected architecture, findings suggesting multiple causes, or access issues.

**HITL approval:**
Every diagnostic command requires operator approval before execution. The approval prompt shows:

```
Motivation: Check nginx upstream configuration
Risk: Low | Expected: Backend server addresses and health check settings
```

**Tools available:**
- `execute_diagnostic_command` -- run shell commands with motivation, risk level, and expected diagnostic value
- `ask_user` -- ask the operator questions

**Safety guards:**
- Maximum 50 diagnostic commands per investigation
- Duplicate command detection -- if the agent requests a command it already ran, the pipeline forces analysis
- Risk levels: Low (read-only), Medium (restarts, config reads), High (mutations, deletions)

### Phase 2: Analysis (AnalystAgent)

A pure LLM agent (no tools) that receives all collected evidence and produces a structured JSON analysis:

```json
{
  "root_cause": "...",
  "impact": "...",
  "affected_services": ["..."],
  "timeline": [{"timestamp": "...", "description": "..."}],
  "fix_plan": ["Step 1: ...", "Step 2: ..."]
}
```

### Phase 3: Reporting (ReporterAgent)

Writes a Markdown post-mortem report and saves it to `.infraware/incidents/<date>-<slug>.md` using the `save_incident_report` tool. The report includes:

- Summary
- Timeline
- Root Cause
- Impact
- Evidence
- Fix Plan
- Lessons Learned

After the report is saved, the pipeline asks the operator whether to create a remediation plan. If declined, the pipeline ends.

### Phase 4: Planning (PlannerAgent)

Creates a structured remediation plan based on the analysis. The planner:

1. **Asks scoping questions** -- clarifies maintenance windows, backup preferences, approach choices
2. **Writes the plan** -- saves to `.infraware/plans/<date>-<slug>.md` using `save_remediation_plan`
3. **Review loop** -- shows the plan and asks if changes are needed (up to 10 revision rounds)
4. **Execution gate** -- asks whether to proceed with execution

**Plan format:**

```markdown
# Remediation Plan: <title>

## Summary
<what this plan does and why>

## Prerequisites
- List any prerequisites (backups, maintenance windows, etc.)

## Steps

### Step 1: <description>
- **Command:** `<exact shell command>`
- **Risk:** Low / Medium / High
- **Expected outcome:** <what should happen>
- **Rollback:** `<command to undo this step>`

### Step 2: ...

## Verification

### Verify 1: <what to verify>
- **Command:** `<verification command>`
- **Expected outcome:** <success criteria>
```

**Tools available:**
- `ask_user` -- ask the operator scoping/review questions
- `save_remediation_plan` -- persist the plan to disk

**Review loop:**
After saving the plan, the agent shows its content and asks if the operator wants changes. If yes, the planner revises and re-saves. This repeats for up to 10 rounds. After 10 rounds, the pipeline proceeds to execution confirmation automatically.

If the operator declines execution, the pipeline ends (the plan is still saved on disk).

### Phase 5: Execution (ExecutorAgent)

Executes the remediation plan step by step with HITL approval on every command. The executor:

1. **Follows the plan** -- executes steps in order using `execute_diagnostic_command`
2. **Assesses results** -- after each command, evaluates whether the step succeeded
3. **Handles failures** -- on failure, asks the operator whether to:
   - Execute the rollback command and retry
   - Skip the step and continue
   - Abort the plan execution
4. **Runs verification** -- executes verification steps at the end
5. **Summarizes** -- provides a final summary of steps executed, failures, and overall status

**Tools available:**
- `execute_diagnostic_command` -- run plan commands (HITL on each)
- `ask_user` -- ask for failure-handling decisions

If the operator rejects a command, plan execution stops immediately.

## State Machine

The pipeline introduces several HITL interrupt states:

```
IncidentConfirmation (y/n to start)
    │
    └──► InvestigatorAgent loop
              │
              ├── IncidentCommand (approve/reject diagnostic command)
              │       │ (approve) ──► execute ──► InvestigatorAgent loop
              │       └── (reject) ──► pipeline ends
              │
              ├── IncidentQuestion (operator answers scoping question)
              │       └──► InvestigatorAgent loop
              │
              └── (text response, no tool) ──► Phase 2 + 3
                    │
                    └──► IncidentPlanConfirmation (y/n to plan)
                              │
                              ├── (no) ──► pipeline ends
                              └── (yes) ──► PlannerAgent loop
                                    │
                                    ├── IncidentPlannerQuestion (scoping)
                                    │       └──► PlannerAgent loop
                                    │
                                    └── (plan saved) ──► Review loop
                                          │
                                          ├── IncidentPlannerQuestion (is_review=true)
                                          │       ├── (wants changes) ──► PlannerAgent revision
                                          │       └── (no changes) ──► IncidentExecutionConfirmation
                                          │
                                          └── IncidentExecutionConfirmation (y/n to execute)
                                                    │
                                                    ├── (no) ──► pipeline ends
                                                    └── (yes) ──► ExecutorAgent loop
                                                          │
                                                          ├── IncidentPlanCommand (approve/reject)
                                                          │       │ (approve) ──► execute ──► ExecutorAgent loop
                                                          │       └── (reject) ──► pipeline ends
                                                          │
                                                          ├── IncidentExecutorQuestion (rollback/skip/abort)
                                                          │       └──► ExecutorAgent loop
                                                          │
                                                          └── (text response) ──► Completed
```

## Usage

Start an investigation through the terminal's natural language interface:

```
? investigate: our web server is returning 502 errors since this morning
```

The agent will:
1. Ask you to confirm the investigation
2. Ask scoping questions about your environment
3. Propose diagnostic commands for your approval
4. Analyze collected evidence
5. Save a post-mortem report to `.infraware/incidents/`
6. Ask if you want to create a remediation plan
7. Ask scoping questions about the fix approach
8. Show the plan for review (you can request changes)
9. Ask if you want to execute the plan
10. Execute each step with your approval

You can decline at any HITL gate (steps 1, 6, 9, or any command approval) to end the pipeline gracefully.

## Output Files

| Directory | Contents |
|-----------|----------|
| `.infraware/incidents/` | Post-mortem reports (`<date>-<slug>.md`) |
| `.infraware/plans/` | Remediation plans (`<date>-<slug>.md`) |

## Files

| File | Purpose |
|------|---------|
| `src/agent/adapters/rig/incident.rs` | Pipeline orchestration, entry points for all 5 phases |
| `src/agent/adapters/rig/incident/agents.rs` | Agent builders, system prompts, `SavePlanTool`, `SaveReportTool` |
| `src/agent/adapters/rig/incident/context.rs` | `IncidentContext`, `CommandResult`, `Finding`, `RiskLevel` data models |
| `src/agent/adapters/rig/orchestrator.rs` | `create_resume_stream` match arms for all HITL resume contexts |
| `src/agent/adapters/rig/state.rs` | `ResumeContext` variants and `PendingInterrupt` constructors |
| `src/agent/shared/events.rs` | `IncidentPhase` enum, `AgentEvent::Phase` variant |
| `src/agent/adapters/rig/tools/diagnostic_command.rs` | `DiagnosticCommandTool` (investigation and execution) |
| `src/agent/adapters/rig/tools/start_incident.rs` | `StartIncidentInvestigationTool` |
| `src/agent/adapters/rig/tools/ask_user.rs` | `AskUserTool` (shared across all agents) |
| `src/app/llm_event_handler.rs` | Phase banner rendering in terminal UI |

## Configuration

The investigation pipeline uses the same configuration as the normal RigEngine agent (see `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `RIG_MAX_TOKENS`, etc.). The memory system is shared across all agents in the pipeline -- facts learned during investigation are available in future sessions.
