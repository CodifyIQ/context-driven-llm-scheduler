"""AI-agent pulse: a tiny state machine with cheap-checks-first.

Demonstrates how a handler advances a persisted state machine
(idle → working → escalate) across wake-ups, doing the cheapest check first
and only "escalating" after repeated stalls. No real LLM/agent calls — the
library deliberately ships no agent logic. State lives in the pulse's memory
facts, so it carries across wake-ups with no external bookkeeping.
"""

import tempfile
from pathlib import Path

from context_driven_llm_scheduler import (
    FileStore,
    Pulse,
    PulseDefinition,
    PulseManager,
)

STORE_DIR = Path(tempfile.gettempdir()) / "context_driven_llm_scheduler-ai-agent"
manager = PulseManager(FileStore(STORE_DIR))


def job_is_done() -> bool:
    """Cheap stand-in health check. Pretend the job is still running."""
    return False


@manager.pulse(
    PulseDefinition(id="agent-heartbeat", instructions="Watch the job.")
)
def handle(pulse: Pulse, extra: dict | None = None) -> None:
    """Advance the agent state machine, escalating after 3 stalls."""
    facts = pulse.memory.facts
    facts.setdefault("state", "idle")
    facts.setdefault("stall_count", 0)

    # Cheapest possible check first — bail before any expensive work.
    if job_is_done():
        facts["state"] = "idle"
        facts["stall_count"] = 0
        print("[idle] nothing to do")
        return

    if facts["state"] == "idle":
        facts["state"] = "working"

    facts["stall_count"] += 1
    if facts["stall_count"] >= 3 and facts["state"] != "escalate":
        facts["state"] = "escalate"
        print("[ESCALATE] job stalled 3+ times — paging a human")
    else:
        print(f"[working] stall_count={facts['stall_count']}")


if __name__ == "__main__":
    for _ in range(4):
        result = manager.trigger("agent-heartbeat")
        print(f"  -> state={result['memory']['facts']['state']}")
