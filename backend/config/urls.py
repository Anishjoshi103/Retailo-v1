from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from .health import health

urlpatterns = [
    path("api/v1/health", health, name="health"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="api-docs"),
]
