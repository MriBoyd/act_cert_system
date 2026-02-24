from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.certificates.tests.utils import make_admin_user


class LogManagementTests(TestCase):
    def setUp(self):
        self.superuser = make_admin_user(is_superuser=True)
        self.staff = make_admin_user(username="staff", is_superuser=False)

    def test_log_management_requires_login(self):
        response = self.client.get(reverse("admin-log-management"))
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_view_and_clear_logs(self):
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            (log_dir / "app.log").write_text("line1\nline2\nline3\n", encoding="utf-8")

            with override_settings(LOG_DIR=log_dir):
                self.client.force_login(self.superuser)
                response = self.client.get(reverse("admin-log-management"), {"log": "app", "lines": 2})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "line2")
                self.assertContains(response, "line3")

                clear = self.client.post(reverse("admin-log-clear", kwargs={"log_key": "app"}))
                self.assertEqual(clear.status_code, 302)
                self.assertEqual((log_dir / "app.log").read_text(encoding="utf-8"), "")

    def test_non_superuser_cannot_clear_logs(self):
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            (log_dir / "app.log").write_text("line1\n", encoding="utf-8")

            with override_settings(LOG_DIR=log_dir):
                self.client.force_login(self.staff)
                clear = self.client.post(reverse("admin-log-clear", kwargs={"log_key": "app"}))
                self.assertEqual(clear.status_code, 302)
                self.assertEqual((log_dir / "app.log").read_text(encoding="utf-8"), "line1\n")

    def test_log_search_filters_results(self):
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            (log_dir / "security.log").write_text(
                "event=auth_login_failed user=a\n"
                "event=auth_login_success user=a\n",
                encoding="utf-8",
            )

            with override_settings(LOG_DIR=log_dir):
                self.client.force_login(self.superuser)
                response = self.client.get(
                    reverse("admin-log-management"),
                    {"log": "security", "q": "failed", "lines": 50},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "auth_login_failed")
                self.assertNotContains(response, "auth_login_success")

    def test_log_download_returns_attachment(self):
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            (log_dir / "security.log").write_text("line1\n", encoding="utf-8")

            with override_settings(LOG_DIR=log_dir):
                self.client.force_login(self.superuser)
                response = self.client.get(reverse("admin-log-download", kwargs={"log_key": "security"}))
                self.assertEqual(response.status_code, 200)
                self.assertIn("attachment;", response.get("Content-Disposition", ""))
                self.assertIn("security.log", response.get("Content-Disposition", ""))

    def test_log_download_404_if_missing(self):
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            with override_settings(LOG_DIR=log_dir):
                self.client.force_login(self.superuser)
                response = self.client.get(reverse("admin-log-download", kwargs={"log_key": "audit"}))
                self.assertEqual(response.status_code, 404)

    def test_log_pagination_pages_from_end(self):
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            (log_dir / "app.log").write_text(
                "\n".join([f"line{i:03d}" for i in range(1, 121)]) + "\n",
                encoding="utf-8",
            )

            with override_settings(LOG_DIR=log_dir):
                self.client.force_login(self.superuser)

                page1 = self.client.get(reverse("admin-log-management"), {"log": "app", "lines": 50, "page": 1})
                self.assertEqual(page1.status_code, 200)
                self.assertContains(page1, "line120")
                self.assertNotContains(page1, "line001")

                page3 = self.client.get(reverse("admin-log-management"), {"log": "app", "lines": 50, "page": 3})
                self.assertEqual(page3.status_code, 200)
                self.assertContains(page3, "line001")
                self.assertNotContains(page3, "line120")
