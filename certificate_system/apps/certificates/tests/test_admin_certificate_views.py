from __future__ import annotations

from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase
from django.urls import reverse

from apps.certificates.models import Certificate, VerificationLog
from apps.certificates.services.certificate_service import create_certificate
from apps.certificates.tests.utils import make_admin_user, make_template
from apps.certificates.tests.utils import make_image


class AdminCertificateViewsTests(TestCase):
    def setUp(self):
        self.admin = make_admin_user(is_superuser=False)
        self.template = make_template(name="T")
        self.client.login(username=self.admin.username, password="pass12345")

    def test_generate_certificate_view_creates_certificate(self):
        logo = make_image("logo.png")
        extra_1 = make_image("extra-1.png")
        extra_2 = make_image("extra-2.png")
        resp = self.client.post(
            reverse("admin-generate-certificate"),
            data={
                "template": str(self.template.id),
                "recipient_name": "John Doe",
                "recipient_email": "john@example.com",
                "course_name": "Django 101",
                "issue_date": "2025-01-01",
                "serial_number": "GEN-001",
                "logo_image": logo,
                "extra_images": [extra_1, extra_2],
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("admin-dashboard"))
        self.assertEqual(Certificate.objects.count(), 1)

        cert = Certificate.objects.get(serial_number="GEN-001")
        self.assertTrue(bool(cert.pdf_file))
        self.assertTrue(bool(cert.qr_code_image))
        self.assertTrue(bool(cert.logo_image))
        self.assertEqual(cert.overlay_images.count(), 2)

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


class AdminCertificateBulkActionsTests(TestCase):
    def setUp(self):
        self.admin = make_admin_user(is_superuser=False)
        self.template = make_template(name="T")
        self.client.login(username=self.admin.username, password="pass12345")

    def test_bulk_enable_skips_non_valid(self):
        cert_valid = create_certificate(
            template=self.template,
            issued_by=self.admin,
            recipient_name="Alice",
            recipient_email="alice@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 1),
            serial_number="BULK-EN-001",
        )
        cert_valid.status = Certificate.Status.VALID
        cert_valid.is_enabled = False
        cert_valid.save(update_fields=["status", "is_enabled", "updated_at"])

        cert_revoked = create_certificate(
            template=self.template,
            issued_by=self.admin,
            recipient_name="Bob",
            recipient_email="bob@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 1),
            serial_number="BULK-EN-002",
        )
        cert_revoked.status = Certificate.Status.REVOKED
        cert_revoked.is_enabled = False
        cert_revoked.save(update_fields=["status", "is_enabled", "updated_at"])

        resp = self.client.post(
            reverse("admin-certificate-bulk-actions"),
            data={
                "action": "enable",
                "selected_ids": [str(cert_valid.id), str(cert_revoked.id)],
                "next": reverse("admin-certificate-list"),
            },
        )
        self.assertEqual(resp.status_code, 302)

        cert_valid.refresh_from_db()
        cert_revoked.refresh_from_db()
        self.assertTrue(cert_valid.is_enabled)
        self.assertFalse(cert_revoked.is_enabled)
        self.assertEqual(cert_revoked.status, Certificate.Status.REVOKED)

    def test_bulk_mark_revoked_disables(self):
        cert_a = create_certificate(
            template=self.template,
            issued_by=self.admin,
            recipient_name="Alice",
            recipient_email="alice@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 1),
            serial_number="BULK-RV-001",
        )
        cert_b = create_certificate(
            template=self.template,
            issued_by=self.admin,
            recipient_name="Bob",
            recipient_email="bob@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 1),
            serial_number="BULK-RV-002",
        )

        resp = self.client.post(
            reverse("admin-certificate-bulk-actions"),
            data={
                "action": "mark_revoked",
                "selected_ids": [str(cert_a.id), str(cert_b.id)],
                "next": reverse("admin-certificate-list"),
            },
        )
        self.assertEqual(resp.status_code, 302)

        cert_a.refresh_from_db()
        cert_b.refresh_from_db()
        self.assertEqual(cert_a.status, Certificate.Status.REVOKED)
        self.assertEqual(cert_b.status, Certificate.Status.REVOKED)
        self.assertFalse(cert_a.is_enabled)
        self.assertFalse(cert_b.is_enabled)

    def test_bulk_delete_removes_records_and_files(self):
        cert = create_certificate(
            template=self.template,
            issued_by=self.admin,
            recipient_name="Alice",
            recipient_email="alice@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 1),
            serial_number="BULK-DEL-001",
        )
        pdf_name = cert.pdf_file.name
        qr_name = cert.qr_code_image.name
        self.assertTrue(bool(pdf_name))
        self.assertTrue(bool(qr_name))
        self.assertTrue(default_storage.exists(pdf_name))
        self.assertTrue(default_storage.exists(qr_name))

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                reverse("admin-certificate-bulk-actions"),
                data={
                    "action": "delete",
                    "selected_ids": [str(cert.id)],
                    "next": reverse("admin-certificate-list"),
                },
            )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Certificate.objects.filter(id=cert.id).exists())

        self.assertFalse(default_storage.exists(pdf_name))
        self.assertFalse(default_storage.exists(qr_name))
