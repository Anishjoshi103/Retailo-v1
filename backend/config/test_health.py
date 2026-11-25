from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class ReadinessTests(SimpleTestCase):
    def test_health_remains_a_liveness_check(self):
        with patch("config.health._check_database") as database_check, patch(
            "config.health._check_throttle_cache"
        ) as cache_check:
            response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "retailo-api"})
        database_check.assert_not_called()
        cache_check.assert_not_called()

    def test_readiness_returns_ok_when_dependencies_are_healthy(self):
        with patch("config.health._check_database"), patch(
            "config.health._check_throttle_cache"
        ):
            response = self.client.get(reverse("readiness"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "retailo-api"})

    def test_readiness_returns_503_when_database_is_unavailable(self):
        with patch(
            "config.health._check_database", side_effect=RuntimeError("connection details")
        ), patch("config.health._check_throttle_cache"):
            response = self.client.get(reverse("readiness"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable", "service": "retailo-api"})
        self.assertNotIn("connection details", response.content.decode())

    def test_readiness_returns_503_when_throttle_cache_is_unavailable(self):
        with patch("config.health._check_database"), patch(
            "config.health._check_throttle_cache", side_effect=RuntimeError("redis credentials")
        ):
            response = self.client.get(reverse("readiness"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable", "service": "retailo-api"})
        self.assertNotIn("redis credentials", response.content.decode())

    def test_readiness_returns_503_when_both_dependencies_are_unavailable(self):
        with patch("config.health._check_database", side_effect=RuntimeError), patch(
            "config.health._check_throttle_cache", side_effect=RuntimeError
        ):
            response = self.client.get(reverse("readiness"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable", "service": "retailo-api"})
