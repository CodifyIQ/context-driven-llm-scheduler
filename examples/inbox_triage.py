"""Markdown-defined pulse: the membrane in action, runnable offline.

The pulse is defined entirely in ``pulses/inbox_triage.md`` — schedule, memory
policy, and the standing instructions. context_driven_llm_scheduler assembles the prompt from
those instructions plus what the pulse remembers (:meth:`Pulse.recall`), the
model decides what to do, and context_driven_llm_scheduler folds the model's memory operations
back into stored state (:meth:`Pulse.persist`).

This example ships a fake adapter so it runs with no API key. The real thing is
one line — see ``REAL_ADAPTER`` below. Run it twice::

    uv run python examples/inbox_triage.py
    uv run python examples/inbox_triage.py

The first run "notifies"; the second sees the email in memory and stays quiet.
"""

import tempfile
from pathlib import Path

from context_driven_llm_scheduler import FileStore, Pulse, PulseManager

PULSES_DIR = Path(__file__).parent / "pulses"
STORE_DIR = Path(tempfile.gettempdir()) / "context_driven_llm_scheduler-inbox-triage"

manager = PulseManager.from_dir(PULSES_DIR, FileStore(STORE_DIR))


def fetch_urgent_emails() -> list[dict[str, str]]:
    """Stand-in inbox fetch. Returns one fixed urgent email."""
    return [{"id": "msg-42", "subject": "Server on fire"}]


class FakeAdapter:
    """Offline stand-in for a real model: emits ops by simple rules.

    Mirrors what a model would return through ``update_memory`` so the example
    runs deterministically without network or keys.
    """

    def complete(self, prompt: str, **kwargs: object) -> str:
        """Return the prompt unchanged (unused here)."""
        return prompt

    def count_tokens(self, text: str) -> int:
        """Rough token estimate for budgeting demos."""
        return len(text) // 4

    def propose_memory_ops(
        self, pulse: Pulse, emails: list[dict[str, str]]
    ) -> list[dict[str, object]]:
        """Decide ops the way the instructions describe."""
        ops: list[dict[str, object]] = []
        for email in emails:
            if email["id"] in pulse.memory.seen.get("emails", []):
                continue
            ops.append({"op": "seen", "field": "emails", "id": email["id"]})
            if pulse.seconds_until_available("notify") > 0:
                ops.append({"op": "note", "text": "Held alert (throttle)."})
                continue
            print(f"[ALERT] {email['subject']} ({email['id']})")
            ops.append({"op": "throttle", "field": "notify"})
            ops.append(
                {"op": "note", "text": f"Notified about {email['id']}."}
            )
        return ops


adapter = FakeAdapter()

# REAL_ADAPTER: swap the block below in (and
# `pip install context_driven_llm_scheduler[litellm]`) to run on any provider — the model emits
# the same ops. Call defaults (timeout, retries, ...) are configured once at
# construction, not per call:
#
#   from context_driven_llm_scheduler import LiteLLMAdapter
#   adapter = LiteLLMAdapter(
#       "anthropic/claude-sonnet-4-6", timeout=30, num_retries=2,
#   )
#   # inside the handler:
#   prompt = pulse.recall(extra={"emails": emails})
#   return adapter.propose_memory_ops(prompt)


@manager.pulse("inbox-triage")
def triage(pulse: Pulse, extra: dict | None = None) -> list[dict[str, object]]:
    """Recall memory, let the model decide, return memory ops to persist."""
    emails = fetch_urgent_emails()
    prompt = pulse.recall(extra={"emails": emails})
    print("--- prompt the model would see ---")
    print(prompt)
    print("----------------------------------")
    return adapter.propose_memory_ops(pulse, emails)


if __name__ == "__main__":
    result = manager.trigger("inbox-triage")
    print(f"notes={result['memory']['notes']}")
