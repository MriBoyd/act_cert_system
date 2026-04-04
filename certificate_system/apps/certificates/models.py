import hashlib
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CertificateTemplate(models.Model):
    """Template stores background and dynamic field layout metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    issuer_name = models.CharField(max_length=255)
    course_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, help_text="Internal description of this template.")
    background_image = models.ImageField(upload_to="templates/backgrounds/")
    dynamic_fields = models.JSONField(
        default=list,
        help_text="List of field maps. Example: [{name, x, y, font_size}]",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.name


class Certificate(models.Model):
    class Status(models.TextChoices):
        VALID = "VALID", "Valid"
        REVOKED = "REVOKED", "Revoked"
        DISABLED = "DISABLED", "Disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.PROTECT,
        related_name="certificates",
    )
    recipient_name = models.CharField(max_length=255)
    recipient_email = models.EmailField(blank=True)
    course_name = models.CharField(max_length=255)
    issue_date = models.DateField()
    serial_number = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.VALID, db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)

    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    qr_code_image = models.ImageField(upload_to="certificates/qr/", blank=True)
    pdf_file = models.FileField(upload_to="certificates/pdf/", blank=True)
    png_file = models.FileField(upload_to="certificates/images/", blank=True)
    jpg_file = models.FileField(upload_to="certificates/images/", blank=True)

    logo_image = models.ImageField(upload_to="certificates/overlays/", blank=True)
    signature_image = models.ImageField(upload_to="certificates/overlays/", blank=True)

    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_certificates",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient_name"]),
            models.Index(fields=["course_name"]),
            models.Index(fields=["issue_date"]),
            models.Index(fields=["id", "status", "is_enabled"]),
        ]

    def clean(self) -> None:
        if self.status != self.Status.VALID and self.is_enabled:
            raise ValidationError("Certificate cannot be enabled unless it is VALID.")

    def save(self, *args, **kwargs):
        if not self.fingerprint:
            payload = (
                f"{self.template_id}|{self.recipient_name.strip().lower()}|"
                f"{self.course_name.strip().lower()}|{self.issue_date.isoformat()}"
            )
            self.fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)

    @property
    def is_verifiable(self) -> bool:
        return self.status == self.Status.VALID and self.is_enabled

    def __str__(self) -> str:
        return f"{self.recipient_name} - {self.course_name}"


class VerificationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate = models.ForeignKey(
        Certificate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_logs",
    )
    certificate_uuid = models.UUIDField(db_index=True)
    requester_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    is_valid = models.BooleanField(default=False, db_index=True)
    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["certificate_uuid", "checked_at"]),
            models.Index(fields=["is_valid", "checked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.certificate_uuid} ({'valid' if self.is_valid else 'invalid'})"


class FeatureFlagOverride(models.Model):
    """Database override for runtime feature flags.

    If an override exists for a flag name, it takes precedence over settings/env.
    Deleting the override reverts to the configured default.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=True, db_index=True)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feature_flag_updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name}={'on' if self.enabled else 'off'}"


class CertificateOverlayImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate = models.ForeignKey(
        Certificate,
        on_delete=models.CASCADE,
        related_name="overlay_images",
    )
    name = models.CharField(max_length=64, blank=True)
    image = models.ImageField(upload_to="certificates/overlays/")
    order = models.PositiveSmallIntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self) -> str:
        return f"{self.certificate_id}:{self.name or self.image.name}"
