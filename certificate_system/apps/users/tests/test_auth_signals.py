from __future__ import annotations

from django.test import TestCase

from apps.users.models import User


class AuthSignalsTests(TestCase):
    def test_login_emits_security_log(self):
        User.objects.create_user(username="u1", password="pass12345")

        with self.assertLogs("security", level="INFO") as cm:
            ok = self.client.login(username="u1", password="pass12345")

        self.assertTrue(ok)
        self.assertTrue(any("auth_login_success" in msg for msg in cm.output))

    def test_login_failed_emits_security_log_warning(self):
        User.objects.create_user(username="u2", password="pass12345")

        with self.assertLogs("security", level="WARNING") as cm:
            ok = self.client.login(username="u2", password="wrong")

        self.assertFalse(ok)
        self.assertTrue(any("auth_login_failed" in msg for msg in cm.output))
