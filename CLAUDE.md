# context_driven_llm_scheduler — agent notes

Lightweight, scheduler- and model-agnostic Python library for markdown-defined,
memoryful **pulses** (inspired by OpenClaw's Heartbeat; we use the term
"Pulse"). A pulse is a `pulse.md` — pure-prose body is enough (id defaults to
the filename stem); optional frontmatter (id/schedule/throttle/keep/model)
overrides. The headline value is the **membrane**: `recall()`
reads memory→prompt (memory in, with token budgeting); the model decides;
`persist()` writes the model's **memory protocol** ops back into state (memory
out). The model call is the caller's. Core cycle: `manager.trigger(pulse_id)` →
load context → recall/handler → persist ops → save.

## Layout
- `src/context_driven_llm_scheduler/core/` — `types.py`, `exceptions.py`, `store.py` (ABC),
  `manager.py` (`PulseManager`, `from_dir`/`pulse()`, optional `on_event` +
  `result_log`, `trigger(..., instance=, coalesce_window=)` +
  `trigger_definition(def, handler, ...)` for ad-hoc, unregistered runs),
  `memory.py` (`Memory`, `apply_ops` → changeset, `MEMORY_OPS`,
  `MEMORY_TOOL_SCHEMA`),
  `pulse.py` (`PulseDefinition` w/ filename-id fallback, `Pulse` with
  `recall`/`persist` + `record_result`/`carried_facts`/`carried_notes` +
  caller-driven `compact_prompt`/`compact` + `seconds_until_available`).
- `src/context_driven_llm_scheduler/adapters/` — `base.py` (`ModelAdapter` protocol),
  `litellm_adapter.py` (`LiteLLMAdapter`, `litellm` extra, lazy; Bedrock via a
  `bedrock/...` model string).
- `src/context_driven_llm_scheduler/result_log.py` — `ResultLog` (append-only markdown run
  log, one `<id>.md` per pulse, portalocker) + `render_entry`.
- `src/context_driven_llm_scheduler/stores/` — `file.py` (`FileStore`, portalocker),
  `sqlite.py` (`SQLiteStore`, SQLAlchemy + `BEGIN IMMEDIATE`, `sqlite` extra).
- `src/context_driven_llm_scheduler/schedulers/apscheduler_wrapper.py` — optional, `scheduler` extra.
- `src/context_driven_llm_scheduler/util.py` — `add_to_seen_set`, `check_throttle`,
  `prune_history`, `migrate_context` (the verbs `apply_ops` builds on) + `utcnow`.
- `examples/`, `tests/features/` (Behave).

## Memory protocol
Closed op set the model emits and `apply_ops` applies: `note`, `seen`,
`throttle`, `set`, `forget`. Memory lives under the reserved `"memory"` key of
the context dict (`notes`/`seen`/`throttles`/`facts`). Extend the set
deliberately in `memory.py` (`MEMORY_OPS` + `MEMORY_TOOL_SCHEMA`).

## Conventions
Follow `.claude/rules/python.instructions.md` (type hints everywhere,
Google-style docstrings, absolute imports, ruff @ 120 cols). Tests are **Behave
only** — see `.claude/skills/bdd-test` and `tests/features/`.

## Commands
```bash
uv sync --extra sqlite --extra scheduler --extra dev
uv run ruff check .
uv run behave --tags="not @integration-test"
uv build
```

## Design invariants
- Context is always plain JSON-serializable dict; datetimes stored as ISO strings.
- `trigger()` wraps load→handler→persist→save in `store.transaction(key)` for
  concurrency safety. The manager owns the effective store key: `instance=`
  composes `(pulse_id, instance)` into one partitioned key (`_store_key`,
  separator `::`; it rejects a `pulse_id`/`instance` containing `::` so two
  pairs can't silently collapse onto one key), so one definition runs across
  isolated per-instance state while the store ABC
  and backends stay unchanged (they see one opaque key). `instance=None` is
  byte-for-byte the unpartitioned path; transaction, coalescing, and result-log
  files (`<id>__<instance>.md`) are all per-instance. `trigger_definition()`
  runs a call-time `PulseDefinition` + handler with no registration — pair it
  with `instance=` to fan a runtime-sourced (DB/remote) body across tenants.
  `coalesce_window` rides that same transaction to collapse a herd of
  near-simultaneous triggers (one scheduler per web worker) into one
  run — no leader election. The APScheduler wrapper defaults it on, derived
  from the schedule's period, plus `max_instances=1`/`coalesce=True`.
- The `ResultLog` is a human/audit artifact, kept strictly separate from the
  context store — it never holds machine state, so it can't corrupt a pulse.
  `record_result` is independent of memory ops; `carried_facts`/`carried_notes`
  snapshot what fed the run before `persist` mutates memory.
- Optional deps (`sqlalchemy`, `apscheduler`, `litellm`) are imported lazily;
  `import context_driven_llm_scheduler` must work with only `portalocker` installed. The core is
  model-agnostic — it never imports a model lib; `ModelAdapter` (2 methods:
  `complete`, `count_tokens`) is the only contract.
- Frontmatter is parsed by a tiny in-house parser (`pulse.py`), no YAML dep.
- Budgeting in `recall()` never silently truncates — dropped notes are
  disclosed in the prompt.
