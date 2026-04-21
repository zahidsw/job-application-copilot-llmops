from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from job_app_ops.agents.job_application_agents import JobApplicationAgents
from job_app_ops.config import Settings
from job_app_ops.database import RunRepository
from job_app_ops.schemas import (
    AgentStageSummary,
    ApplicationResult,
    ApprovalPacket,
    GeneratedArtifact,
    JobApplicationRequest,
    JobOpportunity,
    JobRequirements,
    MatchAssessment,
    RunStatus,
)
from job_app_ops.services.exporter import ArtifactExporter
from job_app_ops.services.mcp_remote_client import MCPRemoteToolClient
from job_app_ops.services.metrics import job_application_artifacts_total, job_application_runs_total, track_run_duration
from job_app_ops.services.mlflow_tracker import MLflowTracker


class ApplicationState(TypedDict, total=False):
    run_id: str
    request: JobApplicationRequest
    opportunity: JobOpportunity
    requirements: JobRequirements
    assessment: MatchAssessment
    artifacts: list[GeneratedArtifact]
    approval_packet: ApprovalPacket
    status: RunStatus
    stage_summaries: list[AgentStageSummary]
    metrics: dict[str, float]


class JobApplicationWorkflow:
    def __init__(
        self,
        settings: Settings,
        agents: JobApplicationAgents,
        tools: MCPRemoteToolClient,
        exporter: ArtifactExporter,
        tracker: MLflowTracker,
        repository: RunRepository,
    ) -> None:
        self.settings = settings
        self.agents = agents
        self.tools = tools
        self.exporter = exporter
        self.tracker = tracker
        self.repository = repository
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ApplicationState)
        graph.add_node("source_intake", self._source_intake_node)
        graph.add_node("requirements", self._requirements_node)
        graph.add_node("matcher", self._matcher_node)
        graph.add_node("tailorer", self._tailorer_node)
        graph.add_node("reviewer", self._reviewer_node)
        graph.set_entry_point("source_intake")
        graph.add_edge("source_intake", "requirements")
        graph.add_edge("requirements", "matcher")
        graph.add_edge("matcher", "tailorer")
        graph.add_edge("tailorer", "reviewer")
        graph.add_edge("reviewer", END)
        return graph.compile()

    async def run(self, request: JobApplicationRequest) -> ApplicationResult:
        run_id = uuid4().hex[:12]
        with track_run_duration():
            with self.tracker.run_context(self.settings.mlflow_experiment_name, run_name=f"job-app-{run_id}"):
                self.tracker.log_request(request)
                final_state = await self.graph.ainvoke(
                    {
                        "run_id": run_id,
                        "request": request,
                        "status": RunStatus.queued,
                        "stage_summaries": [],
                        "metrics": {},
                    }
                )

        artifacts = self.exporter.export(run_id, final_state.get("artifacts", []))
        for artifact in artifacts:
            job_application_artifacts_total.labels(artifact_type=artifact.artifact_type).inc()

        status = final_state.get("status", RunStatus.failed)
        result = ApplicationResult(
            run_id=run_id,
            status=status,
            request=final_state.get("request", request),
            opportunity=final_state["opportunity"],
            requirements=final_state["requirements"],
            assessment=final_state["assessment"],
            artifacts=artifacts,
            approval_packet=final_state.get("approval_packet"),
            stage_summaries=final_state.get("stage_summaries", []),
            metrics=final_state.get("metrics", {}),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.repository.save_result(result)
        self.tracker.log_result(result)
        job_application_runs_total.labels(status=result.status.value).inc()
        return result

    async def _source_intake_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        request = state["request"]
        company = request.company
        role = request.role
        source_name = request.source_name
        source_url = request.source_url
        destination = request.destination or source_url
        job_text = request.job_text
        fetch_note = ""

        if not job_text and source_url:
            fetched = await self.tools.fetch_job(source_url)
            job_text = fetched.job_text or fetched.raw_html
            company = company or fetched.company
            role = role or fetched.role
            source_name = source_name or fetched.source_name
            destination = destination or fetched.final_url or source_url
            fetch_note = fetched.fetch_note

        if not job_text:
            raise ValueError("Job description text could not be resolved. Provide job_text or a fetchable source_url.")

        resolved_request = request.model_copy(
            update={
                "company": company,
                "role": role,
                "source_name": source_name or request.source_type.value,
                "destination": destination,
                "job_text": job_text,
            }
        )

        source_policy = await self.tools.evaluate_source(
            source_url=resolved_request.source_url,
            source_name=resolved_request.source_name,
            source_type=resolved_request.source_type,
            submission_channel=resolved_request.submission_channel,
        )
        opportunity = await self.tools.normalize_job(
            {
                "company": resolved_request.company,
                "role": resolved_request.role,
                "source_name": resolved_request.source_name,
                "source_url": resolved_request.source_url,
                "source_type": resolved_request.source_type.value,
                "destination": resolved_request.destination,
                "submission_channel": resolved_request.submission_channel.value,
                "job_text": resolved_request.job_text,
                **source_policy,
            }
        )
        return {
            "request": resolved_request,
            "opportunity": opportunity,
            "status": RunStatus.intake,
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="source_intake", summary=f"Normalized {opportunity.role} at {opportunity.company}. {fetch_note}".strip(), duration_seconds=round(perf_counter() - start, 3))],
        }

    async def _requirements_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        requirements = await self.tools.extract_requirements(state["opportunity"].normalized_description)
        return {
            "requirements": requirements,
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="requirements", summary="Extracted structured requirements from the job description.", duration_seconds=round(perf_counter() - start, 3))],
        }

    async def _matcher_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        assessment = self.agents.match(state["request"].profile, state["opportunity"], state["requirements"])
        status = RunStatus.matching if assessment.ready_for_tailoring else RunStatus.blocked
        return {
            "assessment": assessment,
            "status": status,
            "metrics": {"overall_score": float(assessment.overall_score)},
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="matcher", summary=f"Computed fit score {assessment.overall_score}% with decision {assessment.decision}.", duration_seconds=round(perf_counter() - start, 3))],
        }

    async def _tailorer_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        artifacts: list[GeneratedArtifact] = []
        status = state.get("status", RunStatus.blocked)
        if state["assessment"].ready_for_tailoring:
            artifacts = self.agents.generate_artifacts(
                state["request"].profile,
                state["opportunity"],
                state["requirements"],
                state["assessment"],
            )
            status = RunStatus.tailoring
        return {
            "artifacts": artifacts,
            "status": status,
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="tailorer", summary="Generated tailored artifacts." if artifacts else "Skipped artifact generation because the role did not clear the gate.", duration_seconds=round(perf_counter() - start, 3))],
        }

    async def _reviewer_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        packet = self.agents.review(state["opportunity"], state["assessment"], state.get("artifacts", []))
        status = RunStatus.awaiting_approval if state["assessment"].ready_for_tailoring else RunStatus.blocked
        return {
            "approval_packet": packet,
            "status": status,
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="reviewer", summary=packet.summary, duration_seconds=round(perf_counter() - start, 3))],
        }
