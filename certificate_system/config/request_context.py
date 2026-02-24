from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str = ""
    user_id: str = ""
    username: str = ""
    ip: str = ""
    method: str = ""
    path: str = ""


_request_context: ContextVar[RequestContext] = ContextVar(
    "request_context", default=RequestContext()
)


def _extract_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def set_request_context(request) -> str:
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

    user = getattr(request, "user", None)
    user_id = ""
    username = ""
    if user is not None and getattr(user, "is_authenticated", False):
        user_id = str(getattr(user, "id", ""))
        username = getattr(user, "get_username", lambda: "")() or getattr(user, "username", "")

    _request_context.set(
        RequestContext(
            request_id=request_id,
            user_id=user_id,
            username=username,
            ip=_extract_ip(request),
            method=getattr(request, "method", ""),
            path=getattr(request, "path", ""),
        )
    )

    return request_id


def clear_request_context() -> None:
    _request_context.set(RequestContext())


def get_request_context() -> RequestContext:
    return _request_context.get()
