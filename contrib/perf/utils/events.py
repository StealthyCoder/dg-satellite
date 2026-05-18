from contextlib import contextmanager
from locust import TaskSet, User
from requests import RequestException
from time import perf_counter
from typing import Dict, Optional, Union

Parent = Union[TaskSet, User]


@contextmanager
def tracking(parent: Optional[Parent], *opnames: str):
    """Track stats for complex actions which span accross several requests.

    Several names can be passed in to allow calculating aggregates.
    """
    if parent is None:
        yield None
        return
    # See locust.clients.HTTPSession.request for details
    if isinstance(parent, TaskSet):
        parent = parent.user
    start_time = perf_counter()
    error: Optional[Exception] = None
    try:
        yield None
    except Exception as why:
        error = why
        raise
    finally:
        duration = (perf_counter() - start_time) * 1000
        ctx = parent.context()
        for name in opnames:
            parent.environment.events.request.fire(
                context=ctx,
                exception=error,
                name=name,
                request_type="TRACE",  # mandatory HTTP method, fake it
                response=None,  # unused by locust, may be None
                response_length=0,  # not applicable, fake it
                response_time=duration,
            )
