from __future__ import annotations

from contextlib import contextmanager

from job_app_ops.config import Settings
from job_app_ops.schemas import (
    ApplicationResult,
    ApprovalPacket,
    CandidateProfile,
    JobApplicationRequest,
    JobOpportunity,
    JobRequirements,
    JobSourceType,
    MatchAssessment,
    RunStatus,
    SubmissionChannel,
)
from job_app_ops.services import mlflow_tracker
from job_app_ops.services.mlflow_tracker import MLflowTracker


class FakeMlflow:
    def __init__(self) -> None:
        self._active_run = None
        self.experiments: list[str] = []
        self.started_run_names: list[str] = []
        self.logged_metrics: list[dict[str, float]] = []
        self.logged_tags: list[dict[str, str]] = []
        self.tracking_uris: list[str] = []

    def set_tracking_uri(self, uri: str) -> None:
        self.tracking_uris.append(uri)

    def active_run(self):
        return self._active_run

    def set_experiment(self, name: str) -> None:
        self.experiments.append(name)

    @contextmanager
    def start_run(self, run_name: str):
        self.started_run_names.append(run_name)
        self._active_run = {"run_name": run_name}
        try:
            yield self._active_run
        finally:
            self._active_run = None

    def log_metrics(self, metrics: dict[str, float]) -> None:
        self.logged_metrics.append(metrics)

    def set_tags(self, tags: dict[str, str]) -> None:
        self.logged_tags.append(tags)


def test_log_result_creates_ad_hoc_mlflow_run_when_none_is_active(monkeypatch):
    fake_mlflow = FakeMlflow()
    monkeypatch.setattr(mlflow_tracker, "mlflow", fake_mlflow)

    settings = Settings(mlflow_enabled=True, mlflow_tracking_uri="http://mlflow:5000")
    tracker = MLflowTracker(settings)
    result = ApplicationResult(
        run_id="run-123",
        status=RunStatus.awaiting_approval,
        request=JobApplicationRequest(profile=CandidateProfile(), company="Example AG", role="Platform Engineer"),
        opportunity=JobOpportunity(
            company="Example AG",
            role="Platform Engineer",
            source_name="example.com",
            source_url="https://example.com/jobs/platform",
            source_type=JobSourceType.company_site,
            destination="https://example.com/jobs/platform",
            submission_channel=SubmissionChannel.company_site,
            normalized_description="Platform engineer with Python and observability.",
        ),
        requirements=JobRequirements(required_skills=["Python"]),
        assessment=MatchAssessment(overall_score=88, decision="ready_to_tailor", ready_for_tailoring=True),
        approval_packet=ApprovalPacket(
            summary="Ready for approval.",
            exact_action_after_approval="Prepare the company-site packet.",
        ),
    )

    tracker.log_result(result)

    assert fake_mlflow.tracking_uris == ["http://mlflow:5000"]
    assert fake_mlflow.experiments == [settings.mlflow_experiment_name]
    assert fake_mlflow.started_run_names == ["run-123-awaiting_approval"]
    assert fake_mlflow.logged_metrics[-1]["overall_score"] == 88
    assert fake_mlflow.logged_tags[-1]["run_id"] == "run-123"
    assert fake_mlflow.logged_tags[-1]["status"] == "awaiting_approval"
