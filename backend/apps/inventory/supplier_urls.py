from django.urls import path

from .supplier_views import SupplierDetailView, SupplierListCreateView

urlpatterns = [
    path("suppliers", SupplierListCreateView.as_view(), name="supplier-list-create"),
    path("suppliers/<uuid:supplier_id>", SupplierDetailView.as_view(), name="supplier-detail"),
]
