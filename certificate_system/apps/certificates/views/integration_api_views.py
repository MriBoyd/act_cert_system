from __future__ import annotations

import io

from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, Http404
from django.urls import reverse
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.certificates.api_permissions import ApiKeyAuthenticated, HasApiKeyScope
from apps.certificates.feature_flags import is_feature_enabled
from apps.certificates.models import Certificate, CertificateTemplate
from apps.certificates.serializers_integration import (
    IntegrationCertificateCreateSerializer,
    IntegrationCertificateBulkItemSerializer,
    IntegrationCertificateSerializer,
    IntegrationCertificateUpdateSerializer,
    IntegrationCertificateStatusSerializer,
    IntegrationTemplateSerializer,
    IntegrationTemplateWriteSerializer,
)
from apps.certificates.services.certificate_service import DuplicateCertificateError, create_certificate
from apps.certificates.services.image_generator import generate_certificate_image
from config.api_key_auth import ApiKeyAuthentication


def _feature_guard() -> Response | None:
    if not is_feature_enabled("integration_api"):
        return Response({"detail": "Feature disabled."}, status=status.HTTP_404_NOT_FOUND)
    return None


class IntegrationTemplateListAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["templates:read"]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        guarded = _feature_guard()
        if guarded:
            return guarded

        qs = CertificateTemplate.objects.all().order_by("name")
        return Response(IntegrationTemplateSerializer(qs, many=True).data)

    def post(self, request):
        guarded = _feature_guard()
        if guarded:
            return guarded

        # Require templates:write for creates
        api_key = request.auth
        if not api_key.has_scope("templates:write"):
            return Response({"detail": "Missing scope: templates:write"}, status=status.HTTP_403_FORBIDDEN)

        serializer = IntegrationTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(IntegrationTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


class IntegrationTemplateDetailAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["templates:read"]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_object(self, template_uuid):
        template = CertificateTemplate.objects.filter(id=template_uuid).first()
        if not template:
            raise Http404("Template not found.")
        return template

    def get(self, request, template_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded
        template = self.get_object(template_uuid)
        return Response(IntegrationTemplateSerializer(template).data)

    def patch(self, request, template_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        if not request.auth.has_scope("templates:write"):
            return Response({"detail": "Missing scope: templates:write"}, status=status.HTTP_403_FORBIDDEN)

        template = self.get_object(template_uuid)
        serializer = IntegrationTemplateWriteSerializer(instance=template, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(IntegrationTemplateSerializer(template).data)

    def delete(self, request, template_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        if not request.auth.has_scope("templates:write"):
            return Response({"detail": "Missing scope: templates:write"}, status=status.HTTP_403_FORBIDDEN)

        template = self.get_object(template_uuid)
        try:
            template.delete()
        except ProtectedError:
            return Response(
                {"detail": "Template is in use and cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class IntegrationCertificateCreateAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["certificates:read"]

    def get(self, request):
        guarded = _feature_guard()
        if guarded:
            return guarded

        qs = Certificate.objects.select_related("template").all().order_by("-created_at")

        status_filter = request.GET.get("status")
        template_id = request.GET.get("template_id")
        serial_number = request.GET.get("serial_number")
        search = (request.GET.get("search") or "").strip()

        if status_filter:
            qs = qs.filter(status=status_filter)
        if template_id:
            qs = qs.filter(template_id=template_id)
        if serial_number:
            qs = qs.filter(serial_number=serial_number)
        if search:
            qs = qs.filter(
                Q(recipient_name__icontains=search)
                | Q(course_name__icontains=search)
                | Q(serial_number__icontains=search)
            )

        # Simple bounded list (no extra pagination UX added here)
        limit = int(request.GET.get("limit", 100))
        limit = max(1, min(limit, 500))
        qs = qs[:limit]

        return Response(IntegrationCertificateSerializer(qs, many=True).data)

    def post(self, request):
        guarded = _feature_guard()
        if guarded:
            return guarded

        if not request.auth.has_scope("certificates:write"):
            return Response({"detail": "Missing scope: certificates:write"}, status=status.HTTP_403_FORBIDDEN)

        serializer = IntegrationCertificateCreateSerializer(data=request.data, context={})
        serializer.is_valid(raise_exception=True)
        template = serializer.context["template"]

        try:
            cert = create_certificate(
                template=template,
                issued_by=request.user,
                recipient_name=serializer.validated_data["recipient_name"],
                recipient_email=serializer.validated_data.get("recipient_email", ""),
                course_name=serializer.validated_data["course_name"],
                issue_date=serializer.validated_data["issue_date"],
                serial_number=serializer.validated_data["serial_number"],
            )
        except DuplicateCertificateError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        verify_path = reverse("public-verify-detail", kwargs={"certificate_uuid": cert.id})
        base_url = getattr(request, "build_absolute_uri", None)
        verification_url = request.build_absolute_uri(verify_path) if base_url else verify_path

        payload = IntegrationCertificateSerializer(cert).data
        payload["verification_url"] = verification_url
        payload["pdf_download_url"] = request.build_absolute_uri(
            reverse("api-integration-certificate-pdf", kwargs={"certificate_uuid": cert.id})
        )
        payload["qr_download_url"] = request.build_absolute_uri(
            reverse("api-integration-certificate-qr", kwargs={"certificate_uuid": cert.id})
        )

        return Response(payload, status=status.HTTP_201_CREATED)


class IntegrationCertificateBulkCreateAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["certificates:read"]

    def post(self, request):
        guarded = _feature_guard()
        if guarded:
            return guarded

        if not request.auth.has_scope("certificates:write"):
            return Response({"detail": "Missing scope: certificates:write"}, status=status.HTTP_403_FORBIDDEN)

        if not isinstance(request.data, dict):
            return Response({"detail": "Request body must be a JSON object."}, status=status.HTTP_400_BAD_REQUEST)

        items = request.data.get("certificates")
        shared_template_id = request.data.get("template_id")

        if not isinstance(items, list):
            return Response({"detail": "'certificates' must be a JSON array."}, status=status.HTTP_400_BAD_REQUEST)
        if len(items) == 0:
            return Response({"detail": "No certificates provided."}, status=status.HTTP_400_BAD_REQUEST)

        if len(items) > 500:
            return Response({"detail": "Too many certificates. Max 500 per request."}, status=status.HTTP_400_BAD_REQUEST)

        shared_template = None
        if shared_template_id:
            shared_template = CertificateTemplate.objects.filter(id=shared_template_id).first()
            if not shared_template:
                return Response({"detail": "Template not found."}, status=status.HTTP_400_BAD_REQUEST)
            if not shared_template.is_active:
                return Response({"detail": "Template is not active."}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        failed = 0
        results: list[dict] = []

        for index, raw_item in enumerate(items):
            if not isinstance(raw_item, dict):
                failed += 1
                results.append({"index": index, "status": "error", "detail": "Item must be a JSON object."})
                continue

            item = dict(raw_item)
            template = shared_template

            if template is not None:
                serializer = IntegrationCertificateBulkItemSerializer(data=item)
            else:
                # Require template_id per item
                serializer = IntegrationCertificateCreateSerializer(data=item, context={})

            if not serializer.is_valid():
                failed += 1
                results.append({
                    "index": index,
                    "status": "error",
                    "errors": serializer.errors,
                })
                continue

            if template is None:
                template = serializer.context.get("template")

            metadata = serializer.validated_data.get("metadata")

            try:
                cert = create_certificate(
                    template=template,
                    issued_by=request.user,
                    recipient_name=serializer.validated_data["recipient_name"],
                    recipient_email=serializer.validated_data.get("recipient_email", ""),
                    course_name=serializer.validated_data["course_name"],
                    issue_date=serializer.validated_data["issue_date"],
                    serial_number=serializer.validated_data["serial_number"],
                )
            except DuplicateCertificateError as exc:
                failed += 1
                results.append({
                    "index": index,
                    "status": "error",
                    "detail": str(exc),
                    "code": "duplicate",
                    "serial_number": item.get("serial_number"),
                })
                continue
            except Exception as exc:  # noqa: BLE001
                failed += 1
                results.append({
                    "index": index,
                    "status": "error",
                    "detail": "Failed to create certificate.",
                    "code": "create_failed",
                    "serial_number": item.get("serial_number"),
                })
                continue

            if metadata is not None:
                cert.metadata = metadata
                cert.save(update_fields=["metadata", "updated_at"])

            created += 1

            verify_path = reverse("public-verify-detail", kwargs={"certificate_uuid": cert.id})
            verification_url = request.build_absolute_uri(verify_path)

            payload = IntegrationCertificateSerializer(cert).data
            payload["verification_url"] = verification_url
            payload["pdf_download_url"] = request.build_absolute_uri(
                reverse("api-integration-certificate-pdf", kwargs={"certificate_uuid": cert.id})
            )
            payload["png_download_url"] = request.build_absolute_uri(
                reverse("api-integration-certificate-png", kwargs={"certificate_uuid": cert.id})
            )
            payload["jpg_download_url"] = request.build_absolute_uri(
                reverse("api-integration-certificate-jpg", kwargs={"certificate_uuid": cert.id})
            )
            payload["qr_download_url"] = request.build_absolute_uri(
                reverse("api-integration-certificate-qr", kwargs={"certificate_uuid": cert.id})
            )

            results.append({"index": index, "status": "created", **payload})

        return Response(
            {
                "created": created,
                "failed": failed,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )


class IntegrationCertificateDetailAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["certificates:read"]

    def get_object(self, certificate_uuid):
        cert = Certificate.objects.select_related("template").filter(id=certificate_uuid).first()
        if not cert:
            raise Http404("Certificate not found.")
        return cert

    def get(self, request, certificate_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        cert = self.get_object(certificate_uuid)
        return Response(IntegrationCertificateSerializer(cert).data)

    def patch(self, request, certificate_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        if not request.auth.has_scope("certificates:write"):
            return Response({"detail": "Missing scope: certificates:write"}, status=status.HTTP_403_FORBIDDEN)

        cert = self.get_object(certificate_uuid)

        # Allow editing, and if printable fields change, regenerate artifacts.
        old_values = {
            "template_id": str(cert.template_id),
            "recipient_name": cert.recipient_name,
            "recipient_email": cert.recipient_email,
            "course_name": cert.course_name,
            "issue_date": cert.issue_date,
        }

        serializer = IntegrationCertificateUpdateSerializer(instance=cert, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Apply template_id specially
        if "template_id" in serializer.validated_data:
            cert.template_id = serializer.validated_data["template_id"]

        for k, v in serializer.validated_data.items():
            if k == "template_id":
                continue
            setattr(cert, k, v)

        # Force fingerprint regeneration if key fields changed
        if any(
            str(getattr(cert, "template_id")) != old_values["template_id"]
            or cert.recipient_name != old_values["recipient_name"]
            or cert.course_name != old_values["course_name"]
            or cert.issue_date != old_values["issue_date"]
            for _ in [0]
        ):
            cert.fingerprint = ""

        cert.save()

        # Regenerate QR/PDF if core display fields changed or template changed
        from apps.certificates.services.pdf_generator import generate_certificate_pdf
        from apps.certificates.services.qr_service import generate_qr_image
        from django.conf import settings

        verify_path = reverse("public-verify-detail", kwargs={"certificate_uuid": cert.id})
        verification_url = f"{getattr(settings, 'SITE_BASE_URL', 'http://127.0.0.1:8000')}{verify_path}"
        qr_image = generate_qr_image(verification_url=verification_url, cert_uuid=cert.id)
        cert.qr_code_image.save(qr_image.name, qr_image, save=False)
        pdf_file = generate_certificate_pdf(cert)
        cert.pdf_file.save(pdf_file.name, pdf_file, save=False)
        png_file = generate_certificate_image(cert, fmt="PNG")
        cert.png_file.save(png_file.name, png_file, save=False)
        jpg_file = generate_certificate_image(cert, fmt="JPEG")
        cert.jpg_file.save(jpg_file.name, jpg_file, save=False)
        cert.save(update_fields=["qr_code_image", "pdf_file", "png_file", "jpg_file", "updated_at"])

        return Response(IntegrationCertificateSerializer(cert).data)

    def delete(self, request, certificate_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        if not request.auth.has_scope("certificates:delete"):
            return Response({"detail": "Missing scope: certificates:delete"}, status=status.HTTP_403_FORBIDDEN)

        cert = self.get_object(certificate_uuid)

        # Best-effort file cleanup
        try:
            if cert.pdf_file:
                cert.pdf_file.delete(save=False)
            if cert.qr_code_image:
                cert.qr_code_image.delete(save=False)
            if getattr(cert, "png_file", None):
                cert.png_file.delete(save=False)
            if getattr(cert, "jpg_file", None):
                cert.jpg_file.delete(save=False)
        except Exception:  # noqa: BLE001
            pass

        cert.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IntegrationCertificateStatusAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["certificates:write"]

    def patch(self, request, certificate_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        cert = Certificate.objects.filter(id=certificate_uuid).first()
        if not cert:
            raise Http404("Certificate not found.")

        serializer = IntegrationCertificateStatusSerializer(instance=cert, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(IntegrationCertificateSerializer(cert).data)


class IntegrationCertificatePdfDownloadAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["files:read"]

    def get(self, request, certificate_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        cert = Certificate.objects.filter(id=certificate_uuid).first()
        if not cert or not cert.pdf_file:
            raise Http404("Certificate PDF not available.")

        return FileResponse(
            cert.pdf_file.open("rb"),
            as_attachment=True,
            filename=f"certificate-{cert.serial_number}.pdf",
        )


class IntegrationCertificateQrDownloadAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["files:read"]

    def get(self, request, certificate_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        cert = Certificate.objects.filter(id=certificate_uuid).first()
        if not cert or not cert.qr_code_image:
            raise Http404("Certificate QR not available.")

        return FileResponse(
            cert.qr_code_image.open("rb"),
            as_attachment=True,
            filename=f"certificate-{cert.serial_number}-qr.png",
        )


class IntegrationCertificatePngDownloadAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["files:read"]

    def get(self, request, certificate_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        cert = Certificate.objects.select_related("template").filter(id=certificate_uuid).first()
        if not cert:
            raise Http404("Certificate not found.")

        if getattr(cert, "png_file", None):
            return FileResponse(
                cert.png_file.open("rb"),
                as_attachment=True,
                filename=f"certificate-{cert.serial_number}.png",
                content_type="image/png",
            )

        image_file = generate_certificate_image(cert, fmt="PNG")
        cert.png_file.save(image_file.name, image_file, save=True)
        return FileResponse(
            cert.png_file.open("rb"),
            as_attachment=True,
            filename=f"certificate-{cert.serial_number}.png",
            content_type="image/png",
        )


class IntegrationCertificateJpgDownloadAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [ApiKeyAuthenticated, HasApiKeyScope]
    required_scopes = ["files:read"]

    def get(self, request, certificate_uuid):
        guarded = _feature_guard()
        if guarded:
            return guarded

        cert = Certificate.objects.select_related("template").filter(id=certificate_uuid).first()
        if not cert:
            raise Http404("Certificate not found.")

        if getattr(cert, "jpg_file", None):
            return FileResponse(
                cert.jpg_file.open("rb"),
                as_attachment=True,
                filename=f"certificate-{cert.serial_number}.jpg",
                content_type="image/jpeg",
            )

        image_file = generate_certificate_image(cert, fmt="JPEG")
        cert.jpg_file.save(image_file.name, image_file, save=True)
        return FileResponse(
            cert.jpg_file.open("rb"),
            as_attachment=True,
            filename=f"certificate-{cert.serial_number}.jpg",
            content_type="image/jpeg",
        )
