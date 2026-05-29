"""One manager, many pulses, shared store — the scheduler-agnostic core.

Shows the central value proposition: any scheduler (cron, K8s CronJob,
Lambda, Airflow) just calls ``manager.trigger(pulse_id)``. Here two unrelated
pulses share a single store and are triggered directly. Neither calls a model —
a handler may drive its pulse's memory directly when no model is involved.
"""

import tempfile
from pathlib import Path

from context_driven_llm_scheduler import (
    FileStore,
    Pulse,
    PulseDefinition,
    PulseManager,
)

STORE_DIR = Path(tempfile.gettempdir()) / "context_driven_llm_scheduler-multi"
manager = PulseManager(FileStore(STORE_DIR))


@manager.pulse(PulseDefinition(id="billing-sweep", instructions="Send one."))
def billing(pulse: Pulse, extra: dict | None = None) -> None:
    """Pretend to send one invoice per wake-up, counting in memory."""
    facts = pulse.memory.facts
    facts["invoices_sent"] = facts.get("invoices_sent", 0) + 1
    print(f"[billing] invoices_sent={facts['invoices_sent']}")


@manager.pulse(PulseDefinition(id="cache-warmer", instructions="Warm it."))
def cache(pulse: Pulse, extra: dict | None = None) -> None:
    """Pretend to warm a cache, tracking how many times in memory."""
    facts = pulse.memory.facts
    facts["warmed"] = facts.get("warmed", 0) + 1
    print(f"[cache] warmed={facts['warmed']}")


def run_pulse(pulse_id: str) -> None:
    """Entry point any external scheduler would call.

    Args:
        pulse_id: The pulse to trigger.
    """
    manager.trigger(pulse_id)


if __name__ == "__main__":
    # Whatever scheduler you use, integration is just this call.
    run_pulse("billing-sweep")
    run_pulse("cache-warmer")
    run_pulse("billing-sweep")
    print(f"store={STORE_DIR}")
