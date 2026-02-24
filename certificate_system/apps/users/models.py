import uuid
import hashlib
import secrets

from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        CERTIFICATE_ADMIN = "CERTIFICATE_ADMIN", "Certificate Admin"
        VIEWER = "VIEWER", "Viewer"

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.VIEWER)
    is_verified_issuer = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["public_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"


class ApiKey(models.Model):
    """API key for integrating external platforms.

    Store only a hash of the raw key. The raw key is shown once at creation time
    (e.g., via management command).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="api_keys",
    )

    prefix = models.CharField(max_length=16, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["prefix", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}…){'' if self.is_active else ' [disabled]'}"

    @staticmethod
    def generate_raw_key() -> str:
        # URL-safe, long enough to prevent guessing.
        return f"act_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_raw_key(raw_key: str) -> str:
        # Pepper with SECRET_KEY to reduce risk if DB leaks.
        payload = f"{settings.SECRET_KEY}:{raw_key}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def create_with_raw_key(
        cls,
        *,
        name: str,
        user: User,
        scopes: list[str] | None = None,
        expires_at=None,
    ) -> tuple["ApiKey", str]:
        raw_key = cls.generate_raw_key()
        api_key = cls.objects.create(
            name=name,
            user=user,
            prefix=raw_key[:12],
            key_hash=cls.hash_raw_key(raw_key),
            scopes=list(scopes or []),
            expires_at=expires_at,
            is_active=True,
        )
        return api_key, raw_key

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def verify(self, raw_key: str) -> bool:
        return secrets.compare_digest(self.key_hash, self.hash_raw_key(raw_key))
