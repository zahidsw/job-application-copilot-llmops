from __future__ import annotations

import asyncio
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
    SimilarJobMatch,
)
from job_app_ops.services.exporter import ArtifactExporter
from job_app_ops.services.mcp_remote_client import MCPRemoteToolClient
from job_app_ops.services.langsmith_observability import (
    set_langsmith_metadata,
    summarize_graph_run_inputs,
    summarize_graph_run_outputs,
    summarize_similar_refresh_inputs,
    summarize_workflow_node_inputs,
    summarize_workflow_node_outputs,
    traceable,
)
from job_app_ops.services.metrics import (
    instrument_graph_node,
    job_application_artifacts_total,
    job_application_runs_total,
    track_graph_node_duration,
    track_run_duration,
)
from job_app_ops.services.mlflow_tracker import MLflowTracker


class ApplicationState(TypedDict, total=False):
    run_id: str
    request: JobApplicationRequest
    opportunity: JobOpportunity
    requirements: JobRequirements
    assessment: MatchAssessment
    similar_jobs: list[SimilarJobMatch]
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
        graph.add_node("similar_jobs", self._similar_jobs_node)
        graph.set_entry_point("source_intake")
        graph.add_edge("source_intake", "requirements")
        graph.add_edge("requirements", "matcher")
        graph.add_edge("matcher", "tailorer")
        graph.add_edge("tailorer", "reviewer")
        graph.add_edge("reviewer", "similar_jobs")
        graph.add_edge("similar_jobs", END)
        return graph.compile()

    @traceable(
        name="job_application_graph_run",
        run_type="chain",
        tags=["job-application", "langgraph"],
        process_inputs=summarize_graph_run_inputs,
        process_outputs=summarize_graph_run_outputs,
    )
    async def run(self, request: JobApplicationRequest) -> ApplicationResult:
        run_id = uuid4().hex[:12]
        set_langsmith_metadata(
            run_id=run_id,
            environment=self.settings.environment,
            company=request.company,
            role=request.role,
            source_type=request.source_type.value,
            submission_channel=request.submission_channel.value,
            profile_id=request.profile.profile_id,
        )
        with track_run_duration():
            with self.tracker.run_context(self.settings.mlflow_experiment_name, run_name=f"job-app-{run_id}"):
                await asyncio.to_thread(self.tracker.log_request, request)
                final_state = await self.graph.ainvoke(
                    {
                        "run_id": run_id,
                        "request": request,
                        "status": RunStatus.queued,
                        "stage_summaries": [],
                        "metrics": {},
                    },
                    config={
                        "tags": ["job-application", self.settings.environment],
                        "metadata": {
                            "run_id": run_id,
                            "environment": self.settings.environment,
                            "company": request.company,
                            "role": request.role,
                            "source_type": request.source_type.value,
                            "submission_channel": request.submission_channel.value,
                            "profile_id": request.profile.profile_id,
                        },
                    },
                )

        artifacts = await asyncio.to_thread(self.exporter.export, run_id, final_state.get("artifacts", []))
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
            similar_jobs=final_state.get("similar_jobs", []),
            artifacts=artifacts,
            approval_packet=final_state.get("approval_packet"),
            stage_summaries=final_state.get("stage_summaries", []),
            metrics=final_state.get("metrics", {}),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.repository.save_result(result)
        await asyncio.to_thread(self.tracker.log_result, result)
        job_application_runs_total.labels(status=result.status.value).inc()
        return result

    @traceable(
        name="node.similar_jobs_refresh",
        run_type="tool",
        tags=["job-application", "similar-jobs"],
        process_inputs=summarize_similar_refresh_inputs,
        process_outputs=summarize_graph_run_outputs,
    )
    async def discover_similar_jobs(self, result: ApplicationResult, limit: int | None = None) -> ApplicationResult:
        start = perf_counter()
        with track_graph_node_duration("similar_jobs_refresh"):
            requested_limit = max(1, limit or result.request.similar_job_limit or 5)
            set_langsmith_metadata(
                run_id=result.run_id,
                company=result.opportunity.company,
                role=result.opportunity.role,
                requested_limit=requested_limit,
                source_domain=result.opportunity.source_name,
            )
            matches = await self.tools.find_similar_jobs(
                opportunity=result.opportunity,
                requirements=result.requirements,
                limit=requested_limit,
            )
        summary = (
            f"Found {len(matches)} similar jobs scored at or above {self.settings.similar_job_min_score}% similarity."
            if matches
            else f"No similar jobs cleared the {self.settings.similar_job_min_score}% similarity threshold."
        )
        stage_summaries = list(result.stage_summaries) + [
            AgentStageSummary(
                stage="similar_jobs",
                summary=summary,
                duration_seconds=round(perf_counter() - start, 3),
            )
        ]
        metrics = dict(result.metrics)
        metrics["similar_job_count"] = float(len(matches))
        metrics["similar_job_refresh_in_progress"] = 0.0
        metrics["similar_job_refresh_failed"] = 0.0
        metrics["similar_job_refresh_duration_seconds"] = round(perf_counter() - start, 3)
        request = result.request.model_copy(
            update={
                "discover_similar_jobs": True,
                "similar_job_limit": requested_limit,
            }
        )
        updated = result.model_copy(
            update={
                "request": request,
                "similar_jobs": matches,
                "stage_summaries": stage_summaries,
                "metrics": metrics,
                "updated_at": datetime.utcnow(),
            }
        )
        self.repository.save_result(updated)
        await asyncio.to_thread(self.tracker.log_result, updated)
        return updated

    def queue_similar_jobs_refresh(self, result: ApplicationResult, limit: int | None = None) -> ApplicationResult:
        requested_limit = max(1, limit or result.request.similar_job_limit or 5)
        stage_summaries = list(result.stage_summaries) + [
            AgentStageSummary(
                stage="similar_jobs",
                summary="Similar-job discovery is running in the background.",
                duration_seconds=0,
            )
        ]
        metrics = dict(result.metrics)
        metrics["similar_job_refresh_in_progress"] = 1.0
        metrics["similar_job_refresh_failed"] = 0.0
        request = result.request.model_copy(
            update={
                "discover_similar_jobs": True,
                "similar_job_limit": requested_limit,
            }
        )
        updated = result.model_copy(
            update={
                "request": request,
                "stage_summaries": stage_summaries,
                "metrics": metrics,
                "updated_at": datetime.utcnow(),
            }
        )
        self.repository.save_result(updated)
        return updated

    def mark_similar_jobs_refresh_failed(
        self,
        result: ApplicationResult,
        error: str,
        limit: int | None = None,
    ) -> ApplicationResult:
        requested_limit = max(1, limit or result.request.similar_job_limit or 5)
        stage_summaries = list(result.stage_summaries) + [
            AgentStageSummary(
                stage="similar_jobs",
                summary=f"Similar-job discovery failed: {error}",
                duration_seconds=0,
            )
        ]
        metrics = dict(result.metrics)
        metrics["similar_job_refresh_in_progress"] = 0.0
        metrics["similar_job_refresh_failed"] = 1.0
        request = result.request.model_copy(
            update={
                "discover_similar_jobs": True,
                "similar_job_limit": requested_limit,
            }
        )
        updated = result.model_copy(
            update={
                "request": request,
                "stage_summaries": stage_summaries,
                "metrics": metrics,
                "updated_at": datetime.utcnow(),
            }
        )
        self.repository.save_result(updated)
        return updated

    @traceable(
        name="node.source_intake",
        run_type="chain",
        tags=["job-application", "langgraph-node"],
        process_inputs=summarize_workflow_node_inputs,
        process_outputs=summarize_workflow_node_outputs,
    )
    @instrument_graph_node("source_intake")
    async def _source_intake_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        request = state["request"]
        set_langsmith_metadata(
            run_id=state.get("run_id"),
            node="source_intake",
            source_type=request.source_type.value,
            submission_channel=request.submission_channel.value,
            source_name=request.source_name,
        )
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

    @traceable(
        name="node.requirements",
        run_type="chain",
        tags=["job-application", "langgraph-node"],
        process_inputs=summarize_workflow_node_inputs,
        process_outputs=summarize_workflow_node_outputs,
    )
    @instrument_graph_node("requirements")
    async def _requirements_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        set_langsmith_metadata(run_id=state.get("run_id"), node="requirements")
        requirements = await self.tools.extract_requirements(state["opportunity"].normalized_description)
        return {
            "requirements": requirements,
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="requirements", summary="Extracted structured requirements from the job description.", duration_seconds=round(perf_counter() - start, 3))],
        }

    @traceable(
        name="node.matcher",
        run_type="chain",
        tags=["job-application", "langgraph-node"],
        process_inputs=summarize_workflow_node_inputs,
        process_outputs=summarize_workflow_node_outputs,
    )
    @instrument_graph_node("matcher")
    async def _matcher_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        assessment = await asyncio.to_thread(
            self.agents.match,
            state["request"].profile,
            state["opportunity"],
            state["requirements"],
        )
        set_langsmith_metadata(
            run_id=state.get("run_id"),
            node="matcher",
            overall_score=assessment.overall_score,
            decision=assessment.decision,
            ready_for_tailoring=assessment.ready_for_tailoring,
        )
        status = RunStatus.matching if assessment.ready_for_tailoring else RunStatus.blocked
        return {
            "assessment": assessment,
            "status": status,
            "metrics": {"overall_score": float(assessment.overall_score)},
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="matcher", summary=f"Computed fit score {assessment.overall_score}% with decision {assessment.decision}.", duration_seconds=round(perf_counter() - start, 3))],
        }

    @traceable(
        name="node.tailorer",
        run_type="chain",
        tags=["job-application", "langgraph-node"],
        process_inputs=summarize_workflow_node_inputs,
        process_outputs=summarize_workflow_node_outputs,
    )
    @instrument_graph_node("tailorer")
    async def _tailorer_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        artifacts: list[GeneratedArtifact] = []
        status = state.get("status", RunStatus.blocked)
        if state["assessment"].ready_for_tailoring:
            artifacts = await asyncio.to_thread(
                self.agents.generate_artifacts,
                state["request"].profile,
                state["opportunity"],
                state["requirements"],
                state["assessment"],
            )
            status = RunStatus.tailoring
        set_langsmith_metadata(
            run_id=state.get("run_id"),
            node="tailorer",
            artifact_count=len(artifacts),
            status=status.value,
        )
        return {
            "artifacts": artifacts,
            "status": status,
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="tailorer", summary="Generated tailored artifacts." if artifacts else "Skipped artifact generation because the role did not clear the gate.", duration_seconds=round(perf_counter() - start, 3))],
        }

    @traceable(
        name="node.reviewer",
        run_type="chain",
        tags=["job-application", "langgraph-node"],
        process_inputs=summarize_workflow_node_inputs,
        process_outputs=summarize_workflow_node_outputs,
    )
    @instrument_graph_node("reviewer")
    async def _reviewer_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        packet = await asyncio.to_thread(
            self.agents.review,
            state["opportunity"],
            state["assessment"],
            state.get("artifacts", []),
        )
        status = RunStatus.awaiting_approval if state["assessment"].ready_for_tailoring else RunStatus.blocked
        set_langsmith_metadata(
            run_id=state.get("run_id"),
            node="reviewer",
            status=status.value,
            risk_count=len(packet.risks),
        )
        return {
            "approval_packet": packet,
            "status": status,
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="reviewer", summary=packet.summary, duration_seconds=round(perf_counter() - start, 3))],
        }

    @traceable(
        name="node.similar_jobs",
        run_type="chain",
        tags=["job-application", "langgraph-node"],
        process_inputs=summarize_workflow_node_inputs,
        process_outputs=summarize_workflow_node_outputs,
    )
    @instrument_graph_node("similar_jobs")
    async def _similar_jobs_node(self, state: ApplicationState) -> ApplicationState:
        start = perf_counter()
        request = state["request"]
        set_langsmith_metadata(
            run_id=state.get("run_id"),
            node="similar_jobs",
            enabled=request.discover_similar_jobs,
            limit=request.similar_job_limit,
        )
        if not request.discover_similar_jobs:
            return {
                "similar_jobs": [],
                "stage_summaries": state.get("stage_summaries", [])
                + [
                    AgentStageSummary(
                        stage="similar_jobs",
                        summary="Skipped similar-job discovery because the option was not enabled.",
                        duration_seconds=round(perf_counter() - start, 3),
                    )
                ],
            }

        matches = await self.tools.find_similar_jobs(
            opportunity=state["opportunity"],
            requirements=state["requirements"],
            limit=request.similar_job_limit,
        )
        summary = (
            f"Found {len(matches)} similar jobs scored at or above 80% similarity."
            if matches
            else "No similar jobs cleared the 80% similarity threshold."
        )
        metrics = dict(state.get("metrics", {}))
        metrics["similar_job_count"] = float(len(matches))
        return {
            "similar_jobs": matches,
            "metrics": metrics,
            "stage_summaries": state.get("stage_summaries", [])
            + [AgentStageSummary(stage="similar_jobs", summary=summary, duration_seconds=round(perf_counter() - start, 3))],
        }
