from __future__ import annotations

import base64
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.certificates.models import Certificate, CertificateTemplate
from apps.users.models import User


_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)


def make_image(name: str = "bg.png") -> SimpleUploadedFile:
    # Prefer generating a known-valid image (used by DRF ImageField validation)
    # but keep a fallback for environments without Pillow.
    try:
        from PIL import Image  # type: ignore
        import io

        img = Image.new("RGB", (1, 1), (255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return SimpleUploadedFile(name, buf.read(), content_type="image/png")
    except Exception:  # noqa: BLE001
        return SimpleUploadedFile(name, _PNG_1X1, content_type="image/png")


def make_admin_user(
    *,
    username: str = "admin",
    password: str = "pass12345",
    is_superuser: bool = True,
) -> User:
    if is_superuser:
        return User.objects.create_superuser(username=username, password=password)

    user = User.objects.create_user(username=username, password=password)
    user.is_staff = True
    user.role = User.Role.CERTIFICATE_ADMIN
    user.save(update_fields=["is_staff", "role"])
    return user


def make_template(*, name: str = "Template 1", issuer: str = "Issuer") -> CertificateTemplate:
    return CertificateTemplate.objects.create(
        name=name,
        issuer_name=issuer,
        background_image=make_image(),
        dynamic_fields=[],
        is_active=True,
    )


def make_certificate(
    *,
    template: CertificateTemplate,
    issued_by: User,
    serial_number: str = "SN-001",
    recipient_name: str | None = None,
) -> Certificate:
    if recipient_name is None:
        recipient_name = f"Recipient {serial_number}"
    return Certificate.objects.create(
        template=template,
        recipient_name=recipient_name,
        recipient_email="john@example.com",
        course_name="Course",
        issue_date=date(2025, 1, 1),
        serial_number=serial_number,
        status=Certificate.Status.VALID,
        is_enabled=True,
        fingerprint="",
        issued_by=issued_by,
    )
