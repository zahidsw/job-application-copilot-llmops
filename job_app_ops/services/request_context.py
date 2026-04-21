from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class RequestContext:
    request_id: str
    tenant_id: str
    traceparent: str


_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def build_request_context(tenant_id: str, request_id: str | None = None, traceparent: str | None = None) -> RequestContext:
    return RequestContext(
        request_id=request_id or uuid4().hex,
        tenant_id=tenant_id,
        traceparent=traceparent or f"00-{uuid4().hex}-{uuid4().hex[:16]}-01",
    )


def set_request_context(context: RequestContext):
    return _request_context.set(context)


def reset_request_context(token) -> None:
    _request_context.reset(token)


def current_request_context() -> RequestContext | None:
    return _request_context.get()
