from apps.certificates.feature_flags import DEFAULT_FLAGS, is_feature_enabled


def feature_flags_context(request):
    return {
        "feature_flags": {
            name: is_feature_enabled(name)
            for name in DEFAULT_FLAGS
        }
    }
