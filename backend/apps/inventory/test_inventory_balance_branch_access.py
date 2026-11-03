from apps.inventory.test_purchase_receipts import PurchaseReceiptApiTests


class InventoryBalanceBranchFilterTests(PurchaseReceiptApiTests):
    def test_inventory_balance_filter_rejects_unauthorized_branch(self):
        response = self.client.get(
            "/api/v1/inventory/balances",
            {"branch_id": str(self.other_branch.id)},
        )
        self.assertEqual(response.status_code, 403, response.content)
