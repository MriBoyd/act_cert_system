from rest_framework import serializers

from .models import Certificate


class CertificateVerificationSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    issuer = serializers.CharField(source="template.issuer_name", read_only=True)
    certificate_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "certificate_id",
            "recipient_name",
            "course_name",
            "issuer",
            "issue_date",
            "status",
            "is_enabled",
            "template_name",
        ]
