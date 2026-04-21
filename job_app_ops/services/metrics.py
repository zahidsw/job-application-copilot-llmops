from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter

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


@contextmanager
def track_run_duration():
    start = perf_counter()
    try:
        yield
    finally:
        job_application_run_duration_seconds.observe(perf_counter() - start)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), "text/plain; version=0.0.4; charset=utf-8"
