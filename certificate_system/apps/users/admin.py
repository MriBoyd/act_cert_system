from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ApiKey, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "is_verified_issuer",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("role", "is_verified_issuer", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Certificate Controls",
            {
                "fields": (
                    "public_id",
                    "role",
                    "is_verified_issuer",
                )
            },
        ),
    )
    readonly_fields = ("public_id",)


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "prefix", "is_active", "expires_at", "last_used_at")
    list_filter = ("is_active",)
    search_fields = ("name", "user__username", "prefix")
    readonly_fields = (
        "id",
        "prefix",
        "key_hash",
        "created_at",
        "updated_at",
        "last_used_at",
        "last_used_ip",
    )

