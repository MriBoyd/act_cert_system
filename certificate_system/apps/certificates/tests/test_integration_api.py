from __future__ import annotations

from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.certificates.models import Certificate
from apps.certificates.tests.utils import make_admin_user, make_template
from apps.users.models import ApiKey


class IntegrationApiTests(TestCase):
    def setUp(self):
        self.user = make_admin_user(is_superuser=False)
        self.template = make_template(name="T")

        _api_key, raw_key = ApiKey.create_with_raw_key(
            name="Test Key",
            user=self.user,
            scopes=[
                "templates:read",
                "templates:write",
                "certificates:read",
                "certificates:write",
                "certificates:delete",
                "files:read",
            ],
        )
        self.raw_key = raw_key

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Api-Key {self.raw_key}"}

    def test_requires_api_key(self):
        resp = self.client.get(reverse("api-integration-templates"))
        self.assertEqual(resp.status_code, 401)

    def test_scope_enforced(self):
        _api_key, raw_key = ApiKey.create_with_raw_key(
            name="Limited",
            user=self.user,
            scopes=["templates:read"],
        )
        resp = self.client.post(
            reverse("api-integration-certificate-create"),
            data={
                "template_id": str(self.template.id),
                "recipient_name": "John",
                "recipient_email": "john@example.com",
                "course_name": "Course",
                "issue_date": "2025-01-01",
                "serial_number": "S-1",
            },
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Api-Key {raw_key}"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_template_list(self):
        resp = self.client.get(reverse("api-integration-templates"), **self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()), 1)

    def test_bulk_create_certificates_json(self):
        # One certificate created upfront to force a duplicate in the bulk request.
        created = self.client.post(
            reverse("api-integration-certificate-create"),
            data={
                "template_id": str(self.template.id),
                "recipient_name": "John",
                "recipient_email": "john@example.com",
                "course_name": "Course",
                "issue_date": "2025-01-01",
                "serial_number": "BULK-001",
            },
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(created.status_code, 201)

        resp = self.client.post(
            reverse("api-integration-certificate-bulk"),
            data={
                "template_id": str(self.template.id),
                "certificates": [
                    {
                        "recipient_name": "Dup",
                        "recipient_email": "dup@example.com",
                        "course_name": "Course",
                        "issue_date": "2025-01-01",
                        "serial_number": "BULK-001",
                    },
                    {
                        "recipient_name": "Jane",
                        "recipient_email": "jane@example.com",
                        "course_name": "Course",
                        "issue_date": "2025-01-02",
                        "serial_number": "BULK-002",
                    },
                ],
            },
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["created"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(len(payload["results"]), 2)

        self.assertEqual(Certificate.objects.filter(serial_number="BULK-001").count(), 1)
        self.assertEqual(Certificate.objects.filter(serial_number="BULK-002").count(), 1)

    def test_create_detail_status_and_downloads(self):
        create_resp = self.client.post(
            reverse("api-integration-certificate-create"),
            data={
                "template_id": str(self.template.id),
                "recipient_name": "John",
                "recipient_email": "john@example.com",
                "course_name": "Course",
                "issue_date": "2025-01-01",
                "serial_number": "INT-001",
            },
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(create_resp.status_code, 201)
        cert_id = create_resp.json()["certificate_id"]

        detail = self.client.get(
            reverse("api-integration-certificate-detail", kwargs={"certificate_uuid": cert_id}),
            **self._auth_headers(),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["serial_number"], "INT-001")

        patch = self.client.patch(
            reverse("api-integration-certificate-status", kwargs={"certificate_uuid": cert_id}),
            data={"status": Certificate.Status.REVOKED, "is_enabled": False},
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.json()["status"], Certificate.Status.REVOKED)

        pdf = self.client.get(
            reverse("api-integration-certificate-pdf", kwargs={"certificate_uuid": cert_id}),
            **self._auth_headers(),
        )
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("attachment;", pdf.get("Content-Disposition", ""))

        url = reverse(
            "api-integration-certificate-png",
            kwargs={"certificate_uuid": str(cert_id)},
        )
        res = self.client.get(url, **self._auth_headers())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/png")
        content = b"".join(res.streaming_content)
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))

        url = reverse(
            "api-integration-certificate-jpg",
            kwargs={"certificate_uuid": str(cert_id)},
        )
        res = self.client.get(url, **self._auth_headers())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/jpeg")
        content = b"".join(res.streaming_content)
        self.assertTrue(content.startswith(b"\xff\xd8\xff"))

        qr = self.client.get(
            reverse("api-integration-certificate-qr", kwargs={"certificate_uuid": cert_id}),
            **self._auth_headers(),
        )
        self.assertEqual(qr.status_code, 200)
        self.assertIn("attachment;", qr.get("Content-Disposition", ""))

        # List should include it
        lst = self.client.get(reverse("api-integration-certificate-create"), **self._auth_headers())
        self.assertEqual(lst.status_code, 200)
        self.assertTrue(any(row["serial_number"] == "INT-001" for row in lst.json()))

        # Update should regenerate and persist
        upd = self.client.patch(
            reverse("api-integration-certificate-detail", kwargs={"certificate_uuid": cert_id}),
            data={"recipient_name": "John Updated"},
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(upd.status_code, 200)
        self.assertEqual(upd.json()["recipient_name"], "John Updated")

        # Delete
        delete = self.client.delete(
            reverse("api-integration-certificate-detail", kwargs={"certificate_uuid": cert_id}),
            **self._auth_headers(),
        )
        self.assertEqual(delete.status_code, 204)

    def test_template_create_update_delete(self):
        from apps.certificates.tests.utils import make_image
        upload = make_image("bg.png")

        created = self.client.post(
            reverse("api-integration-templates"),
            data={
                "name": "Tpl API",
                "issuer_name": "Issuer",
                "background_image": upload,
                "dynamic_fields": "[]",
                "is_active": True,
            },
            **self._auth_headers(),
        )
        self.assertEqual(created.status_code, 201)
        tpl_id = created.json()["id"]

        updated = self.client.patch(
            reverse("api-integration-template-detail", kwargs={"template_uuid": tpl_id}),
            data={"issuer_name": "Issuer2"},
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["issuer_name"], "Issuer2")

        deleted = self.client.delete(
            reverse("api-integration-template-detail", kwargs={"template_uuid": tpl_id}),
            **self._auth_headers(),
        )
        self.assertEqual(deleted.status_code, 204)

    def test_feature_flag_off_returns_404(self):
        with override_settings(FEATURE_FLAGS={"integration_api": False}):
            resp = self.client.get(reverse("api-integration-templates"), **self._auth_headers())
        self.assertEqual(resp.status_code, 404)
