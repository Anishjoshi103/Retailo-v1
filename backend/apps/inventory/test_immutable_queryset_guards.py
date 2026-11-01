from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import Product
from apps.inventory.models import (
    PurchaseReceipt,
    PurchaseReceiptLine,
    PurchaseReturn,
    StockMovement,
)
from apps.tenancy.models import Branch, Tenant


class PostedInventoryQuerySetImmutabilityTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Immutable Store", slug="immutable-store")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN")
        self.user = get_user_model().objects.create_user(
            username="immutable@example.test",
            email="immutable@example.test",
            password="Test-password-123",
        )
        self.product = Product.objects.create(
            tenant=self.tenant,
            sku="IMM-1",
            name="Immutable product",
            selling_price=Decimal("10.00"),
            purchase_price=Decimal("5.00"),
        )
        self.receipt = PurchaseReceipt.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            supplier_name="Supplier",
            idempotency_key="immutable-receipt",
            request_hash="a" * 64,
            created_by=self.user,
        )
        self.receipt_line = PurchaseReceiptLine.objects.create(
            tenant=self.tenant,
            receipt=self.receipt,
            product=self.product,
            quantity=Decimal("2.000"),
            unit_cost=Decimal("5.00"),
        )
        self.return_record = PurchaseReturn.objects.create(
            tenant=self.tenant,
            receipt=self.receipt,
            branch=self.branch,
            supplier_name="Supplier",
            reason="Damaged",
            idempotency_key="immutable-return",
            request_hash="b" * 64,
            created_by=self.user,
        )
        self.movement = StockMovement.objects.create(
            tenant=self.tenant,
            branch=self.branch,
            product=self.product,
            quantity_delta=Decimal("2.000"),
            reason=StockMovement.Reason.RECEIPT,
            idempotency_key="immutable-movement",
            created_by=self.user,
        )

    def test_stock_movement_queryset_update_is_blocked(self):
        with self.assertRaises(TypeError):
            StockMovement.objects.filter(pk=self.movement.pk).update(note="rewritten")

    def test_stock_movement_queryset_delete_is_blocked(self):
        with self.assertRaises(TypeError):
            StockMovement.objects.filter(pk=self.movement.pk).delete()

    def test_purchase_receipt_queryset_update_is_blocked(self):
        with self.assertRaises(TypeError):
            PurchaseReceipt.objects.filter(pk=self.receipt.pk).update(supplier_name="Changed")

    def test_purchase_receipt_queryset_delete_is_blocked(self):
        with self.assertRaises(TypeError):
            PurchaseReceipt.objects.filter(pk=self.receipt.pk).delete()

    def test_purchase_receipt_line_queryset_update_is_blocked(self):
        with self.assertRaises(TypeError):
            PurchaseReceiptLine.objects.filter(pk=self.receipt_line.pk).update(quantity=Decimal("3.000"))

    def test_purchase_return_queryset_update_is_blocked(self):
        with self.assertRaises(TypeError):
            PurchaseReturn.objects.filter(pk=self.return_record.pk).update(reason="Changed")
