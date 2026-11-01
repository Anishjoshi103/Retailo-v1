from django.test import SimpleTestCase


class HealthEndpointTests(SimpleTestCase):
    def test_health_returns_ok_without_database(self):
        from django.test import Client

        response = Client().get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "retailo-api"})

    def test_health_response_has_correlation_id(self):
        from django.test import Client

        response = Client().get("/api/v1/health", HTTP_X_REQUEST_ID="retailo-test-123")
        self.assertEqual(response["X-Request-ID"], "retailo-test-123")

    def test_invalid_correlation_id_is_replaced(self):
        from django.test import Client

        response = Client().get("/api/v1/health", HTTP_X_REQUEST_ID="bad\\nheader")
        self.assertNotEqual(response["X-Request-ID"], "bad\\nheader")
        self.assertTrue(response["X-Request-ID"])
