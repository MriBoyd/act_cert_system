from __future__ import annotations

from django.test import TestCase


class RequestContextMiddlewareTests(TestCase):
    def test_sets_x_request_id_header(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Request-ID", response.headers)
        self.assertTrue(response.headers["X-Request-ID"])

    def test_preserves_incoming_x_request_id_header(self):
        response = self.client.get("/", headers={"X-Request-ID": "req-123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Request-ID"), "req-123")
