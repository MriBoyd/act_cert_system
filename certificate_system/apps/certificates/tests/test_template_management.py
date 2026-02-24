from __future__ import annotations

from django.core.files.storage import default_storage
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


class TemplateBulkActionsTests(TestCase):
    def setUp(self):
        self.admin = make_admin_user()
        self.client.force_login(self.admin)

    def test_bulk_activate_and_deactivate(self):
        t1 = make_template(name="T1", issuer="I")
        t2 = make_template(name="T2", issuer="I")
        t1.is_active = False
        t2.is_active = False
        t1.save(update_fields=["is_active"])
        t2.save(update_fields=["is_active"])

        resp = self.client.post(
            reverse("admin-template-bulk-actions"),
            data={
                "action": "activate",
                "selected_ids": [str(t1.id), str(t2.id)],
                "next": reverse("admin-template-list"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertTrue(t1.is_active)
        self.assertTrue(t2.is_active)

        resp = self.client.post(
            reverse("admin-template-bulk-actions"),
            data={
                "action": "deactivate",
                "selected_ids": [str(t1.id), str(t2.id)],
                "next": reverse("admin-template-list"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertFalse(t1.is_active)
        self.assertFalse(t2.is_active)

    def test_bulk_delete_skips_in_use_and_cleans_background(self):
        t_in_use = make_template(name="INUSE", issuer="I")
        t_free = make_template(name="FREE", issuer="I")

        # Make one template in-use
        make_certificate(template=t_in_use, issued_by=self.admin, serial_number="SN-INUSE")

        bg_free = t_free.background_image.name
        self.assertTrue(bool(bg_free))
        self.assertTrue(default_storage.exists(bg_free))

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                reverse("admin-template-bulk-actions"),
                data={
                    "action": "delete",
                    "selected_ids": [str(t_in_use.id), str(t_free.id)],
                    "next": reverse("admin-template-list"),
                },
            )
        self.assertEqual(resp.status_code, 302)

        # In-use should remain; free should be deleted
        self.assertTrue(type(t_in_use).objects.filter(id=t_in_use.id).exists())
        self.assertFalse(type(t_free).objects.filter(id=t_free.id).exists())

        self.assertFalse(default_storage.exists(bg_free))
