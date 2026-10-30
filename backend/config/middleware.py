import uuid


class CorrelationIdMiddleware:
    """Attach a stable request ID to logs and responses."""

    header_name = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get(self.header_name, "").strip()
        # Bound length and accepted characters to avoid log injection.
        if supplied and len(supplied) <= 128 and all(
            char.isalnum() or char in "-_." for char in supplied
        ):
            request_id = supplied
        else:
            request_id = uuid.uuid4().hex

        request.request_id = request_id
        response = self.get_response(request)
        response[self.header_name] = request_id
        return response
