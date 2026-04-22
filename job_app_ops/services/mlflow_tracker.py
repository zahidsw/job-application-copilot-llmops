from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from job_app_ops.config import Settings
from job_app_ops.schemas import ApplicationResult, JobApplicationRequest

try:
    import mlflow
except Exception:  # pragma: no cover
    mlflow = None


logger = logging.getLogger(__name__)


class MLflowTracker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = bool(settings.mlflow_enabled and mlflow is not None)
        if self.enabled:
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    @contextmanager
    def run_context(self, experiment_name: str, run_name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        active_run = mlflow.active_run()
        if active_run is not None:
            mlflow.end_run(status="KILLED")
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=run_name):
            yield

    def log_request(self, request: JobApplicationRequest) -> None:
        if not self.enabled:
            return
        try:
            mlflow.log_params(
                {
                    "company": request.company,
                    "role": request.role,
                    "source_type": request.source_type.value,
                    "submission_channel": request.submission_channel.value,
                }
            )
        except Exception:  # pragma: no cover
            logger.exception("Failed to log request details to MLflow.")

    def log_result(self, result: ApplicationResult) -> None:
        if not self.enabled:
            return
        try:
            if mlflow.active_run() is None:
                mlflow.set_experiment(self.settings.mlflow_experiment_name)
                with mlflow.start_run(run_name=f"{result.run_id}-{result.status.value}"):
                    self._log_result_metrics(result)
                    self._log_result_tags(result)
                return

            self._log_result_metrics(result)
            self._log_result_tags(result)
        except Exception:  # pragma: no cover
            logger.exception("Failed to log result details to MLflow for run %s.", result.run_id)

    def _log_result_metrics(self, result: ApplicationResult) -> None:
        mlflow.log_metrics(
            {
                "overall_score": result.assessment.overall_score,
                "artifact_count": float(len(result.artifacts)),
                "blocked": 1.0 if result.status.value == "blocked" else 0.0,
            }
        )

    def _log_result_tags(self, result: ApplicationResult) -> None:
        mlflow.set_tags(
            {
                "run_id": result.run_id,
                "status": result.status.value,
                "company": result.opportunity.company,
                "role": result.opportunity.role,
            }
        )
