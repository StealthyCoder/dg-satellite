import os

from gevent import spawn_later  # type: ignore
from locust import stats, events  # type: ignore


stats.CONSOLE_STATS_INTERVAL_SEC = int(os.getenv("CONSOLE_STATS_INTERVAL", 5))


@events.init.add_listener
def on_runner_initialized(runner, **kw):
    # An ability to cut off the first $X seconds of stats.
    # Used in tests with heavy initialization which corrupts data.
    def _clear_stats(interval, action):
        print("Clear stats {} seconds after {}".format(interval, action))
        runner.stats.clear_all()

    reset_after = int(os.getenv("CLEAR_STATS_AFTER_INIT") or 0)
    if reset_after > 0:
        spawn_later(reset_after, _clear_stats, reset_after, "initialization complete")

    reset_after = int(os.getenv("CLEAR_STATS_AFTER_SPAWNING") or 0)
    if reset_after > 0:

        @events.spawning_complete.add_listener
        def clear_stats_after_spawning(**kw):
            events.spawning_complete.remove_listener(clear_stats_after_spawning)
            spawn_later(reset_after, _clear_stats, reset_after, "spawning complete")
