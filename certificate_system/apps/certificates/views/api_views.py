from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.certificates.feature_flags import is_feature_enabled
from apps.certificates.serializers import CertificateVerificationSerializer
from apps.certificates.services.verification import verify_certificate


class VerifyCertificateAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request, certificate_uuid):
        if not is_feature_enabled("verification_api"):
            return Response({"detail": "Feature disabled."}, status=status.HTTP_404_NOT_FOUND)

        certificate, is_valid = verify_certificate(certificate_uuid, request)
        if not certificate:
            return Response(
                {
                    "certificate_id": str(certificate_uuid),
                    "is_valid": False,
                    "message": "Certificate not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = CertificateVerificationSerializer(certificate).data
        payload["is_valid"] = is_valid
        return Response(payload, status=status.HTTP_200_OK)
