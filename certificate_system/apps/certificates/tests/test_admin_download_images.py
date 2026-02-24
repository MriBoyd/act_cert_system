from __future__ import annotations

import datetime

from django.test import TestCase
from django.urls import reverse

from apps.certificates.models import Certificate
from apps.certificates.tests.utils import make_image
from apps.users.models import User


class AdminCertificateImageDownloadsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="pass", is_staff=True)
        self.superuser = User.objects.create_superuser(username="root", password="pass")

        # Enable download feature for tests
        from django.test.utils import override_settings

        self._override = override_settings(
            FEATURE_FLAGS={
                "certificate_download": True,
                "integration_api": True,
                "log_management": True,
            }
        )
        self._override.enable()

    def tearDown(self):
        self._override.disable()

    def _create_certificate(self):
        from apps.certificates.models import CertificateTemplate

        from apps.certificates.services.certificate_service import create_certificate

        template = CertificateTemplate.objects.create(
            name="T",
            issuer_name="Issuer",
            background_image=make_image(),
            dynamic_fields=[
                {"name": "recipient_name", "x": 120, "y": 340, "font_size": 28},
                {"name": "course_name", "x": 120, "y": 300, "font_size": 18},
                {"name": "qr_code", "x": 700, "y": 40, "size": 110},
            ],
        )

        return create_certificate(
            template=template,
            issued_by=self.superuser,
            recipient_name="Ada Lovelace",
            recipient_email="",
            course_name="Testing 101",
            issue_date=datetime.date(2025, 1, 1),
            serial_number="SN-IMG-1",
        )

    def test_admin_png_download_requires_login(self):
        cert = self._create_certificate()
        url = reverse("admin-download-certificate-png", kwargs={"certificate_uuid": str(cert.id)})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)

    def test_admin_png_and_jpg_download(self):
        cert = self._create_certificate()
        self.client.login(username="root", password="pass")

        url = reverse("admin-download-certificate-png", kwargs={"certificate_uuid": str(cert.id)})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/png")
        content = b"".join(res.streaming_content)
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))

        url = reverse("admin-download-certificate-jpg", kwargs={"certificate_uuid": str(cert.id)})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/jpeg")
        content = b"".join(res.streaming_content)
        self.assertTrue(content.startswith(b"\xff\xd8\xff"))
