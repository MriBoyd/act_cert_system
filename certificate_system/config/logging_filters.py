from __future__ import annotations

import logging

from config.request_context import get_request_context


class RequestContextFilter(logging.Filter):
    """Inject request context fields into each LogRecord.

    The formatter can safely reference these fields.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        ctx = get_request_context()

        record.request_id = ctx.request_id
        record.user_id = ctx.user_id
        record.username = ctx.username
        record.ip = ctx.ip
        record.method = ctx.method
        record.path = ctx.path

        return True
