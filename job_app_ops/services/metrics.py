from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from inspect import iscoroutinefunction
from time import perf_counter
from typing import Any, Callable

from prometheus_client import Counter, Histogram, generate_latest


job_application_runs_total = Counter(
    "job_application_runs_total",
    "Total job application runs by final status.",
    ["status"],
)

job_application_artifacts_total = Counter(
    "job_application_artifacts_total",
    "Generated application artifacts.",
    ["artifact_type"],
)

job_application_submissions_total = Counter(
    "job_application_submissions_total",
    "Submission or handoff actions.",
    ["channel", "status"],
)

job_application_run_duration_seconds = Histogram(
    "job_application_run_duration_seconds",
    "End-to-end application run duration.",
)

remote_tool_requests_total = Counter(
    "job_application_remote_tool_requests_total",
    "Calls made to the remote tool service.",
    ["tool", "status"],
)

remote_tool_duration_seconds = Histogram(
    "job_application_remote_tool_duration_seconds",
    "Remote tool call duration by tool and status.",
    ["tool", "status"],
)

graph_node_runs_total = Counter(
    "job_application_graph_node_runs_total",
    "LangGraph node executions by node name and status.",
    ["node", "status"],
)

graph_node_duration_seconds = Histogram(
    "job_application_graph_node_duration_seconds",
    "LangGraph node duration by node name and status.",
    ["node", "status"],
)


@contextmanager
def track_run_duration():
    start = perf_counter()
    try:
        yield
    finally:
        job_application_run_duration_seconds.observe(perf_counter() - start)


@contextmanager
def track_remote_tool_duration(tool: str):
    start = perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        remote_tool_duration_seconds.labels(tool=tool, status=status).observe(perf_counter() - start)


@contextmanager
def track_graph_node_duration(node: str):
    start = perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        graph_node_runs_total.labels(node=node, status=status).inc()
        graph_node_duration_seconds.labels(node=node, status=status).observe(perf_counter() - start)


def instrument_graph_node(node: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with track_graph_node_duration(node):
                    return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with track_graph_node_duration(node):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), "text/plain; version=0.0.4; charset=utf-8"
