from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from apps.certificates.models import Certificate
from apps.certificates.tests.utils import make_admin_user, make_certificate, make_template


class TemplateManagementTests(TestCase):
    def setUp(self):
        self.admin = make_admin_user()
        self.client.force_login(self.admin)

    def test_template_list_renders_and_paginates(self):
        for i in range(30):
            make_template(name=f"T{i:02d}", issuer="Issuer")

        url = reverse("admin-template-list")
        response = self.client.get(url, {"per_page": 10, "page": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["templates"]), 10)

    def test_template_list_filters_active(self):
        t1 = make_template(name="Active", issuer="A")
        t2 = make_template(name="Inactive", issuer="B")
        t2.is_active = False
        t2.save(update_fields=["is_active"])

        url = reverse("admin-template-list")
        response = self.client.get(url, {"active": "true"})
        templates = list(response.context["templates"])
        template_ids = {t.id for t in templates}
        self.assertIn(t1.id, template_ids)
        self.assertNotIn(t2.id, template_ids)

    def test_template_list_sorts_by_total_certificates(self):
        t1 = make_template(name="T1", issuer="I")
        t2 = make_template(name="T2", issuer="I")

        make_certificate(template=t1, issued_by=self.admin, serial_number="SN-T1-1")
        make_certificate(template=t1, issued_by=self.admin, serial_number="SN-T1-2")
        make_certificate(template=t2, issued_by=self.admin, serial_number="SN-T2-1")

        url = reverse("admin-template-list")
        response = self.client.get(url, {"sort": "total_certificates", "dir": "desc"})
        self.assertEqual(response.status_code, 200)

        templates = list(response.context["templates"])
        self.assertGreaterEqual(templates[0].total_certificates, templates[1].total_certificates)

    def test_toggle_template_status(self):
        template = make_template(name="Toggle", issuer="I")
        self.assertTrue(template.is_active)

        response = self.client.post(reverse("admin-toggle-template-status", kwargs={"template_uuid": template.id}))
        self.assertEqual(response.status_code, 302)

        template.refresh_from_db()
        self.assertFalse(template.is_active)
