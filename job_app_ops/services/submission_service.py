from __future__ import annotations

from datetime import datetime
from pathlib import Path

from job_app_ops.config import Settings
from job_app_ops.schemas import ApplicationResult, RunStatus, SubmissionChannel, SubmissionRecord
from job_app_ops.services.metrics import job_application_submissions_total


class SubmissionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def approve(self, result: ApplicationResult, send_email_now: bool = False) -> ApplicationResult:
        packet_dir = self.settings.reports_dir / result.run_id
        packet_dir.mkdir(parents=True, exist_ok=True)

        if result.request.submission_channel == SubmissionChannel.email:
            packet = packet_dir / "email-dispatch.md"
            packet.write_text(
                f"# Email Dispatch\n\nTo: {result.request.destination}\n\nArtifacts:\n" +
                "\n".join(f"- {artifact.path or artifact.file_name}" for artifact in result.artifacts),
                encoding="utf-8",
            )
            status = "email_draft_prepared"
            if send_email_now and self.settings.smtp_host and self.settings.smtp_from:
                status = "email_ready_for_transport"
            submission = SubmissionRecord(
                channel=SubmissionChannel.email,
                status=status,
                destination=result.request.destination,
                dispatch_summary="Prepared an email application packet.",
                evidence=str(packet),
            )
            final_status = RunStatus.submitted
        elif result.request.submission_channel == SubmissionChannel.company_site:
            packet = packet_dir / "company-site-packet.md"
            packet.write_text(
                f"# Company Site Packet\n\nDestination: {result.request.destination}\n\nApproval packet ready for operator-guided submission.",
                encoding="utf-8",
            )
            submission = SubmissionRecord(
                channel=SubmissionChannel.company_site,
                status="company_site_packet_prepared",
                destination=result.request.destination,
                dispatch_summary="Prepared a company-site submission packet.",
                evidence=str(packet),
            )
            final_status = RunStatus.submitted
        else:
            packet = packet_dir / "manual-handoff.md"
            packet.write_text(
                f"# Manual Handoff\n\nDestination: {result.request.destination}\n\nUse this packet for LinkedIn / Indeed manual submission.",
                encoding="utf-8",
            )
            submission = SubmissionRecord(
                channel=SubmissionChannel.manual_handoff,
                status="manual_handoff_prepared",
                destination=result.request.destination,
                dispatch_summary="Prepared a manual handoff packet.",
                evidence=str(packet),
            )
            final_status = RunStatus.manual_handoff

        job_application_submissions_total.labels(channel=submission.channel.value, status=submission.status).inc()
        return result.model_copy(update={"status": final_status, "submission_record": submission, "updated_at": datetime.utcnow()})

    def reject(self, result: ApplicationResult, reason: str) -> ApplicationResult:
        submission = SubmissionRecord(
            channel=result.request.submission_channel,
            status="rejected_by_operator",
            destination=result.request.destination,
            dispatch_summary=reason,
            evidence="No dispatch executed.",
        )
        return result.model_copy(update={"status": RunStatus.rejected, "submission_record": submission, "updated_at": datetime.utcnow()})
