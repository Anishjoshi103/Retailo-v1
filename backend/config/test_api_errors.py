from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from config.api_errors import api_error_response, api_exception_handler


class ApiErrorEnvelopeTests(SimpleTestCase):
    def test_direct_error_response_uses_standard_envelope(self):
        request = APIRequestFactory().get("/api/v1/auth/login")
        request.request_id = "request-123"
        response = api_error_response(
            code="invalid_credentials",
            message="Email or password is incorrect.",
            status_code=401,
            request=request,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data, {"error": {
            "code": "invalid_credentials",
            "message": "Email or password is incorrect.",
            "field_errors": {},
            "request_id": "request-123",
        }})

    def test_validation_exception_uses_standard_envelope(self):
        request = APIRequestFactory().post("/api/v1/products")
        request.request_id = "request-456"
        response = api_exception_handler(
            ValidationError({"name": ["This field is required."]}),
            {"request": request},
        )
        self.assertEqual(response.data["error"]["request_id"], "request-456")
        self.assertEqual(response.data["error"]["field_errors"], {"name": ["This field is required."]})
        self.assertEqual(set(response.data), {"error"})
