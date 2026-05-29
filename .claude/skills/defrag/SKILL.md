---
name: "defrag"
description: "Scan the codebase for fragmentation and fix what's safe. Catches structural issues that linters miss: duplicated logic, pattern drift, orphaned code, oversized files, stale documentation, and broken design invariants. Use when the user says /defrag, asks to clean up the codebase, wants a health check, or before a release. Also use proactively after a burst of feature work to prevent entropy from accumulating."
---

# Defrag: Codebase Fragmentation Scan

Scan the entire codebase for structural fragmentation. Auto-fix what's safe, report what needs human judgment.

`ruff` already handles lint and formatting. Defrag catches the higher-level issues it misses — duplication, drift, dead code, stale docs, and violations of this library's design invariants.

## How it works

Defrag does not define what "correct" looks like. The conventions live in `CLAUDE.md` and `.claude/rules/`. Defrag reads those documents, then checks whether the codebase follows them.

This means defrag stays accurate as conventions evolve — it has no hardcoded patterns to go stale.

## Phase 1: Gather conventions

Before scanning, read the project's convention sources. These are the source of truth for what "correct structure" means:

- `CLAUDE.md` — package layout, the memory protocol, **design invariants**, conventions, and commands
- `.claude/rules/python.instructions.md` — Python naming, type hints, docstrings, imports, error handling

Also read the relevant skill reference for deeper pattern context:

- `.claude/skills/bdd-test/SKILL.md` — test coverage expectations (Behave only)

Do not re-specify these conventions in your scan. Reference them by reading the files above.

## Phase 2: Launch scan agents in parallel

Use the Agent tool to launch two agents concurrently. Each agent receives the same instruction framework but scans a different scope. Tell each agent: "This is a research-only task — do NOT edit files. Report findings only."

Pass each agent the relevant convention file paths to read before scanning.

### Agent 1: Source & tests scan

Scope: `src/context_driven_llm_scheduler/` and `tests/`

Scan for:
1. **Pattern drift** — Read the layout in `CLAUDE.md` (`core/`, `adapters/`, `stores/`, `schedulers/`, `util.py`). Confirm each module sits where the layout says and exposes what the layout describes. Flag deviations.
2. **Duplicated logic** — Search for functions with similar names or near-identical bodies across modules. The verbs `apply_ops` builds on live in `util.py` (`add_to_seen_set`, `check_throttle`, `prune_history`, `migrate_context`); flag local reimplementations that belong there.
3. **Orphaned code** — Run `uv run ruff check --select F401,F811,F841` for unused imports/variables. Search for functions and classes never referenced outside their own file (account for lazy re-exports in `__init__.py` `__getattr__`).
4. **Convention violations** — Read `.claude/rules/python.instructions.md`, then check the code against each convention it specifies (Google-style docstrings, type hints on every signature and class attribute, absolute imports, no `from x import *`, error-handling style).
5. **Test coverage gaps** — Read the BDD conventions (tests are **Behave only**; see `.claude/skills/bdd-test` and `tests/features/`). Compare public surface (`PulseManager`, `Pulse.recall`/`persist`, memory ops, stores, adapters) against feature files. Flag behavior with no corresponding scenario.

### Agent 2: Design-invariant & cross-cutting scan

Scope: project-wide

Read the **Design invariants** section of `CLAUDE.md` first, then scan for violations:

1. **Lazy optional deps** — `import context_driven_llm_scheduler` must work with only `portalocker` installed. Confirm `sqlalchemy`, `apscheduler`, and `litellm` are imported lazily (inside functions / `__getattr__`), never at module top level in code reachable from the package root. Flag any eager import.
2. **Model-agnostic core** — `core/` must never import a model library. The only model contract is `ModelAdapter` (two methods: `complete`, `count_tokens`). Flag any model-lib import under `core/`.
3. **No YAML dependency** — frontmatter is parsed by the in-house parser in `pulse.py`. Flag any `import yaml` or added YAML dependency.
4. **JSON-serializable context** — context must stay a plain JSON-serializable dict; datetimes stored as ISO strings. Flag places that stash non-serializable objects or raw `datetime`s into context.
5. **Honest budgeting** — `recall()` must never silently truncate; dropped notes are disclosed in the prompt. Flag any truncation path that drops content without disclosure.
6. **Transactional trigger** — `trigger()` must wrap load→handler→persist→save in `store.transaction(key)`. Flag any path that mutates/saves outside the transaction.
7. **Closed memory op set** — ops are `note`, `seen`, `throttle`, `set`, `forget`, defined in `memory.py` (`MEMORY_OPS` + `MEMORY_TOOL_SCHEMA`). Flag op handling that drifts from this set or extends it without updating both constants.
8. **Documentation drift** — Compare `CLAUDE.md` against the actual code. Flag conventions the code doesn't follow, and patterns in the code `CLAUDE.md` doesn't document. Stale docs are high-impact because they cause AI-generated code to contradict the codebase.
9. **Skill drift** — Skills are **prescriptive**: they document the target architecture, not the current state. For each skill in `.claude/skills/`, spot-check 2-3 patterns against the actual code. When the code deviates, flag the **code** as needing to adopt the prescribed pattern — do NOT recommend changing the skill to match the code.
10. **Dependency health** — Check `pyproject.toml` (core deps + the `sqlite` / `scheduler` / `litellm` / `dev` extras) against actual imports. Flag declared-but-unused and used-but-undeclared dependencies, and any optional dependency that leaked into core (`dependencies`).

### Report format for all agents

Each agent groups findings by severity:
- **auto-fixable** — safe to fix without human judgment (unused imports, formatting, missing type hints on trivial signatures)
- **needs-review** — real issue but requires human decision (duplication candidates, invariant violations, architecture choices)
- **informational** — observations about codebase health, not actionable yet

## Phase 3: Fix and report

Wait for all agents to complete. Then:

1. **Auto-fix** safe issues directly — unused imports, formatting, trivially mechanical fixes.
2. **Verify** fixes don't break anything by running `uv run ruff check .` and `uv run behave --tags="not @integration-test"`. If a fix introduces a new issue, revert it and move it to "needs-review."
3. **Present** the consolidated report:

```
## Defrag Report

### Auto-fixed
- [list of changes made, with file paths]

### Needs Review
- **[Category]**: [description] — [file:line]

### Informational
- [observations about codebase health]
```
