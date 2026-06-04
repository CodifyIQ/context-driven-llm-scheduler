"""Optional thin APScheduler wrapper.

Requires the ``scheduler`` extra (``pip install context_driven_llm_scheduler[scheduler]``).
This is purely a convenience for systems that want built-in scheduling; the
core library stays scheduler-agnostic — any cron/K8s/Lambda job can call
``manager.trigger(pulse_id)`` directly.
"""

from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from context_driven_llm_scheduler.core.manager import PulseManager
from context_driven_llm_scheduler.util import utcnow


class APSchedulerPulse:
    """Drive :meth:`PulseManager.trigger` calls from APScheduler jobs.

    Attributes:
        manager: The pulse manager whose pulses are scheduled.
        scheduler: The underlying APScheduler ``BackgroundScheduler``.
    """

    manager: PulseManager
    scheduler: BackgroundScheduler

    def __init__(
        self,
        manager: PulseManager,
        scheduler: BackgroundScheduler | None = None,
    ) -> None:
        """Initialize the wrapper.

        Args:
            manager: The pulse manager to trigger.
            scheduler: An existing scheduler to use, or None to create a new
                ``BackgroundScheduler``.
        """
        self.manager = manager
        self.scheduler = scheduler or BackgroundScheduler()

    def add_cron(
        self,
        pulse_id: str,
        cron_expr: str,
        *,
        dedupe: bool = True,
        coalesce_window: float | None = None,
        **kwargs: object,
    ) -> Job:
        """Schedule a pulse on a 5-field crontab expression.

        Hardened against duplicate execution by default. Within one process,
        ``max_instances=1`` and ``coalesce=True`` stop a slow run from stacking
        overlapping ones (override either via ``kwargs``). Across processes —
        e.g. one scheduler per web worker — ``dedupe`` passes a coalesce window
        to :meth:`PulseManager.trigger` so the herd collapses to a single run.

        Args:
            pulse_id: The registered pulse to trigger.
            cron_expr: A standard ``m h dom mon dow`` crontab expression.
            dedupe: When True (default), skip a run whose previous run was
                within ``coalesce_window`` seconds, so concurrent schedulers
                don't double-fire. Set False to disable cross-process
                de-duplication.
            coalesce_window: Seconds within which a repeat run is treated as a
                duplicate. Defaults to the schedule's own period (the gap
                between consecutive fires), so a job never runs more than once
                per scheduled tick.
            **kwargs: Extra arguments forwarded to ``add_job`` (e.g.
                ``max_instances``, ``coalesce``).

        Returns:
            The created APScheduler ``Job``.
        """
        trigger = CronTrigger.from_crontab(cron_expr)
        window = self._resolve_window(
            dedupe, coalesce_window, _cron_period_seconds(trigger)
        )
        return self.scheduler.add_job(
            self.manager.trigger,
            trigger=trigger,
            args=[pulse_id],
            kwargs={"coalesce_window": window},
            id=pulse_id,
            **{"max_instances": 1, "coalesce": True, **kwargs},
        )

    def add_interval(
        self,
        pulse_id: str,
        *,
        seconds: float,
        dedupe: bool = True,
        coalesce_window: float | None = None,
        **kwargs: object,
    ) -> Job:
        """Schedule a pulse to fire every ``seconds``.

        Hardened against duplicate execution like :meth:`add_cron`; see there
        for the ``dedupe`` / ``coalesce_window`` semantics. The window defaults
        to ``seconds`` (the interval itself).

        Args:
            pulse_id: The registered pulse to trigger.
            seconds: Interval between triggers, in seconds.
            dedupe: When True (default), de-duplicate concurrent runs across
                processes via a coalesce window.
            coalesce_window: Seconds within which a repeat run is a duplicate.
                Defaults to ``seconds``.
            **kwargs: Extra arguments forwarded to ``add_job``.

        Returns:
            The created APScheduler ``Job``.
        """
        window = self._resolve_window(dedupe, coalesce_window, seconds)
        return self.scheduler.add_job(
            self.manager.trigger,
            trigger="interval",
            seconds=seconds,
            args=[pulse_id],
            kwargs={"coalesce_window": window},
            id=pulse_id,
            **{"max_instances": 1, "coalesce": True, **kwargs},
        )

    @staticmethod
    def _resolve_window(
        dedupe: bool, explicit: float | None, derived: float | None
    ) -> float | None:
        """Pick the coalesce window: off, explicit, or derived from schedule.

        Args:
            dedupe: Whether cross-process de-duplication is enabled.
            explicit: A caller-supplied window, or None to derive one.
            derived: The window derived from the schedule's period.

        Returns:
            The window to pass to :meth:`PulseManager.trigger`, or None to
            disable coalescing.
        """
        if not dedupe:
            return None
        return explicit if explicit is not None else derived

    def start(self) -> None:
        """Start the background scheduler."""
        self.scheduler.start()

    def shutdown(self, wait: bool = True) -> None:
        """Stop the background scheduler.

        Args:
            wait: Whether to wait for running jobs to finish.
        """
        self.scheduler.shutdown(wait=wait)


def _cron_period_seconds(trigger: CronTrigger) -> float | None:
    """Best-effort seconds between consecutive fires of ``trigger``.

    Used to default a cron job's coalesce window to its own period. Returns
    None if the period can't be determined (e.g. an irregular schedule with no
    two upcoming fires), in which case cross-process de-duplication stays off
    unless the caller passes an explicit window.

    Args:
        trigger: The cron trigger to measure.

    Returns:
        The period in seconds, or None if it can't be derived.
    """
    try:
        now = utcnow()
        first = trigger.get_next_fire_time(None, now)
        if first is None:
            return None
        second = trigger.get_next_fire_time(first, first)
        if second is None:
            return None
        return (second - first).total_seconds()
    except Exception:  # never let window-derivation break scheduling
        return None
