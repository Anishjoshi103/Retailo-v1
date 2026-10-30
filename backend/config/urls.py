from django.urls import path
from .health import health

urlpatterns = [
    path("api/v1/health", health, name="health"),
]
