from __future__ import annotations

from typing import Optional, Tuple

from django.utils import timezone
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from apps.users.models import ApiKey


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate requests using a scoped API key.

    Supported headers:

    - `Authorization: Api-Key <raw_key>`
    - `X-API-Key: <raw_key>`

    On success:

    - `request.user` is the ApiKey's user
    - `request.auth` is the ApiKey instance
    """

    keyword = "Api-Key"

    def authenticate_header(self, request) -> str:
        # Providing this header allows DRF to return 401 (instead of 403)
        # for NotAuthenticated/AuthenticationFailed cases.
        return self.keyword

    def authenticate(self, request) -> Optional[Tuple[object, ApiKey]]:
        raw_key = self._get_raw_key(request)
        if not raw_key:
            return None

        key_hash = ApiKey.hash_raw_key(raw_key)
        try:
            api_key = ApiKey.objects.select_related("user").get(key_hash=key_hash)
        except ApiKey.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid API key.") from exc

        if not api_key.is_active or api_key.is_expired():
            raise AuthenticationFailed("API key disabled or expired.")

        # Best-effort last-used tracking (should never block the request)
        try:
            api_key.last_used_at = timezone.now()
            api_key.last_used_ip = self._get_ip(request)
            api_key.save(update_fields=["last_used_at", "last_used_ip", "updated_at"])
        except Exception:  # noqa: BLE001
            pass

        return api_key.user, api_key

    def _get_raw_key(self, request) -> str:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header:
            parts = auth_header.split(" ", 1)
            if len(parts) == 2 and parts[0] == self.keyword:
                return parts[1].strip()

        return (request.META.get("HTTP_X_API_KEY") or "").strip()

    def _get_ip(self, request) -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR") or ""
