from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import Response
import uvicorn

from job_app_ops.config import get_settings
from job_app_ops.schemas import JobFetchResult, JobOpportunity, JobRequirements, JobSourceType, SubmissionChannel
from job_app_ops.services.metrics import render_metrics
from job_app_ops.services.tool_gateway import evaluate_source_policy, extract_job_requirements, fetch_job_from_url, normalize_job_post


settings = get_settings()
app = FastAPI(title="Job Application Tool Service", version="0.1.0")


@app.get("/ready")
async def ready():
    return {"status": "ok", "service": "job-application-tool-service"}


@app.get("/metrics")
async def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


@app.post("/api/v1/tools/evaluate-source")
async def evaluate_source(payload: dict[str, str | bool]):
    return evaluate_source_policy(
        settings=settings,
        source_url=str(payload.get("source_url", "")),
        source_name=str(payload.get("source_name", "")),
        source_type=JobSourceType(str(payload.get("source_type", JobSourceType.manual_entry.value))),
        submission_channel=SubmissionChannel(str(payload.get("submission_channel", SubmissionChannel.manual_handoff.value))),
    )


@app.post("/api/v1/tools/normalize-job", response_model=JobOpportunity)
async def normalize_job(payload: dict[str, object]):
    return normalize_job_post(
        company=str(payload.get("company", "")),
        role=str(payload.get("role", "")),
        source_name=str(payload.get("source_name", "")),
        source_url=str(payload.get("source_url", "")),
        source_type=JobSourceType(str(payload.get("source_type", JobSourceType.manual_entry.value))),
        destination=str(payload.get("destination", "")),
        submission_channel=SubmissionChannel(str(payload.get("submission_channel", SubmissionChannel.manual_handoff.value))),
        job_text=str(payload.get("job_text", "")),
        source_identifier=str(payload.get("source_identifier", "")),
        source_approved=bool(payload.get("source_approved", True)),
        source_policy_note=str(payload.get("source_policy_note", "")),
    )


@app.post("/api/v1/tools/extract-requirements", response_model=JobRequirements)
async def extract_requirements(payload: dict[str, str]):
    return extract_job_requirements(str(payload.get("description", "")))


@app.post("/api/v1/tools/fetch-job", response_model=JobFetchResult)
async def fetch_job(payload: dict[str, str]):
    return fetch_job_from_url(str(payload.get("source_url", "")))


def run_mcp() -> None:
    uvicorn.run(app, host="0.0.0.0", port=settings.mcp_port, reload=False)


if __name__ == "__main__":
    run_mcp()
