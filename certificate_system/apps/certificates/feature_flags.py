from functools import wraps

from django.conf import settings
from django.http import Http404


def _db_override(flag_name: str) -> bool | None:
    try:
        from apps.certificates.models import FeatureFlagOverride

        override = (
            FeatureFlagOverride.objects.filter(name=flag_name)
            .values_list("enabled", flat=True)
            .first()
        )
        if override is None:
            return None
        return bool(override)
    except Exception:  # noqa: BLE001
        # If DB/migrations aren't ready yet, fall back to settings/env.
        return None


DEFAULT_FLAGS = {
    "admin_dashboard": True,
    "template_management": True,
    "certificate_generation": True,
    "bulk_generation": True,
    "certificate_management": True,
    "certificate_detail": True,
    "certificate_download": True,
    "public_verification": True,
    "qr_scanner": True,
    "verification_api": True,
    "verification_animation": True,
    "log_management": True,
    "integration_api": True,
}


def is_feature_enabled(flag_name: str) -> bool:
    if flag_name == "admin_dashboard":
        return True

    override = _db_override(flag_name)
    if override is not None:
        return override
    feature_flags = getattr(settings, "FEATURE_FLAGS", {})
    if flag_name in feature_flags:
        return bool(feature_flags.get(flag_name))
    return bool(DEFAULT_FLAGS.get(flag_name, False))


def require_feature(flag_name: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(*args, **kwargs):
            if not is_feature_enabled(flag_name):
                raise Http404("Feature not available")
            return view_func(*args, **kwargs)

        return _wrapped

    return decorator
