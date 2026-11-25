import logging
from uuid import uuid4

from django.core.cache import caches
from django.db import connections
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness endpoint; deliberately does not require a database query."""
    return JsonResponse({"status": "ok", "service": "retailo-api"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness(request):
    """Check required runtime dependencies without exposing failure details."""
    checks = (
        ("database", _check_database),
        ("throttle_cache", _check_throttle_cache),
    )
    unavailable = []

    for name, check in checks:
        try:
            check()
        except Exception:
            logger.exception("Readiness dependency check failed: %s", name)
            unavailable.append(name)

    if unavailable:
        return JsonResponse(
            {"status": "unavailable", "service": "retailo-api"},
            status=503,
        )

    return JsonResponse({"status": "ok", "service": "retailo-api"})


def _check_database():
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")
        if cursor.fetchone()[0] != 1:
            raise RuntimeError("Database health query returned an unexpected result.")


def _check_throttle_cache():
    cache = caches["throttle"]
    key = f"readiness:{uuid4().hex}"
    try:
        cache.set(key, "ok", timeout=5)
        if cache.get(key) != "ok":
            raise RuntimeError("Throttle cache probe did not round-trip.")
    finally:
        cache.delete(key)
