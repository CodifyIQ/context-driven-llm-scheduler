"""Behave hooks: give every scenario a fresh temp store and manager."""

import shutil
import tempfile
from pathlib import Path

from context_driven_llm_scheduler import FileStore, PulseManager


def before_scenario(context, scenario):
    """Build an isolated FileStore + PulseManager for the scenario."""
    context.tmpdir = Path(tempfile.mkdtemp(prefix="context_driven_llm_scheduler-test-"))
    context.store = FileStore(context.tmpdir / "store")
    context.manager = PulseManager(context.store)
    context.result = None
    context.raised = None


def after_scenario(context, scenario):
    """Remove the scenario's temp directory."""
    tmpdir = getattr(context, "tmpdir", None)
    if tmpdir is not None:
        shutil.rmtree(tmpdir, ignore_errors=True)
