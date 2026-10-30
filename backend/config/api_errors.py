from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    request = context.get("request")
    request_id = getattr(request, "request_id", None)
    detail = response.data
    if isinstance(exc, APIException):
        message = str(exc.detail)
    else:
        message = "Request failed"

    response.data = {
        "error": {
            "code": getattr(exc, "default_code", "request_error"),
            "message": message,
            "details": detail,
            "request_id": request_id,
        }
    }
    return response
