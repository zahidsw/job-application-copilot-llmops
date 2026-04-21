from __future__ import annotations

from job_app_ops.config import Settings
from job_app_ops.schemas import GeneratedArtifact
from job_app_ops.services.document_renderer import DocumentRenderer


class ArtifactExporter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._renderer = DocumentRenderer()

    def export(self, run_id: str, artifacts: list[GeneratedArtifact]) -> list[GeneratedArtifact]:
        run_dir = self.settings.artifacts_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        exported: list[GeneratedArtifact] = []
        for artifact in artifacts:
            target = run_dir / artifact.file_name
            target.write_text(artifact.content, encoding="utf-8")
            persisted = artifact.model_copy(update={"path": str(target)})
            exported.append(persisted)
            exported.extend(self._renderer.render_derivatives(persisted, target))
        return exported
