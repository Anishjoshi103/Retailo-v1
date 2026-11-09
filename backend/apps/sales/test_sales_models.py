from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.catalog.models import Product
from apps.sales.models import Sale, SaleLine, SalePayment
from apps.tenancy.models import Branch, Tenant

TWOPLACES = Decimal("0.01")


class SalesModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.other_tenant = Tenant.objects.create(name="Store B", slug="store-b")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN")
        self.user = get_user_model().objects.create_user(
            username="cashier@example.test", email="cashier@example.test", password="Test-password-123"
        )
        self.product = Product.objects.create(
            tenant=self.tenant, sku="RICE-1", name="Rice", unit=Product.Unit.KG,
            gst_rate=Decimal("18.00"), selling_price=Decimal("100.00"),
        )

    def sale_fields(self, **overrides):
        fields = dict(
            tenant=self.tenant, branch=self.branch, invoice_number="INV-MAIN-000001",
            invoice_date=date(2026, 11, 9), seller_gstin="27AAPFU0939F1ZV",
            seller_state_code="27", place_of_supply_state_code="27",
            taxable_total=Decimal("100.00"), cgst_total=Decimal("9.00"),
            sgst_total=Decimal("9.00"), igst_total=Decimal("0.00"), total_tax=Decimal("18.00"),
            round_off=Decimal("0.00"), grand_total=Decimal("118.00"),
            idempotency_key="key-1", request_hash="h" * 64, created_by=self.user,
        )
        fields.update(overrides)
        return fields

    def make_sale(self, **overrides):
        return Sale.objects.create(**self.sale_fields(**overrides))

    def make_line(self, sale, **overrides):
        fields = dict(
            tenant=self.tenant, sale=sale, product=self.product, sku="RICE-1", name="Rice",
            hsn_code="1006", unit="kg", quantity=Decimal("1.000"), unit_price=Decimal("100.00"),
            gst_rate=Decimal("18.00"), taxable_value=Decimal("100.00"),
            cgst_amount=Decimal("9.00"), sgst_amount=Decimal("9.00"), igst_amount=Decimal("0.00"),
            line_total=Decimal("118.00"),
        )
        fields.update(overrides)
        return SaleLine.objects.create(**fields)

    def test_posted_sale_with_line_and_payments_is_stored(self):
        sale = self.make_sale()
        self.make_line(sale)
        SalePayment.objects.create(tenant=self.tenant, sale=sale, method="cash", amount=Decimal("100.00"))
        SalePayment.objects.create(tenant=self.tenant, sale=sale, method="upi", amount=Decimal("18.00"), reference="UPI-1")
        self.assertEqual(sale.lines.for_tenant(self.tenant.id).count(), 1)
        self.assertEqual(sale.payments.for_tenant(self.tenant.id).count(), 2)

    def test_sale_is_immutable_through_every_path(self):
        sale = self.make_sale()
        sale.customer_name = "Changed"
        with self.assertRaises(TypeError):
            sale.save()
        with self.assertRaises(TypeError):
            sale.delete()
        scoped = Sale.objects.for_tenant(self.tenant.id).filter(pk=sale.pk)
        with self.assertRaises(TypeError):
            scoped.update(customer_name="Changed")
        with self.assertRaises(TypeError):
            scoped.delete()
        with self.assertRaises(TypeError):
            Sale.objects.for_tenant(self.tenant.id).bulk_update([sale], ["customer_name"])

    def test_lines_and_payments_are_immutable(self):
        sale = self.make_sale()
        line = self.make_line(sale)
        payment = SalePayment.objects.create(tenant=self.tenant, sale=sale, method="cash", amount=Decimal("118.00"))
        for record in (line, payment):
            with self.assertRaises(TypeError):
                record.save()
            with self.assertRaises(TypeError):
                record.delete()
        with self.assertRaises(TypeError):
            SaleLine.objects.for_tenant(self.tenant.id).filter(pk=line.pk).update(sku="X")
        with self.assertRaises(TypeError):
            SalePayment.objects.for_tenant(self.tenant.id).filter(pk=payment.pk).delete()

    def test_invoice_number_is_unique_per_branch_and_idempotency_key_per_tenant(self):
        self.make_sale()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_sale(idempotency_key="key-2")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_sale(invoice_number="INV-MAIN-000002")
        north = Branch.objects.create(tenant=self.tenant, name="North", code="NORTH")
        self.make_sale(branch=north, idempotency_key="key-3")

    def test_idempotency_key_may_repeat_across_tenants(self):
        self.make_sale()
        other_branch = Branch.objects.create(tenant=self.other_tenant, name="Main", code="MAIN")
        self.make_sale(tenant=self.other_tenant, branch=other_branch)

    def test_database_rejects_inconsistent_sale_totals(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_sale(grand_total=Decimal("119.00"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_sale(total_tax=Decimal("17.00"), grand_total=Decimal("117.00"))

    def test_database_rejects_inconsistent_or_invalid_lines_and_payments(self):
        sale = self.make_sale()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_line(sale, line_total=Decimal("120.00"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_line(sale, quantity=Decimal("0.000"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            SalePayment.objects.create(tenant=self.tenant, sale=sale, method="cash", amount=Decimal("0.00"))

    def test_children_must_share_the_sales_tenant(self):
        sale = self.make_sale()
        with self.assertRaises(ValueError):
            self.make_line(sale, tenant=self.other_tenant)
        with self.assertRaises(ValueError):
            SalePayment.objects.create(tenant=self.other_tenant, sale=sale, method="cash", amount=Decimal("1.00"))

    def test_unscoped_sale_queries_are_refused(self):
        self.make_sale()
        with self.assertRaises(RuntimeError):
            Sale.objects.count()
