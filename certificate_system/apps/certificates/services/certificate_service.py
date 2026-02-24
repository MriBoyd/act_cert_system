from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.certificates.models import Certificate
from apps.certificates.services.image_generator import generate_certificate_image
from apps.certificates.services.pdf_generator import generate_certificate_pdf
from apps.certificates.services.qr_service import generate_qr_image


class DuplicateCertificateError(Exception):
    pass


@transaction.atomic
def create_certificate(*, template, issued_by, recipient_name, recipient_email, course_name, issue_date, serial_number):
    try:
        certificate = Certificate.objects.create(
            template=template,
            issued_by=issued_by,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            course_name=course_name,
            issue_date=issue_date,
            serial_number=serial_number,
            metadata={},
        )
    except IntegrityError as exc:
        raise DuplicateCertificateError(
            "Duplicate detected by serial number or certificate fingerprint."
        ) from exc

    verify_path = reverse("public-verify-detail", kwargs={"certificate_uuid": certificate.id})
    verification_url = f"{getattr(settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000')}{verify_path}"

    qr_image = generate_qr_image(verification_url=verification_url, cert_uuid=certificate.id)
    certificate.qr_code_image.save(qr_image.name, qr_image, save=False)

    pdf_file = generate_certificate_pdf(certificate)
    certificate.pdf_file.save(pdf_file.name, pdf_file, save=False)

    png_file = generate_certificate_image(certificate, fmt="PNG")
    certificate.png_file.save(png_file.name, png_file, save=False)

    jpg_file = generate_certificate_image(certificate, fmt="JPEG")
    certificate.jpg_file.save(jpg_file.name, jpg_file, save=False)

    certificate.save(update_fields=["qr_code_image", "pdf_file", "png_file", "jpg_file", "updated_at"])
    return certificate
