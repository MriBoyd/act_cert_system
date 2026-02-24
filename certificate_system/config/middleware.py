from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin

from config.request_context import clear_request_context, set_request_context


class RequestContextMiddleware(MiddlewareMixin):
    """Attach a request id and request/user metadata to log records.

    - Sets/propagates `X-Request-ID`
    - Stores request context via `contextvars` for logging filters
    """

    def process_request(self, request):
        request_id = set_request_context(request)
        request.request_id = request_id

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None)
        if request_id:
            response.headers.setdefault("X-Request-ID", request_id)
        clear_request_context()
        return response

    def process_exception(self, request, exception):  # noqa: ARG002
        clear_request_context()
        return None
