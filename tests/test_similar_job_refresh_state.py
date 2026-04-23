from __future__ import annotations

from job_app_ops.graph.workflow import JobApplicationWorkflow
from job_app_ops.schemas import (
    ApplicationResult,
    CandidateProfile,
    JobApplicationRequest,
    JobOpportunity,
    JobRequirements,
    JobSourceType,
    MatchAssessment,
    RunStatus,
    SubmissionChannel,
)


class FakeRepository:
    def __init__(self) -> None:
        self.saved_results: list[ApplicationResult] = []

    def save_result(self, result: ApplicationResult) -> None:
        self.saved_results.append(result)


def _workflow_with_fake_repository() -> tuple[JobApplicationWorkflow, FakeRepository]:
    repository = FakeRepository()
    workflow = JobApplicationWorkflow.__new__(JobApplicationWorkflow)
    workflow.repository = repository
    return workflow, repository


def _application_result() -> ApplicationResult:
    return ApplicationResult(
        run_id="run-123",
        status=RunStatus.awaiting_approval,
        request=JobApplicationRequest(
            profile=CandidateProfile(),
            company="Example AG",
            role="Platform Engineer",
            discover_similar_jobs=False,
        ),
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
    )


def test_queue_similar_jobs_refresh_marks_run_in_progress():
    workflow, repository = _workflow_with_fake_repository()

    updated = workflow.queue_similar_jobs_refresh(_application_result(), limit=3)

    assert updated.metrics["similar_job_refresh_in_progress"] == 1.0
    assert updated.metrics["similar_job_refresh_failed"] == 0.0
    assert updated.request.discover_similar_jobs is True
    assert updated.request.similar_job_limit == 3
    assert updated.stage_summaries[-1].summary == "Similar-job discovery is running in the background."
    assert repository.saved_results == [updated]


def test_mark_similar_jobs_refresh_failed_clears_in_progress_state():
    workflow, repository = _workflow_with_fake_repository()

    updated = workflow.mark_similar_jobs_refresh_failed(_application_result(), "provider timeout", limit=4)

    assert updated.metrics["similar_job_refresh_in_progress"] == 0.0
    assert updated.metrics["similar_job_refresh_failed"] == 1.0
    assert updated.request.similar_job_limit == 4
    assert "provider timeout" in updated.stage_summaries[-1].summary
    assert repository.saved_results == [updated]
