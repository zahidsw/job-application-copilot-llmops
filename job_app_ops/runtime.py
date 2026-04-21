from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from job_app_ops.agents.job_application_agents import JobApplicationAgents
from job_app_ops.agents.llm_client import LLMClient
from job_app_ops.config import Settings, get_settings
from job_app_ops.database import RunRepository, init_db
from job_app_ops.graph.workflow import JobApplicationWorkflow
from job_app_ops.services.exporter import ArtifactExporter
from job_app_ops.services.mcp_remote_client import MCPRemoteToolClient
from job_app_ops.services.mlflow_tracker import MLflowTracker
from job_app_ops.services.profile_vault import ProfileVaultService
from job_app_ops.services.submission_service import SubmissionService


@dataclass
class Runtime:
    settings: Settings
    workflow: JobApplicationWorkflow
    tools: MCPRemoteToolClient
    repository: RunRepository
    tracker: MLflowTracker
    submission_service: SubmissionService
    profile_vault: ProfileVaultService

    async def startup(self) -> None:
        await self.tools.startup()

    async def shutdown(self) -> None:
        await self.tools.shutdown()

    async def readiness(self) -> dict[str, object]:
        self.repository.healthcheck()
        mcp_status = await self.tools.readiness()
        return {"database": "ok", "mcp": mcp_status}


@lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    settings = get_settings()
    init_db(settings)
    tools = MCPRemoteToolClient(settings)
    profile_vault = ProfileVaultService(settings)
    agents = JobApplicationAgents(settings, profile_vault, LLMClient(settings))
    exporter = ArtifactExporter(settings)
    repository = RunRepository(settings)
    tracker = MLflowTracker(settings)
    submission_service = SubmissionService(settings)
    workflow = JobApplicationWorkflow(
        settings=settings,
        agents=agents,
        tools=tools,
        exporter=exporter,
        tracker=tracker,
        repository=repository,
    )
    return Runtime(
        settings=settings,
        workflow=workflow,
        tools=tools,
        repository=repository,
        tracker=tracker,
        submission_service=submission_service,
        profile_vault=profile_vault,
    )
