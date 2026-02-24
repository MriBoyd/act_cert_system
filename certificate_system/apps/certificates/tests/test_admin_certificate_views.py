from __future__ import annotations

from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.certificates.models import Certificate, VerificationLog
from apps.certificates.services.certificate_service import create_certificate
from apps.certificates.tests.utils import make_admin_user, make_template


class AdminCertificateViewsTests(TestCase):
    def setUp(self):
        self.admin = make_admin_user(is_superuser=False)
        self.template = make_template(name="T")
        self.client.login(username=self.admin.username, password="pass12345")

    def test_generate_certificate_view_creates_certificate(self):
        resp = self.client.post(
            reverse("admin-generate-certificate"),
            data={
                "template": str(self.template.id),
                "recipient_name": "John Doe",
                "recipient_email": "john@example.com",
                "course_name": "Django 101",
                "issue_date": "2025-01-01",
                "serial_number": "GEN-001",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("admin-dashboard"))
        self.assertEqual(Certificate.objects.count(), 1)

        cert = Certificate.objects.get(serial_number="GEN-001")
        self.assertTrue(bool(cert.pdf_file))
        self.assertTrue(bool(cert.qr_code_image))

    def test_bulk_generate_creates_multiple_certificates(self):
        csv_content = (
            "recipient_name,recipient_email,course_name,issue_date,serial_number\n"
            "Alice,alice@example.com,Django,2025-01-01,BULK-001\n"
            "Bob,bob@example.com,Django,2025-01-02,BULK-002\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("bulk.csv", csv_content, content_type="text/csv")

        resp = self.client.post(
            reverse("admin-bulk-generate"),
            data={"template": str(self.template.id), "csv_file": upload},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("admin-dashboard"))
        self.assertEqual(Certificate.objects.count(), 2)

    def test_certificate_detail_includes_verification_logs(self):
        cert = create_certificate(
            template=self.template,
            issued_by=self.admin,
            recipient_name="John",
            recipient_email="john@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 1),
            serial_number="DET-001",
        )
        VerificationLog.objects.create(
            certificate=cert,
            certificate_uuid=cert.id,
            requester_ip="127.0.0.1",
            user_agent="tests",
            is_valid=True,
        )

        resp = self.client.get(reverse("admin-certificate-detail", kwargs={"certificate_uuid": cert.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["certificate"].id, cert.id)
        self.assertGreaterEqual(len(resp.context["verification_logs"]), 1)

    def test_manage_certificate_status_validates_enabled_requires_valid_status(self):
        cert = create_certificate(
            template=self.template,
            issued_by=self.admin,
            recipient_name="John",
            recipient_email="john@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 1),
            serial_number="STAT-001",
        )

        resp = self.client.post(
            reverse("admin-certificate-status", kwargs={"certificate_uuid": cert.id}),
            data={"status": Certificate.Status.REVOKED, "is_enabled": True},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("enabled", resp.content.decode("utf-8").lower())

    def test_download_pdf_and_qr(self):
        cert = create_certificate(
            template=self.template,
            issued_by=self.admin,
            recipient_name="John",
            recipient_email="john@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 1),
            serial_number="DL-001",
        )

        pdf = self.client.get(reverse("admin-download-certificate-pdf", kwargs={"certificate_uuid": cert.id}))
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("attachment;", pdf.get("Content-Disposition", ""))
        self.assertIn("certificate-DL-001.pdf", pdf.get("Content-Disposition", ""))

        qr = self.client.get(reverse("admin-download-certificate-qr", kwargs={"certificate_uuid": cert.id}))
        self.assertEqual(qr.status_code, 200)
        self.assertIn("attachment;", qr.get("Content-Disposition", ""))
        self.assertIn("certificate-DL-001-qr.png", qr.get("Content-Disposition", ""))
