from __future__ import annotations

from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.certificates.forms import BulkCertificateUploadForm
from apps.certificates.services.certificate_service import DuplicateCertificateError, create_certificate
from apps.certificates.tests.utils import make_admin_user, make_template


class CertificateServiceTests(TestCase):
    def setUp(self):
        self.issuer = make_admin_user(is_superuser=False)
        self.template = make_template(name="Template")

    def test_create_certificate_generates_qr_pdf_and_images(self):
        cert = create_certificate(
            template=self.template,
            issued_by=self.issuer,
            recipient_name="John Doe",
            recipient_email="john@example.com",
            course_name="Django 101",
            issue_date=date(2025, 1, 15),
            serial_number="SER-001",
        )

        self.assertTrue(bool(cert.qr_code_image))
        self.assertTrue(bool(cert.pdf_file))
        self.assertTrue(bool(cert.png_file))
        self.assertTrue(bool(cert.jpg_file))

        # Validate file contents look plausible
        with cert.pdf_file.open("rb") as f:
            header = f.read(4)
        self.assertEqual(header, b"%PDF")

        with cert.qr_code_image.open("rb") as f:
            png_sig = f.read(8)
        self.assertEqual(png_sig, b"\x89PNG\r\n\x1a\n")

        with cert.png_file.open("rb") as f:
            png_sig = f.read(8)
        self.assertEqual(png_sig, b"\x89PNG\r\n\x1a\n")

        with cert.jpg_file.open("rb") as f:
            jpg_sig = f.read(3)
        self.assertEqual(jpg_sig, b"\xff\xd8\xff")

    def test_duplicate_serial_raises_duplicate_error(self):
        create_certificate(
            template=self.template,
            issued_by=self.issuer,
            recipient_name="A",
            recipient_email="a@example.com",
            course_name="Course",
            issue_date=date(2025, 1, 15),
            serial_number="SER-002",
        )

        with self.assertRaises(DuplicateCertificateError):
            create_certificate(
                template=self.template,
                issued_by=self.issuer,
                recipient_name="B",
                recipient_email="b@example.com",
                course_name="Course",
                issue_date=date(2025, 1, 15),
                serial_number="SER-002",
            )


class BulkCsvFormTests(TestCase):
    def setUp(self):
        self.issuer = make_admin_user(is_superuser=False)
        self.template = make_template(name="Template")

    def test_parse_rows_requires_columns(self):
        csv_content = "recipient_name,course_name\nJohn,Django\n".encode("utf-8")
        upload = SimpleUploadedFile("data.csv", csv_content, content_type="text/csv")

        form = BulkCertificateUploadForm(files={"csv_file": upload}, data={"template": str(self.template.id)})
        self.assertTrue(form.is_valid())
        with self.assertRaisesMessage(Exception, "CSV must include"):
            form.parse_rows()

    def test_parse_rows_success(self):
        csv_content = (
            "recipient_name,recipient_email,course_name,issue_date,serial_number\n"
            "John,john@example.com,Django,2025-01-01,SN-1\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("data.csv", csv_content, content_type="text/csv")

        form = BulkCertificateUploadForm(files={"csv_file": upload}, data={"template": str(self.template.id)})
        self.assertTrue(form.is_valid())
        rows = form.parse_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["recipient_name"], "John")

    def test_clean_csv_file_rejects_non_csv_extension(self):
        upload = SimpleUploadedFile("data.txt", b"x", content_type="text/plain")
        form = BulkCertificateUploadForm(files={"csv_file": upload}, data={"template": str(self.template.id)})
        self.assertFalse(form.is_valid())
        self.assertIn("csv_file", form.errors)
