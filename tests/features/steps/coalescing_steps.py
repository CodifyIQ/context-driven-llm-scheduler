"""Steps for coalescing.feature: the cross-process de-duplication window."""

import threading

from behave import when


@when('I trigger "{pulse_id}" with a {window:d} second coalesce window')
def step_trigger_coalesced(context, pulse_id, window):
    context.result = context.manager.trigger(
        pulse_id, coalesce_window=window
    )


@when(
    '{n:d} threads trigger "{pulse_id}" with a {window:d} second '
    "coalesce window at once"
)
def step_threads_trigger_coalesced(context, n, pulse_id, window):
    barrier = threading.Barrier(n)
    errors: list[Exception] = []

    def worker():
        try:
            barrier.wait()
            context.manager.trigger(pulse_id, coalesce_window=window)
        except Exception as exc:  # noqa: BLE001 - surface any thread error
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"threads raised: {errors!r}"
