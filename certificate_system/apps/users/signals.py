from __future__ import annotations

import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver


security_logger = logging.getLogger("security")
audit_logger = logging.getLogger("audit")


@receiver(user_logged_in)
def _on_user_logged_in(sender, request, user, **kwargs):  # noqa: ARG001
    username = user.get_username()
    security_logger.info("event=auth_login_success username=%s", username)
    audit_logger.info("event=auth_login_success username=%s", username)


@receiver(user_logged_out)
def _on_user_logged_out(sender, request, user, **kwargs):  # noqa: ARG001
    username = user.get_username()
    security_logger.info("event=auth_logout username=%s", username)
    audit_logger.info("event=auth_logout username=%s", username)


@receiver(user_login_failed)
def _on_user_login_failed(sender, credentials, request, **kwargs):  # noqa: ARG001
    attempted_username = ""
    if isinstance(credentials, dict):
        attempted_username = str(credentials.get("username") or credentials.get("email") or "")

    ip = ""
    if request is not None:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "")

    security_logger.warning(
        "event=auth_login_failed username=%s ip=%s",
        attempted_username,
        ip,
    )
    audit_logger.info(
        "event=auth_login_failed username=%s ip=%s",
        attempted_username,
        ip,
    )
