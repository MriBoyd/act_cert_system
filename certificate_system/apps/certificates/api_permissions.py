from __future__ import annotations

from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

from apps.users.models import ApiKey


class ApiKeyAuthenticated(BasePermission):
    """Require ApiKeyAuthentication to succeed.

    If no API key is provided, raise 401 (NotAuthenticated).
    """

    def has_permission(self, request, view) -> bool:
        api_key = getattr(request, "auth", None)
        if not isinstance(api_key, ApiKey):
            raise NotAuthenticated("API key required.")
        return True


class HasApiKeyScope(BasePermission):
    """Require a scope on the authenticated ApiKey.

    Use per-view via:

    - `required_scopes = ["scope:a", "scope:b"]`

    The request must be authenticated via ApiKeyAuthentication.
    """

    required_scopes: list[str] = []

    def has_permission(self, request, view) -> bool:
        api_key = getattr(request, "auth", None)
        if not isinstance(api_key, ApiKey):
            return False

        required = getattr(view, "required_scopes", None) or self.required_scopes
        if not required:
            return True

        scopes = set(api_key.scopes or [])
        return all(scope in scopes for scope in required)
