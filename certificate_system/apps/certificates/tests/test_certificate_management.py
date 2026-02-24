from __future__ import annotations

from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.certificates.models import Certificate
from apps.certificates.tests.utils import make_admin_user, make_certificate, make_template
from apps.users.models import User


class CertificateAdminAccessTests(TestCase):
    def test_staff_viewer_role_is_denied(self):
        user = User.objects.create_user(username="viewer", password="pass12345")
        user.is_staff = True
        user.role = User.Role.VIEWER
        user.save(update_fields=["is_staff", "role"])

        self.client.login(username="viewer", password="pass12345")
        response = self.client.get(reverse("admin-dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("public-verify"))


class CertificateListTests(TestCase):
    def setUp(self):
        self.admin = make_admin_user(is_superuser=False)
        self.client.login(username=self.admin.username, password="pass12345")

    def test_certificate_list_filters_and_sorting(self):
        template_a = make_template(name="T-A")
        template_b = make_template(name="T-B")

        c1 = make_certificate(template=template_a, issued_by=self.admin, serial_number="SN-001")
        c1.recipient_name = "Bob"
        c1.course_name = "Zeta"
        c1.issue_date = date(2025, 1, 1)
        c1.save()

        c2 = make_certificate(template=template_b, issued_by=self.admin, serial_number="SN-002")
        c2.recipient_name = "Alice"
        c2.course_name = "Alpha"
        c2.issue_date = date(2025, 2, 1)
        c2.status = Certificate.Status.REVOKED
        c2.is_enabled = False
        c2.save()

        url = reverse("admin-certificate-list")

        # Filter by status
        resp = self.client.get(url, {"status": Certificate.Status.REVOKED})
        self.assertEqual(resp.status_code, 200)
        ids = {c.id for c in resp.context["certificates"]}
        self.assertIn(c2.id, ids)
        self.assertNotIn(c1.id, ids)

        # Filter by enabled
        resp = self.client.get(url, {"enabled": "true"})
        ids = {c.id for c in resp.context["certificates"]}
        self.assertIn(c1.id, ids)
        self.assertNotIn(c2.id, ids)

        # Search by recipient name
        resp = self.client.get(url, {"search": "ali"})
        ids = {c.id for c in resp.context["certificates"]}
        self.assertIn(c2.id, ids)
        self.assertNotIn(c1.id, ids)

        # Sort by recipient_name ascending
        resp = self.client.get(url, {"sort": "recipient_name", "dir": "asc"})
        certs = list(resp.context["certificates"])
        self.assertGreaterEqual(len(certs), 2)
        self.assertEqual(certs[0].recipient_name, "Alice")
        self.assertEqual(certs[1].recipient_name, "Bob")

    def test_certificate_list_pagination(self):
        template = make_template(name="T")
        for i in range(12):
            make_certificate(template=template, issued_by=self.admin, serial_number=f"SN-{i:03d}")

        resp = self.client.get(reverse("admin-certificate-list"), {"per_page": 10})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["certificates"]), 10)
        self.assertTrue(resp.context["page_obj"].has_next())


class FeatureFlagTests(TestCase):
    def test_disabled_feature_returns_404_for_admin(self):
        admin = make_admin_user(is_superuser=False)
        self.client.login(username=admin.username, password="pass12345")

        with override_settings(FEATURE_FLAGS={"certificate_management": False}):
            resp = self.client.get(reverse("admin-certificate-list"))
        self.assertEqual(resp.status_code, 404)
