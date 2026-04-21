from __future__ import annotations

import httpx

from job_app_ops.config import Settings
from job_app_ops.schemas import JobFetchResult, JobOpportunity, JobRequirements, JobSourceType, SubmissionChannel
from job_app_ops.services.metrics import remote_tool_requests_total


class MCPRemoteToolClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(base_url=self.settings.mcp_server_url, timeout=self.settings.request_timeout_seconds)

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        await self._client.aclose()

    async def readiness(self) -> dict[str, object]:
        response = await self._client.get("/ready")
        response.raise_for_status()
        return response.json()

    async def evaluate_source(
        self,
        *,
        source_url: str,
        source_name: str,
        source_type: JobSourceType,
        submission_channel: SubmissionChannel,
    ) -> dict[str, object]:
        return await self._post_json(
            "/api/v1/tools/evaluate-source",
            {
                "source_url": source_url,
                "source_name": source_name,
                "source_type": source_type.value,
                "submission_channel": submission_channel.value,
            },
            tool="evaluate_source",
        )

    async def normalize_job(self, payload: dict[str, object]) -> JobOpportunity:
        data = await self._post_json("/api/v1/tools/normalize-job", payload, tool="normalize_job")
        return JobOpportunity.model_validate(data)

    async def extract_requirements(self, description: str) -> JobRequirements:
        data = await self._post_json(
            "/api/v1/tools/extract-requirements",
            {"description": description},
            tool="extract_requirements",
        )
        return JobRequirements.model_validate(data)

    async def fetch_job(self, source_url: str) -> JobFetchResult:
        data = await self._post_json(
            "/api/v1/tools/fetch-job",
            {"source_url": source_url},
            tool="fetch_job",
        )
        return JobFetchResult.model_validate(data)

    async def _post_json(self, path: str, payload: dict[str, object], *, tool: str) -> dict[str, object]:
        try:
            response = await self._client.post(path, json=payload)
            response.raise_for_status()
            remote_tool_requests_total.labels(tool=tool, status="ok").inc()
            return response.json()
        except Exception:
            remote_tool_requests_total.labels(tool=tool, status="error").inc()
            raise
