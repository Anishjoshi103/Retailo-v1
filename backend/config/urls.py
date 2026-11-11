from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.views import BranchesView
from apps.sales.return_views import CreditNoteDetailView, CreditNoteListView, SaleReturnView
from apps.sales.views import SaleDetailView, SaleListCreateView
from apps.tenancy.branch_views import BranchDetailView

from .health import health

urlpatterns = [
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/branches", BranchesView.as_view(), name="branches-list"),
    path("api/v1/branches/<uuid:branch_id>", BranchDetailView.as_view(), name="branch-detail"),
    path("api/v1/sales", SaleListCreateView.as_view(), name="sale-list-create"),
    path("api/v1/sales/<uuid:sale_id>", SaleDetailView.as_view(), name="sale-detail"),
    path("api/v1/sales/<uuid:sale_id>/returns", SaleReturnView.as_view(), name="sale-return"),
    path("api/v1/credit-notes", CreditNoteListView.as_view(), name="credit-note-list"),
    path("api/v1/credit-notes/<uuid:credit_note_id>", CreditNoteDetailView.as_view(), name="credit-note-detail"),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/inventory/", include("apps.inventory.urls")),
    path("api/v1/inventory/", include("apps.inventory.purchase_urls")),
    path("api/v1/inventory/", include("apps.inventory.supplier_urls")),
    path("api/v1/inventory/", include("apps.inventory.return_urls")),
    path("api/v1/health", health, name="health"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="api-docs"),
]
