from django.urls import path

from .supplier_views import SupplierListCreateView

urlpatterns = [path("suppliers", SupplierListCreateView.as_view(), name="supplier-list-create")]
