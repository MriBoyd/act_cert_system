from django.contrib import admin

from .models import Certificate, CertificateTemplate, VerificationLog

admin.site.site_header = "Certificate Platform Admin"
admin.site.site_title = "Certificate Admin"
admin.site.index_title = "Control Panel"


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "issuer_name", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "issuer_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient_name",
        "course_name",
        "serial_number",
        "status",
        "is_enabled",
        "issue_date",
        "created_at",
    )
    list_filter = ("status", "is_enabled", "issue_date")
    search_fields = ("recipient_name", "course_name", "serial_number", "id")
    readonly_fields = ("id", "fingerprint", "created_at", "updated_at")


@admin.register(VerificationLog)
class VerificationLogAdmin(admin.ModelAdmin):
    list_display = ("certificate_uuid", "is_valid", "requester_ip", "checked_at")
    list_filter = ("is_valid", "checked_at")
    search_fields = ("certificate_uuid", "requester_ip")
    readonly_fields = ("id", "checked_at")
