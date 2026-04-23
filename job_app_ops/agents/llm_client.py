from __future__ import annotations

import httpx

from job_app_ops.config import Settings
from job_app_ops.services.langsmith_observability import summarize_llm_inputs, summarize_llm_outputs, traceable


class LLMClient:
    """Small OpenAI-compatible chat client with safe fallback semantics."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def backend_description(self) -> str:
        return f"{self.settings.llm_provider}:{self.settings.llm_model}"

    @property
    def is_configured(self) -> bool:
        key = (self.settings.llm_api_key or "").strip()
        base_url = (self.settings.llm_base_url or "").strip()
        return bool(base_url and key and key.lower() not in {"local", "change-me", "change-me-api-token"})

    @traceable(
        name="llm.generate_markdown",
        run_type="llm",
        tags=["job-application", "llm"],
        process_inputs=summarize_llm_inputs,
        process_outputs=summarize_llm_outputs,
    )
    def generate_markdown(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        if not self.is_configured:
            return ""

        endpoint = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.llm_temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}

        try:
            with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception:
            return ""

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""

        return content.strip()
