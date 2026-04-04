import uuid

from django.shortcuts import render

from apps.certificates.feature_flags import is_feature_enabled, require_feature
from apps.certificates.models import Certificate, VerificationLog
from apps.certificates.services.verification import verify_certificate


@require_feature("public_verification")
def verification_home(request):
    context = {
        "result": None,
        "error": None,
        "show_animation": is_feature_enabled("verification_animation"),
    }

    if request.method == "POST":
        raw_certificate_id = request.POST.get("certificate_id", "").strip()
        try:
            certificate_uuid = uuid.UUID(raw_certificate_id)
            certificate, is_valid = verify_certificate(
                certificate_uuid, 
                request, 
                source=VerificationLog.Source.SEARCH
            )
            context["result"] = {
                "certificate": certificate,
                "is_valid": is_valid,
            }
            if not certificate:
                context["error"] = "Certificate not found."
        except ValueError:
            context["error"] = "Invalid certificate ID format."

    return render(request, "public/verify.html", context)


def verify_by_uuid(request, certificate_uuid):
    # Public viewing of the result page via direct URL/QR shouldn't 
    # count as a "Verification Request" (the POST search does that).
    # We set track=False to prevent duplicate/spoofed log entries on every page load.
    certificate, is_valid = verify_certificate(
        certificate_uuid, 
        request, 
        track=False, 
        source=VerificationLog.Source.QR_SCAN
    )
    return render(
        request,
        "public/verify_result.html",
        {
            "certificate": certificate,
            "is_valid": is_valid,
            "show_animation": is_feature_enabled("verification_animation"),
        },
    )


@require_feature("qr_scanner")
def qr_tools(request):
    return render(request, "public/qr_tools.html")
