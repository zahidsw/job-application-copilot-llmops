from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "job-application-copilot-llmops"
    environment: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    mcp_port: int = 8081
    eval_port: int = 8090
    request_timeout_seconds: int = 30

    database_url: str = "sqlite:///./data/job_applications.db"
    artifacts_dir: Path = Path("data/artifacts")
    profiles_dir: Path = Path("data/profiles")
    reports_dir: Path = Path("data/reports")

    match_threshold: int = 70
    allowed_source_domains: str = "greenhouse.io,lever.co,workday.com,smartrecruiters.com,linkedin.com,indeed.com"
    manual_only_domains: str = "linkedin.com,indeed.com"
    similar_job_search_provider: str = "google_programmable_search"
    similar_job_min_score: int = 80
    google_programmable_search_api_key: str = ""
    google_programmable_search_cx: str = ""

    default_tenant_id: str = "local-dev"
    require_tenant_header: bool = False
    allowed_tenants: str = "local-dev"

    llm_provider: str = "openai_compatible"
    llm_base_url: str = "http://model:8000/v1"
    llm_api_key: str = "local"
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_json_mode: str = "json_object"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1400

    mcp_server_url: str = "http://mcp:8081"
    mcp_verify_ssl: bool = True
    mcp_client_service_name: str = "job-app-api"
    mcp_client_auth_token: str = "change-me-api-token"

    mlflow_enabled: bool = True
    mlflow_tracking_uri: str = "http://mlflow:5000"
    mlflow_experiment_name: str = "job-application-copilot"
    mlflow_eval_experiment_name: str = "job-application-copilot-evals"

    eval_dataset_path: Path = Path("ops/evals/golden_dataset.json")

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    company_site_auto_open: bool = False

    def ensure_paths(self) -> None:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @property
    def allowed_source_domain_set(self) -> set[str]:
        return {item.strip() for item in self.allowed_source_domains.split(",") if item.strip()}

    @property
    def manual_only_domain_set(self) -> set[str]:
        return {item.strip() for item in self.manual_only_domains.split(",") if item.strip()}

    @property
    def allowed_tenant_set(self) -> set[str]:
        return {item.strip() for item in self.allowed_tenants.split(",") if item.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_paths()
    return settings
