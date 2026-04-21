from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from job_app_ops.config import Settings
from job_app_ops.schemas import ApplicationResult, RunSummary


def _resolve_sqlite_path(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///")).resolve()
    return Path("data/job_applications.db").resolve()


def init_db(settings: Settings) -> None:
    path = _resolve_sqlite_path(settings.database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_runs(
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                score INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


class RunRepository:
    def __init__(self, settings: Settings) -> None:
        self._path = _resolve_sqlite_path(settings.database_url)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self._path)
        try:
            yield connection
        finally:
            connection.close()

    def healthcheck(self) -> None:
        with self._connect() as connection:
            connection.execute("SELECT 1")

    def save_result(self, result: ApplicationResult) -> None:
        payload = result.model_dump_json(indent=2)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO application_runs(run_id, status, company, role, score, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    company = excluded.company,
                    role = excluded.role,
                    score = excluded.score,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    result.run_id,
                    result.status.value,
                    result.opportunity.company,
                    result.opportunity.role,
                    result.assessment.overall_score,
                    payload,
                    result.created_at.isoformat(),
                    result.updated_at.isoformat(),
                ),
            )
            connection.commit()

    def get_result(self, run_id: str) -> ApplicationResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM application_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return ApplicationResult.model_validate_json(row[0])

    def list_recent(self, limit: int = 20) -> list[RunSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, status, company, role, score, updated_at
                FROM application_runs
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            RunSummary(
                run_id=row[0],
                status=row[1],
                company=row[2],
                role=row[3],
                score=row[4],
                updated_at=datetime.fromisoformat(row[5]),
            )
            for row in rows
        ]
