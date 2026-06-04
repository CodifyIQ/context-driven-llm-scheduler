"""FastAPI + Bedrock + markdown jobs + markdown results, wired end to end.

Shows the shape for running unattended, markdown-defined LLM jobs inside a
FastAPI backend:

* **Markdown jobs, no frontmatter.** ``pulses/daily_digest.md`` is pure prose;
  its id (``daily_digest``) comes from the filename. Scheduling lives in code,
  where an engineer is already typing — not in the markdown.
* **Bedrock via LiteLLM.** ``LiteLLMAdapter("bedrock/...")`` needs only AWS
  credentials from the usual boto3 chain. The membrane stays model-agnostic.
* **Markdown results.** A :class:`ResultLog` records each run — result, the
  context the model saw, and the memory changes persisted for next time — to
  ``results/<id>.md``.
* **Safe under multiple workers.** The scheduler runs in ONE process (guarded
  by an env flag), and ``add_cron`` defaults a coalesce window on, so even if
  the flag is misconfigured the same tick won't double-fire.

This is a sketch: it has no real route handlers and won't call Bedrock without
credentials. The wiring is the point.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from context_driven_llm_scheduler import (
    APSchedulerPulse,
    FileStore,
    LiteLLMAdapter,
    Pulse,
    PulseManager,
    ResultLog,
)

PULSES_DIR = Path(__file__).parent / "pulses"
STATE_DIR = Path(os.environ.get("PULSE_STATE_DIR", "/var/lib/pulses"))

# One adapter for every pulse; swap the model string for any Bedrock model.
adapter = LiteLLMAdapter(
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
    timeout=30,
    num_retries=2,
)

# Markdown state (machine) and markdown results (human) live side by side.
store = FileStore(STATE_DIR / "store")
result_log = ResultLog(STATE_DIR / "results")
manager = PulseManager.from_dir(PULSES_DIR, store, result_log=result_log)


def fetch_recent_events() -> list[dict[str, str]]:
    """Stand-in for whatever the job should look at this run."""
    return [{"id": "evt-1", "summary": "deploy finished"}]


@manager.pulse("daily_digest")
def run_digest(pulse: Pulse, extra: dict | None = None) -> list[dict[str, object]]:
    """Recall memory, ask Bedrock to decide, record the result and memory ops.

    The model call is ours, exactly as the membrane intends: recall the prompt,
    call the adapter, record the human-readable result, and return the memory
    operations the model emitted for the library to persist.
    """
    events = fetch_recent_events()
    prompt = pulse.recall(extra={"events": events}, adapter=adapter, max_tokens=8000)
    digest = adapter.complete(prompt)
    pulse.record_result(digest, events=len(events))
    return adapter.propose_memory_ops(prompt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the pulse scheduler in exactly one process.

    Run the API with many workers if you like, but set ``RUN_SCHEDULER=1`` for
    only one of them (e.g. a dedicated worker, or a sidecar started with a
    single worker). The coalesce window is a second line of defense, not a
    substitute for this.
    """
    pulses: APSchedulerPulse | None = None
    if os.environ.get("RUN_SCHEDULER") == "1":
        pulses = APSchedulerPulse(manager)
        # Coalesce window defaults to the schedule's period, so duplicate
        # fires across processes collapse to a single run.
        pulses.add_cron("daily_digest", "0 9 * * *")
        pulses.start()
    try:
        yield
    finally:
        if pulses is not None:
            pulses.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/pulses/{pulse_id}/trigger")
def trigger_now(pulse_id: str) -> dict[str, object]:
    """Trigger a pulse on demand (e.g. for testing or a manual re-run).

    No coalesce window here: a manual trigger should always run.
    """
    context = manager.trigger(pulse_id)
    return {"trigger_count": context.get("trigger_count")}
