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

    def add_cron(self, pulse_id: str, cron_expr: str, **kwargs: object) -> Job:
        """Schedule a pulse on a 5-field crontab expression.

        Args:
            pulse_id: The registered pulse to trigger.
            cron_expr: A standard ``m h dom mon dow`` crontab expression.
            **kwargs: Extra arguments forwarded to ``add_job``.

        Returns:
            The created APScheduler ``Job``.
        """
        return self.scheduler.add_job(
            self.manager.trigger,
            trigger=CronTrigger.from_crontab(cron_expr),
            args=[pulse_id],
            id=pulse_id,
            **kwargs,
        )

    def add_interval(
        self, pulse_id: str, *, seconds: float, **kwargs: object
    ) -> Job:
        """Schedule a pulse to fire every ``seconds``.

        Args:
            pulse_id: The registered pulse to trigger.
            seconds: Interval between triggers, in seconds.
            **kwargs: Extra arguments forwarded to ``add_job``.

        Returns:
            The created APScheduler ``Job``.
        """
        return self.scheduler.add_job(
            self.manager.trigger,
            trigger="interval",
            seconds=seconds,
            args=[pulse_id],
            id=pulse_id,
            **kwargs,
        )

    def start(self) -> None:
        """Start the background scheduler."""
        self.scheduler.start()

    def shutdown(self, wait: bool = True) -> None:
        """Stop the background scheduler.

        Args:
            wait: Whether to wait for running jobs to finish.
        """
        self.scheduler.shutdown(wait=wait)
