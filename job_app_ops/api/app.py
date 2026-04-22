from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Awaitable, Callable

import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from job_app_ops.runtime import Runtime, get_runtime
from job_app_ops.schemas import (
    ApproveRunRequest,
    ApplicationResult,
    CandidateProfile,
    EvaluationSummary,
    HealthResponse,
    JobApplicationRequest,
    JobUrlApplicationRequest,
    ProfileAssetKind,
    ProfileVault,
    RejectRunRequest,
)
from job_app_ops.services.metrics import render_metrics
from job_app_ops.services.request_context import build_request_context, reset_request_context, set_request_context
from job_app_ops.services.service_security import TenantPolicyError


def create_api_application(runtime: Runtime | None = None) -> FastAPI:
    runtime = runtime or get_runtime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.startup()
        try:
            yield
        finally:
            await runtime.shutdown()

    app = FastAPI(title="Job Application Copilot API", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        tenant_header = request.headers.get("x-tenant-id")
        request_id = request.headers.get("x-request-id")
        traceparent = request.headers.get("traceparent")

        try:
            tenant_id = tenant_header or runtime.settings.default_tenant_id
            if runtime.settings.require_tenant_header and not tenant_header:
                raise TenantPolicyError("Missing X-Tenant-ID header.")
            if runtime.settings.allowed_tenant_set and tenant_id not in runtime.settings.allowed_tenant_set:
                raise TenantPolicyError(f"Tenant {tenant_id!r} is not allowed.")
        except TenantPolicyError as exc:
            return JSONResponse(status_code=403, content={"detail": str(exc)})

        context = build_request_context(tenant_id=tenant_id, request_id=request_id, traceparent=traceparent)
        token = set_request_context(context)
        try:
            response = await call_next(request)
        finally:
            reset_request_context(token)

        response.headers["X-Request-ID"] = context.request_id
        response.headers["X-Tenant-ID"] = context.tenant_id
        response.headers["traceparent"] = context.traceparent
        return response

    @app.get("/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(service="job-app-api", environment=runtime.settings.environment, details={"mode": "liveness"})

    @app.get("/ready", response_model=HealthResponse)
    async def ready() -> HealthResponse:
        return HealthResponse(service="job-app-api", environment=runtime.settings.environment, details=await runtime.readiness())

    @app.get("/metrics")
    async def metrics() -> Response:
        payload, content_type = render_metrics()
        return Response(content=payload, media_type=content_type)

    @app.post("/api/v1/applications/run", response_model=ApplicationResult)
    async def run_application(request: JobApplicationRequest) -> ApplicationResult:
        try:
            prepared = _prepare_request(runtime, request)
            return await runtime.workflow.run(prepared)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v1/applications/run-from-url", response_model=ApplicationResult)
    async def run_application_from_url(request: JobUrlApplicationRequest) -> ApplicationResult:
        try:
            prepared = _prepare_url_request(runtime, request)
            return await runtime.workflow.run(prepared)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/applications/{run_id}", response_model=ApplicationResult)
    async def get_application(run_id: str) -> ApplicationResult:
        result = runtime.repository.get_result(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} was not found.")
        return result

    @app.post("/api/v1/applications/{run_id}/approve", response_model=ApplicationResult)
    async def approve_application(run_id: str, request: ApproveRunRequest) -> ApplicationResult:
        result = runtime.repository.get_result(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} was not found.")
        updated = runtime.submission_service.approve(result, send_email_now=request.send_email_now)
        runtime.repository.save_result(updated)
        runtime.tracker.log_result(updated)
        return updated

    @app.post("/api/v1/applications/{run_id}/similar-jobs", response_model=ApplicationResult)
    async def discover_similar_jobs(run_id: str, limit: int = 5) -> ApplicationResult:
        result = runtime.repository.get_result(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} was not found.")
        try:
            return await runtime.workflow.discover_similar_jobs(result, limit=limit)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v1/applications/{run_id}/reject", response_model=ApplicationResult)
    async def reject_application(run_id: str, request: RejectRunRequest) -> ApplicationResult:
        result = runtime.repository.get_result(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} was not found.")
        updated = runtime.submission_service.reject(result, request.reason)
        runtime.repository.save_result(updated)
        runtime.tracker.log_result(updated)
        return updated

    @app.get("/api/v1/runs")
    async def list_runs(limit: int = 20):
        return runtime.repository.list_recent(limit=limit)

    @app.get("/api/v1/evals/latest", response_model=EvaluationSummary)
    async def latest_eval_summary() -> EvaluationSummary:
        return EvaluationSummary(case_count=0, metrics={"dataset_exists": 1.0})

    @app.get("/api/v1/profile-vault", response_model=ProfileVault)
    async def get_profile_vault(profile_id: str = "primary-candidate") -> ProfileVault:
        return runtime.profile_vault.get_vault(profile_id)

    @app.get("/api/v1/profile-vault/profile", response_model=CandidateProfile)
    async def get_profile(profile_id: str = "primary-candidate") -> CandidateProfile:
        return runtime.profile_vault.get_profile(profile_id)

    @app.post("/api/v1/profile-vault/profile", response_model=ProfileVault)
    async def save_profile(profile: CandidateProfile) -> ProfileVault:
        return runtime.profile_vault.save_profile(profile)

    @app.post("/api/v1/profile-vault/upload", response_model=ProfileVault)
    async def upload_profile_asset(
        file: UploadFile = File(...),
        kind: ProfileAssetKind | None = None,
    ) -> ProfileVault:
        content = await file.read()
        return runtime.profile_vault.upload_asset(file.filename or "upload.bin", content, kind)

    @app.get("/api/v1/artifacts/{run_id}/{file_name:path}")
    async def download_artifact(run_id: str, file_name: str):
        path = _resolve_managed_file(runtime.settings.artifacts_dir, run_id, file_name)
        return FileResponse(path)

    @app.get("/api/v1/reports/{run_id}/{file_name:path}")
    async def download_report(run_id: str, file_name: str):
        path = _resolve_managed_file(runtime.settings.reports_dir, run_id, file_name)
        return FileResponse(path)

    return app


app = create_api_application()


def run_api() -> None:
    runtime = get_runtime()
    uvicorn.run(app, host=runtime.settings.app_host, port=runtime.settings.app_port, reload=False)


if __name__ == "__main__":
    run_api()


def _prepare_request(runtime: Runtime, request: JobApplicationRequest) -> JobApplicationRequest:
    resolved_profile = runtime.profile_vault.merge_request_profile(request.profile_id, request.profile)
    return request.model_copy(
        update={
            "profile": resolved_profile,
            "profile_id": resolved_profile.profile_id,
            "destination": request.destination or request.source_url,
        }
    )


def _prepare_url_request(runtime: Runtime, request: JobUrlApplicationRequest) -> JobApplicationRequest:
    resolved_profile = runtime.profile_vault.merge_request_profile(request.profile_id, request.profile)
    return JobApplicationRequest(
        profile=resolved_profile,
        profile_id=resolved_profile.profile_id,
        company=request.company,
        role=request.role,
        source_name=request.source_name,
        source_url=request.source_url,
        source_type=request.source_type,
        destination=request.destination or request.source_url,
        submission_channel=request.submission_channel,
        job_text="",
        discover_similar_jobs=request.discover_similar_jobs,
        similar_job_limit=request.similar_job_limit,
    )


def _resolve_managed_file(base_dir: Path, run_id: str, file_name: str) -> Path:
    candidate = (base_dir / run_id / file_name).resolve()
    root = base_dir.resolve()
    if not candidate.is_file() or not candidate.is_relative_to(root):
        raise HTTPException(status_code=404, detail=f"{file_name} was not found for run {run_id}.")
    return candidate
