from django.urls import path

from .purchase_views import PurchaseReceiptCreateView

urlpatterns = [path("receipts", PurchaseReceiptCreateView.as_view(), name="purchase-receipt-create")]
