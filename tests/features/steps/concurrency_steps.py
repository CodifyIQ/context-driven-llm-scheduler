"""Step definitions for concurrency.feature."""

import threading

from behave import when


@when('{n:d} threads trigger "{pulse_id}" at once')
def step_threads_trigger(context, n, pulse_id):
    barrier = threading.Barrier(n)
    errors: list[Exception] = []

    def worker():
        try:
            barrier.wait()
            context.manager.trigger(pulse_id)
        except Exception as exc:  # noqa: BLE001 - surface any thread error
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"threads raised: {errors!r}"
