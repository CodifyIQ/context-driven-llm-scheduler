"""Email-monitor pulse: notify on new urgent mail, with spam prevention.

Run it twice in a row::

    uv run python examples/email_monitor.py
    uv run python examples/email_monitor.py

The first run "notifies" about the simulated urgent email; the second run sees
it in the pulse's seen-set / throttle and stays quiet — proving state persisted
across wake-ups via the FileStore. No model is involved: the handler returns
the same memory operations a model would emit, so de-dup and throttling run
through the standard memory protocol.
"""

import tempfile
from pathlib import Path

from context_driven_llm_scheduler import (
    FileStore,
    Pulse,
    PulseDefinition,
    PulseManager,
)

STORE_DIR = Path(tempfile.gettempdir()) / "context_driven_llm_scheduler-email-monitor"

DEFINITION = PulseDefinition(
    id="email-monitor",
    instructions="Notify me about new urgent emails, at most once a minute.",
    throttles={"alert": 60.0},
    keep={"seen": 500},
)
manager = PulseManager(FileStore(STORE_DIR))


def fetch_urgent_emails() -> list[dict[str, str]]:
    """Stand-in inbox fetch. Returns one fixed urgent email."""
    return [{"id": "msg-42", "subject": "Server on fire"}]


@manager.pulse(DEFINITION)
def handle(pulse: Pulse, extra: dict | None = None) -> list[dict[str, object]]:
    """Notify once per urgent email, throttled to one alert per minute."""
    ops: list[dict[str, object]] = []
    for email in fetch_urgent_emails():
        if email["id"] in pulse.memory.seen.get("notified", []):
            print(f"[skip] already notified about {email['id']}")
            continue
        ops.append({"op": "seen", "field": "notified", "id": email["id"]})
        if pulse.seconds_until_available("alert") > 0:
            print("[skip] cooling down — not alerting yet")
            continue
        print(f"[ALERT] {email['subject']} ({email['id']})")
        ops.append({"op": "throttle", "field": "alert"})
    return ops


if __name__ == "__main__":
    result = manager.trigger("email-monitor")
    print(f"trigger_count={result['trigger_count']} store={STORE_DIR}")
