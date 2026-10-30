from django.urls import path

from .views import InventoryBalanceListView, StockAdjustmentView

urlpatterns = [
    path("balances", InventoryBalanceListView.as_view(), name="inventory-balance-list"),
    path("adjustments", StockAdjustmentView.as_view(), name="inventory-adjustment-create"),
]
