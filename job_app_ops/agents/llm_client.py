from __future__ import annotations

from job_app_ops.config import Settings


class LLMClient:
    """Thin placeholder adapter for future provider-specific integration."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def backend_description(self) -> str:
        return f"{self.settings.llm_provider}:{self.settings.llm_model}"
