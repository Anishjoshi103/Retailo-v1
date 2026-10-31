from django.urls import path

from .return_views import PurchaseReturnCreateView

urlpatterns = [path("returns", PurchaseReturnCreateView.as_view(), name="purchase-return-create")]
