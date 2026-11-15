from django.urls import path

from .purchase_read_views import PurchaseReceiptDetailView, PurchaseReceiptListCreateView

urlpatterns = [
    path("receipts", PurchaseReceiptListCreateView.as_view(), name="purchase-receipt-list-create"),
    path("receipts/<uuid:receipt_id>", PurchaseReceiptDetailView.as_view(), name="purchase-receipt-detail"),
]
