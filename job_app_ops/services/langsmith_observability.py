from __future__ import annotations

import os
from typing import Any, Callable
from urllib.parse import urlparse

from job_app_ops.config import Settings

try:  # pragma: no cover - exercised when LangSmith is installed and enabled.
    from langsmith import set_run_metadata as _set_run_metadata
    from langsmith import traceable as _langsmith_traceable
except Exception:  # pragma: no cover - keeps local/offline runs dependency-tolerant.
    _set_run_metadata = None
    _langsmith_traceable = None


SENSITIVE_TEXT_KEYS = {
    "content",
    "description",
    "job_text",
    "normalized_description",
    "raw_html",
    "reference_texts",
    "system_prompt",
    "user_prompt",
}

SECRET_KEYS = {
    "api_key",
    "authorization",
    "client_secret",
    "llm_api_key",
    "password",
    "secret",
    "smtp_password",
    "token",
}


def configure_langsmith(settings: Settings, *, service_name: str) -> None:
    """Configure LangSmith through environment variables before LangGraph runs."""

    enabled = bool(settings.langsmith_tracing and settings.langsmith_api_key.strip())
    project = settings.langsmith_project.strip() or f"{settings.app_name}-{settings.environment}"

    os.environ["LANGSMITH_TRACING"] = str(enabled).lower()
    os.environ["LANGCHAIN_TRACING_V2"] = str(enabled).lower()
    os.environ["LANGSMITH_PROJECT"] = project
    os.environ["LANGCHAIN_PROJECT"] = project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if settings.langsmith_workspace_id.strip():
        os.environ["LANGSMITH_WORKSPACE_ID"] = settings.langsmith_workspace_id.strip()
    os.environ["LANGSMITH_HIDE_INPUTS"] = str(settings.langsmith_hide_inputs).lower()
    os.environ["LANGSMITH_HIDE_OUTPUTS"] = str(settings.langsmith_hide_outputs).lower()
    os.environ["LANGSMITH_SERVICE_NAME"] = service_name
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key


def traceable(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    if _langsmith_traceable is None:
        return lambda fn: fn
    return _langsmith_traceable(*args, **kwargs)


def set_langsmith_metadata(**metadata: Any) -> None:
    if _set_run_metadata is None or os.environ.get("LANGSMITH_TRACING", "false").lower() != "true":
        return
    try:
        _set_run_metadata(**_sanitize_value(metadata))
    except Exception:
        return


def summarize_graph_run_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    request = inputs.get("request")
    return {"request": _summarize_request(request)}


def summarize_graph_run_outputs(output: Any) -> dict[str, Any]:
    return {"result": _summarize_result(output)}


def summarize_similar_refresh_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "result": _summarize_result(inputs.get("result")),
        "limit": inputs.get("limit"),
    }


def summarize_workflow_node_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {"state": _summarize_state(inputs.get("state", {}))}


def summarize_workflow_node_outputs(output: Any) -> dict[str, Any]:
    return {"state_update": _summarize_state(output if isinstance(output, dict) else {})}


def summarize_remote_tool_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    payload = inputs.get("payload", {})
    return {
        "path": inputs.get("path"),
        "tool": inputs.get("tool"),
        "payload": _summarize_payload(payload),
    }


def summarize_remote_tool_outputs(output: Any) -> dict[str, Any]:
    if isinstance(output, list):
        return {
            "type": "list",
            "count": len(output),
            "items": [_summarize_payload(item) for item in output[:3]],
        }
    return {"response": _summarize_payload(output)}


def summarize_llm_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    client = inputs.get("self")
    settings = getattr(client, "settings", None)
    system_prompt = str(inputs.get("system_prompt", ""))
    user_prompt = str(inputs.get("user_prompt", ""))
    return {
        "provider": getattr(settings, "llm_provider", "unknown"),
        "model": getattr(settings, "llm_model", "unknown"),
        "temperature": getattr(settings, "llm_temperature", None),
        "max_tokens": inputs.get("max_tokens"),
        "system_prompt_chars": len(system_prompt),
        "user_prompt_chars": len(user_prompt),
    }


def summarize_llm_outputs(output: Any) -> dict[str, Any]:
    text = str(output or "")
    return {
        "output_chars": len(text),
        "has_output": bool(text.strip()),
    }


def _summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    request = state.get("request")
    opportunity = state.get("opportunity")
    requirements = state.get("requirements")
    assessment = state.get("assessment")
    artifacts = state.get("artifacts") or []
    similar_jobs = state.get("similar_jobs") or []

    return {
        "run_id": state.get("run_id"),
        "status": _enum_value(state.get("status")),
        "request": _summarize_request(request),
        "opportunity": _summarize_opportunity(opportunity),
        "requirements": _summarize_requirements(requirements),
        "assessment": _summarize_assessment(assessment),
        "artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
        "similar_job_count": len(similar_jobs) if isinstance(similar_jobs, list) else 0,
        "metrics": _sanitize_value(state.get("metrics", {})),
    }


def _summarize_result(result: Any) -> dict[str, Any]:
    return {
        "run_id": _get_value(result, "run_id"),
        "status": _enum_value(_get_value(result, "status")),
        "opportunity": _summarize_opportunity(_get_value(result, "opportunity")),
        "assessment": _summarize_assessment(_get_value(result, "assessment")),
        "artifact_count": len(_get_value(result, "artifacts") or []),
        "similar_job_count": len(_get_value(result, "similar_jobs") or []),
        "metrics": _sanitize_value(_get_value(result, "metrics") or {}),
    }


def _summarize_request(request: Any) -> dict[str, Any]:
    return {
        "profile_id": _get_nested_value(request, "profile", "profile_id") or _get_value(request, "profile_id"),
        "company": _get_value(request, "company"),
        "role": _get_value(request, "role"),
        "source_domain": _domain(_get_value(request, "source_url")),
        "source_type": _enum_value(_get_value(request, "source_type")),
        "submission_channel": _enum_value(_get_value(request, "submission_channel")),
        "job_text_chars": len(str(_get_value(request, "job_text") or "")),
        "discover_similar_jobs": _get_value(request, "discover_similar_jobs"),
        "similar_job_limit": _get_value(request, "similar_job_limit"),
    }


def _summarize_opportunity(opportunity: Any) -> dict[str, Any]:
    return {
        "company": _get_value(opportunity, "company"),
        "role": _get_value(opportunity, "role"),
        "source_name": _get_value(opportunity, "source_name"),
        "source_domain": _domain(_get_value(opportunity, "source_url")),
        "source_type": _enum_value(_get_value(opportunity, "source_type")),
        "submission_channel": _enum_value(_get_value(opportunity, "submission_channel")),
        "location_mode": _get_value(opportunity, "location_mode"),
        "location_hint": _get_value(opportunity, "location_hint"),
        "location_country": _get_value(opportunity, "location_country"),
        "source_approved": _get_value(opportunity, "source_approved"),
        "normalized_description_chars": len(str(_get_value(opportunity, "normalized_description") or "")),
    }


def _summarize_requirements(requirements: Any) -> dict[str, Any]:
    required = _get_value(requirements, "required_skills") or []
    preferred = _get_value(requirements, "preferred_skills") or []
    languages = _get_value(requirements, "language_requirements") or []
    blockers = _get_value(requirements, "hard_blockers") or []
    return {
        "required_skill_count": len(required),
        "preferred_skill_count": len(preferred),
        "language_count": len(languages),
        "hard_blocker_count": len(blockers),
        "required_skills": required[:12],
        "preferred_skills": preferred[:12],
    }


def _summarize_assessment(assessment: Any) -> dict[str, Any]:
    return {
        "overall_score": _get_value(assessment, "overall_score"),
        "decision": _get_value(assessment, "decision"),
        "ready_for_tailoring": _get_value(assessment, "ready_for_tailoring"),
        "missing_evidence_count": len(_get_value(assessment, "missing_evidence") or []),
        "hard_blocker_count": len(_get_value(assessment, "hard_blockers") or []),
    }


def _summarize_payload(payload: Any) -> Any:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    if isinstance(payload, dict):
        summarized: dict[str, Any] = {}
        for key, value in payload.items():
            normalized_key = key.lower()
            if any(secret_key in normalized_key for secret_key in SECRET_KEYS):
                summarized[key] = "[redacted]"
            elif normalized_key in SENSITIVE_TEXT_KEYS:
                summarized[f"{key}_chars"] = len(str(value or ""))
            elif normalized_key.endswith("url"):
                summarized[f"{key}_domain"] = _domain(str(value or ""))
            elif isinstance(value, dict):
                summarized[key] = _summarize_payload(value)
            elif isinstance(value, list):
                summarized[key] = [_summarize_payload(item) for item in value[:8]]
                summarized[f"{key}_count"] = len(value)
            else:
                summarized[key] = _sanitize_value(value)
        return summarized
    if isinstance(payload, list):
        return [_summarize_payload(item) for item in payload[:8]]
    return _sanitize_value(payload)


def _sanitize_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:20]]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value[:20]]
    if isinstance(value, str):
        if len(value) > 240:
            return f"{value[:120]}...<redacted {len(value) - 120} chars>"
        return value
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)


def _get_value(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _get_nested_value(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        current = _get_value(current, key)
        if current is None:
            return None
    return current


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _domain(url: Any) -> str:
    if not url:
        return ""
    parsed = urlparse(str(url))
    return parsed.netloc or parsed.path.split("/", 1)[0]
