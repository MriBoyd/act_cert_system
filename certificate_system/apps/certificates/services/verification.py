import uuid

import logging

from apps.certificates.models import Certificate, VerificationLog

audit_logger = logging.getLogger("audit")
access_logger = logging.getLogger("access")


def _extract_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def verify_certificate(certificate_uuid: uuid.UUID, request, track=True, source=VerificationLog.Source.SEARCH):
    certificate = Certificate.objects.filter(id=certificate_uuid).select_related("template").first()
    is_valid = bool(certificate and certificate.is_verifiable)

    if track:
        VerificationLog.objects.create(
            certificate=certificate,
            certificate_uuid=certificate_uuid,
            requester_ip=_extract_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:1024],
            is_valid=is_valid,
            source=source,
        )

        audit_logger.info(
            "event=certificate_verification_attempt certificate_uuid=%s valid=%s source=%s",
            certificate_uuid,
            is_valid,
            source,
        )

        access_logger.info(
            "event=access_recorded certificate_uuid=%s source=%s ip=%s",
            certificate_uuid,
            source,
            _extract_ip(request),
        )

    return certificate, is_valid
