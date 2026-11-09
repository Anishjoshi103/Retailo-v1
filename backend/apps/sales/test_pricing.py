from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.sales.pricing import price_sale


def product(price, rate):
    return SimpleNamespace(selling_price=Decimal(price), gst_rate=Decimal(rate))


class PricingTests(SimpleTestCase):
    def test_intra_state_line_splits_tax_into_cgst_and_sgst(self):
        sale = price_sale([(product("100.00", "18.00"), Decimal("2.000"))], "27", "27")
        line = sale.lines[0]
        self.assertEqual((line.taxable_value, line.cgst_amount, line.sgst_amount, line.igst_amount), (
            Decimal("200.00"), Decimal("18.00"), Decimal("18.00"), Decimal("0.00")))
        self.assertEqual(line.line_total, Decimal("236.00"))
        self.assertEqual((sale.grand_total, sale.round_off), (Decimal("236.00"), Decimal("0.00")))

    def test_inter_state_line_uses_igst(self):
        sale = price_sale([(product("100.00", "18.00"), Decimal("1.000"))], "27", "29")
        self.assertEqual((sale.cgst_total, sale.sgst_total, sale.igst_total), (
            Decimal("0.00"), Decimal("0.00"), Decimal("18.00")))

    def test_grand_total_rounds_to_the_rupee_and_reports_round_off(self):
        sale = price_sale([(product("33.33", "5.00"), Decimal("3.000"))], "27", "27")
        self.assertEqual(sale.taxable_total, Decimal("99.99"))
        self.assertEqual(sale.total_tax, Decimal("5.00"))
        self.assertEqual((sale.grand_total, sale.round_off), (Decimal("105.00"), Decimal("0.01")))

    def test_round_off_can_be_negative(self):
        sale = price_sale([(product("10.40", "0.00"), Decimal("1.000"))], "27", "27")
        self.assertEqual((sale.grand_total, sale.round_off), (Decimal("10.00"), Decimal("-0.40")))

    def test_totals_reconcile_with_lines(self):
        sale = price_sale([
            (product("100.00", "18.00"), Decimal("2.000")),
            (product("33.33", "5.00"), Decimal("3.000")),
        ], "27", "27")
        self.assertEqual(sale.taxable_total, sum(line.taxable_value for line in sale.lines))
        self.assertEqual(sale.total_tax, sum(line.cgst_amount + line.sgst_amount + line.igst_amount for line in sale.lines))
        self.assertEqual(sale.grand_total, sale.taxable_total + sale.total_tax + sale.round_off)

    def test_fractional_quantity_rounds_taxable_value_to_paise(self):
        sale = price_sale([(product("45.00", "0.00"), Decimal("0.333"))], "27", "27")
        self.assertEqual(sale.lines[0].taxable_value, Decimal("14.99"))
