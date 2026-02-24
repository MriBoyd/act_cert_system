from __future__ import annotations

import uuid

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.certificates.models import VerificationLog
from apps.certificates.tests.utils import make_admin_user, make_certificate, make_template


class VerifyFlowsTests(TestCase):
    def test_public_verify_creates_verification_log(self):
        admin = make_admin_user()
        template = make_template()
        cert = make_certificate(template=template, issued_by=admin, serial_number="SN-VERIFY-1")

        response = self.client.get(reverse("public-verify-detail", kwargs={"certificate_uuid": cert.id}))
        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            VerificationLog.objects.filter(certificate_uuid=cert.id).exists(),
            "Expected verification attempt to be logged",
        )

    @override_settings(FEATURE_FLAGS={"verification_api": True})
    def test_verify_api_returns_200_for_existing_certificate(self):
        admin = make_admin_user()
        template = make_template()
        cert = make_certificate(template=template, issued_by=admin, serial_number="SN-API-1")

        response = self.client.get(reverse("api-verify-certificate", kwargs={"certificate_uuid": cert.id}))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("certificate_id"), str(cert.id))
        self.assertTrue(payload.get("is_valid"))

    @override_settings(FEATURE_FLAGS={"verification_api": True})
    def test_verify_api_returns_404_for_missing_certificate(self):
        missing = uuid.uuid4()
        response = self.client.get(reverse("api-verify-certificate", kwargs={"certificate_uuid": missing}))
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload.get("certificate_id"), str(missing))

    @override_settings(FEATURE_FLAGS={"verification_api": False})
    def test_verify_api_returns_404_when_disabled(self):
        any_uuid = uuid.uuid4()
        response = self.client.get(reverse("api-verify-certificate", kwargs={"certificate_uuid": any_uuid}))
        self.assertEqual(response.status_code, 404)
