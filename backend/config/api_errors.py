from rest_framework.exceptions import APIException, ErrorDetail
from rest_framework.views import exception_handler


def api_error_response(*, code, message, status_code, request=None, field_errors=None):
    response = __import__("rest_framework.response", fromlist=["Response"]).Response(
        {"error": {
            "code": code,
            "message": message,
            "field_errors": field_errors or {},
            "request_id": getattr(request, "request_id", None),
        }},
        status=status_code,
    )
    return response


def _field_errors(detail):
    if isinstance(detail, dict):
        return {str(key): [str(value) for value in (items if isinstance(items, (list, tuple)) else [items])]
                for key, items in detail.items()}
    if isinstance(detail, list):
        return {"non_field_errors": [str(item) for item in detail]}
    return {}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    request = context.get("request")
    detail = response.data
    message = str(exc.detail) if isinstance(exc, APIException) else "Request failed"
    code = getattr(exc, "default_code", "request_error")
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
    response.data = {"error": {
        "code": code,
        "message": message,
        "field_errors": _field_errors(detail) if isinstance(detail, dict) and "detail" not in detail else {},
        "request_id": getattr(request, "request_id", None),
    }}
    return response
