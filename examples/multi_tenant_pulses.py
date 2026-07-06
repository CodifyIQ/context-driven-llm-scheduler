"""One definition, many tenants — instance partitioning + ad-hoc execution.

Shows the two additive capabilities for multi-tenant pulses:

* **Instance partitioning** — the *same* pulse id runs against isolated
  per-tenant state via ``trigger(..., instance=tenant)``. One shared rule, one
  memory per tenant, no composite-id string hacks in app code.
* **Ad-hoc definition execution** — the rule body lives in the consumer's
  "database" (here, a dict) rather than a ``pulse.md`` file, so it is built at
  call time with ``PulseDefinition.from_markdown`` and run directly via
  ``trigger_definition`` with no pre-registration.

Neither path calls a model — a handler may drive its pulse's memory directly.
Run it twice to watch each tenant's per-instance count carry across wake-ups::

    uv run python examples/multi_tenant_pulses.py
    uv run python examples/multi_tenant_pulses.py
"""

import tempfile
from pathlib import Path

from context_driven_llm_scheduler import (
    FileStore,
    Pulse,
    PulseDefinition,
    PulseManager,
)

STORE_DIR = Path(tempfile.gettempdir()) / "context_driven_llm_scheduler-multi-tenant"
manager = PulseManager(FileStore(STORE_DIR))

# Stand-in for the consumer's database: each team's readiness rule as a markdown
# doc keyed by team id. In a real service these are rows fetched per request.
TEAM_RULES: dict[str, str] = {
    "team-hawks": "Check the Hawks' readiness three days before each game.",
    "team-wolves": "Check the Wolves' readiness three days before each game.",
}


def readiness_check(pulse: Pulse, extra: dict | None = None) -> None:
    """Advance a per-tenant readiness count in the pulse's isolated memory.

    The same handler serves every tenant; ``instance`` partitioning is what
    keeps each team's memory separate, so this code never sees a tenant id.

    Args:
        pulse: The bound pulse for this tenant's partition.
        extra: Unused per-trigger payload.
    """
    facts = pulse.memory.facts
    facts["checks_run"] = facts.get("checks_run", 0) + 1
    pulse.record_result(f"readiness check #{facts['checks_run']}")


def run_team_readiness(team_id: str) -> None:
    """Run one team's DB-sourced readiness rule against its own partition.

    This is what the consumer's scheduler calls on the cadence it computes
    (e.g. "three days before each game"): fetch the rule, build a definition,
    and trigger it for the team's instance — no registration involved.

    Args:
        team_id: The tenant whose rule to run; also the state partition.
    """
    definition = PulseDefinition.from_markdown(
        TEAM_RULES[team_id], default_id="readiness-check"
    )
    context = manager.trigger_definition(
        definition, readiness_check, instance=team_id
    )
    print(f"[{team_id}] checks_run={context['memory']['facts']['checks_run']}")


if __name__ == "__main__":
    # Every team shares the "readiness-check" definition id but keeps isolated
    # state: the Hawks run twice, the Wolves once, and their counts never mix.
    run_team_readiness("team-hawks")
    run_team_readiness("team-wolves")
    run_team_readiness("team-hawks")
    print(f"store={STORE_DIR}")
