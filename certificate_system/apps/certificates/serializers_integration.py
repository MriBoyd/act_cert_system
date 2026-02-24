from __future__ import annotations

import json

from rest_framework import serializers

from apps.certificates.models import Certificate, CertificateTemplate


class IntegrationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = [
            "id",
            "name",
            "issuer_name",
            "is_active",
            "dynamic_fields",
            "created_at",
            "updated_at",
        ]


class IntegrationTemplateWriteSerializer(serializers.ModelSerializer):
    dynamic_fields = serializers.JSONField(required=False)

    class Meta:
        model = CertificateTemplate
        fields = [
            "id",
            "name",
            "issuer_name",
            "background_image",
            "dynamic_fields",
            "is_active",
        ]

    def validate_dynamic_fields(self, value):
        # Multipart form-data may provide JSON as a string.
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError("dynamic_fields must be valid JSON.") from exc
        return value


class IntegrationCertificateCreateSerializer(serializers.Serializer):
    template_id = serializers.UUIDField()
    recipient_name = serializers.CharField(max_length=255)
    recipient_email = serializers.EmailField(required=False, allow_blank=True)
    course_name = serializers.CharField(max_length=255)
    issue_date = serializers.DateField()
    serial_number = serializers.CharField(max_length=100)
    metadata = serializers.JSONField(required=False)

    def validate_template_id(self, template_id):
        try:
            template = CertificateTemplate.objects.get(id=template_id)
        except CertificateTemplate.DoesNotExist as exc:
            raise serializers.ValidationError("Template not found.") from exc

        if not template.is_active:
            raise serializers.ValidationError("Template is not active.")

        self.context["template"] = template
        return template_id


class IntegrationCertificateBulkItemSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(max_length=255)
    recipient_email = serializers.EmailField(required=False, allow_blank=True)
    course_name = serializers.CharField(max_length=255)
    issue_date = serializers.DateField()
    serial_number = serializers.CharField(max_length=100)
    metadata = serializers.JSONField(required=False)


class IntegrationCertificateSerializer(serializers.ModelSerializer):
    certificate_id = serializers.UUIDField(source="id", read_only=True)
    template_id = serializers.UUIDField(source="template.id", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    issuer_name = serializers.CharField(source="template.issuer_name", read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "certificate_id",
            "template_id",
            "template_name",
            "issuer_name",
            "recipient_name",
            "recipient_email",
            "course_name",
            "issue_date",
            "serial_number",
            "status",
            "is_enabled",
            "created_at",
            "updated_at",
        ]


class IntegrationCertificateStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = ["status", "is_enabled"]

    def validate(self, attrs):
        # Apply model validation rules (enabled requires VALID)
        instance = self.instance
        if instance is None:
            return attrs

        for k, v in attrs.items():
            setattr(instance, k, v)
        instance.clean()
        return attrs


class IntegrationCertificateUpdateSerializer(serializers.ModelSerializer):
    template_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = Certificate
        fields = [
            "template_id",
            "recipient_name",
            "recipient_email",
            "course_name",
            "issue_date",
            "serial_number",
            "status",
            "is_enabled",
            "metadata",
        ]

    def validate(self, attrs):
        instance = self.instance
        if instance is None:
            return attrs

        # Apply changes to instance and run model validation.
        if "template_id" in attrs:
            try:
                template = CertificateTemplate.objects.get(id=attrs["template_id"])
            except CertificateTemplate.DoesNotExist as exc:
                raise serializers.ValidationError({"template_id": "Template not found."}) from exc
            instance.template = template

        for k, v in attrs.items():
            if k == "template_id":
                continue
            setattr(instance, k, v)

        instance.clean()
        return attrs
