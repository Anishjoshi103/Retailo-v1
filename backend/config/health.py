from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness endpoint; deliberately does not require a database query."""
    return JsonResponse({"status": "ok", "service": "retailo-api"})
