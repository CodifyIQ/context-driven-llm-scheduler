# 🧠 context-driven-llm-scheduler

**Context-driven scheduled tasks for LLMs with persistent memory.**

[![PyPI version](https://img.shields.io/pypi/v/context-driven-llm-scheduler.svg)](https://pypi.org/project/context-driven-llm-scheduler/)
[![Python versions](https://img.shields.io/pypi/pyversions/context-driven-llm-scheduler.svg)](https://pypi.org/project/context-driven-llm-scheduler/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

Most scheduled tasks and cron jobs are stateless — they wake up with no memory of prior runs.

**context-driven-llm-scheduler** solves this by giving LLM-powered recurring tasks **persistent context and memory** across executions.

It lets you build reliable, intelligent scheduled agents that remember what they've seen, what they've done, and what still needs attention.

Inspired by the [Heartbeat pattern](https://docs.openclaw.ai/gateway/heartbeat) from OpenClaw.

## What is context-driven-llm-scheduler?

`context-driven-llm-scheduler` is a lightweight Python library for defining and running **memoryful LLM scheduled tasks** (called **pulses**).

You define each pulse in a markdown file (schedule, memory rules, model, and instructions). The library handles the complex parts:

- Recalling relevant memory and context from previous runs
- Assembling token-efficient prompts (with transparent trimming)
- Atomic persistence of the LLM's decisions
- Built-in deduplication (`seen`) and rate-limiting (`throttle`)

You bring your own scheduler, LLM adapter, and storage backend (or use some default options we provide).

## Features

- **Markdown-first configuration** — prompts, schedules, and rules are easy to edit
- **True persistent memory** — notes, seen items, key-value facts, throttles
- **No lock-in** — compatible with cron, APScheduler, Lambda, Airflow, etc.
- **Production-ready** — concurrency-safe, atomic transactions, honest token budgeting
- **Minimal dependencies**

## Quickstart

**1. Create a pulse definition** at `pulses/inbox-triage.md`:

```markdown
---
id: inbox-triage
schedule: "*/15 * * * *"
throttle: { notify: 1h }
keep: { notes: 20, seen: 500 }
model: anthropic/claude-sonnet-4-6
---

You are my inbox triage assistant.

For each new urgent email:
- Decide if it genuinely needs my attention.
- If yes and the `notify` throttle allows, alert me and record the throttle.
- Always mark the email as `seen`.

Be conservative. Never notify about the same thing twice.
```

**2. Wire it up in Python:**
```python
from context_driven_llm_scheduler import PulseManager, FileStore, LiteLLMAdapter

manager = PulseManager.from_dir("pulses", FileStore("./state"))
adapter = LiteLLMAdapter("anthropic/claude-sonnet-4-6")

@manager.pulse("inbox-triage")
def triage(pulse, extra=None):
    prompt = pulse.recall(extra={"emails": fetch_urgent_emails()})
    ops = adapter.propose_memory_ops(prompt)
    return pulse.persist(ops)
```

**3. Trigger the pulse:**
```python
manager.trigger("inbox-triage")   # Call from cron, scheduler, Lambda, etc.
```

## Core Concepts
### The Pulse Interface

#### Pull Data into the LLM Context Before the Scheduled Job
`pulse.recall(...)` — assembles instructions + historical memory + fresh input data

#### Store Data After the Scheduled Job
`pulse.persist(ops)` — atomically applies the LLM's structured memory operations

### Supported Memory Operations
The LLM outputs operations via tool calling:

`note` — free-text observation
`seen` — mark item as handled (deduplication)
`throttle` — record action for rate limiting
`set` / `forget` — key/value persistent facts

### Multi-tenant pulses

If your product runs the **same recurring task for many customers** — one
readiness check per team, one digest per account, one monitor per project — two
things usually get in the way:

1. **Shared memory.** By default a task keeps a single memory. Run it for 50
   teams and they all write to the same notebook, so one team's history
   overwrites another's.
2. **Fixed, file-based setup.** By default a task is defined in a file and
   registered when the app starts. But in a real product each customer's rule
   lives in *your database* and changes over time — you want to run the rule you
   just fetched, right now.

These two capabilities remove both walls:

- **Per-customer isolation** — run one shared task separately for each customer,
  each with its own private memory. You tell the library which customer a run is
  for (`instance=`); it keeps them apart. One customer's run can never see or
  overwrite another's history. Runs with no customer specified behave exactly as
  before.
- **Run a rule on the fly** — take a task description straight from your
  database and run it immediately, with no need to register it ahead of time
  (`trigger_definition(...)`).

Put together: one rule, authored per customer and stored in your database, runs
on its own schedule for each customer with fully separate memory.

```python
from context_driven_llm_scheduler import PulseDefinition

# Each team's rule is a markdown doc stored in your database.
# Build it at call time and run it for that team, with isolated memory.
definition = PulseDefinition.from_markdown(rule_body, default_id="readiness-check")

for team_id in active_teams:
    manager.trigger_definition(definition, readiness_check, instance=team_id)
```

Every `team_id` shares the one `readiness-check` rule but keeps its own memory;
the single `readiness_check` handler never has to deal with a team id itself.
See `examples/multi_tenant_pulses.py`.

## Installation
```bash
pip install context-driven-llm-scheduler
```

### Optional extras:
```bash
pip install "context-driven-llm-scheduler[litellm,sqlite,scheduler]"
```

## Examples
See the `examples/` directory.