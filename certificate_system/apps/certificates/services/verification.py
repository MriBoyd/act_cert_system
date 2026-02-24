import uuid

import logging

from apps.certificates.models import Certificate, VerificationLog

audit_logger = logging.getLogger("audit")


def _extract_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def verify_certificate(certificate_uuid: uuid.UUID, request):
    certificate = Certificate.objects.filter(id=certificate_uuid).select_related("template").first()
    is_valid = bool(certificate and certificate.is_verifiable)

    VerificationLog.objects.create(
        certificate=certificate,
        certificate_uuid=certificate_uuid,
        requester_ip=_extract_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1024],
        is_valid=is_valid,
    )

    audit_logger.info(
        "event=certificate_verification_attempt certificate_uuid=%s valid=%s",
        certificate_uuid,
        is_valid,
    )

    return certificate, is_valid
