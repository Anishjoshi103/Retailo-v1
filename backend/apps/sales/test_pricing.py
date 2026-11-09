from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.sales.pricing import price_sale


def product(price, rate):
    """``price`` is the tax-inclusive (MRP-style) unit price."""
    return SimpleNamespace(selling_price=Decimal(price), gst_rate=Decimal(rate))


class PricingTests(SimpleTestCase):
    def test_mrp_is_split_into_taxable_value_and_equal_cgst_sgst(self):
        sale = price_sale([(product("100.00", "18.00"), Decimal("2.000"))], "27", "27")
        line = sale.lines[0]
        self.assertEqual((line.taxable_value, line.cgst_amount, line.sgst_amount, line.igst_amount), (
            Decimal("169.50"), Decimal("15.25"), Decimal("15.25"), Decimal("0.00")))
        self.assertEqual(line.line_total, Decimal("200.00"))
        self.assertEqual((sale.grand_total, sale.round_off), (Decimal("200.00"), Decimal("0.00")))

    def test_billed_amount_equals_the_mrp_not_mrp_plus_tax(self):
        sale = price_sale([(product("118.00", "18.00"), Decimal("1.000"))], "27", "27")
        self.assertEqual(sale.grand_total, Decimal("118.00"))
        self.assertEqual((sale.taxable_total, sale.total_tax), (Decimal("100.00"), Decimal("18.00")))

    def test_inter_state_line_uses_igst(self):
        sale = price_sale([(product("100.00", "18.00"), Decimal("1.000"))], "27", "29")
        self.assertEqual((sale.cgst_total, sale.sgst_total, sale.igst_total), (
            Decimal("0.00"), Decimal("0.00"), Decimal("15.25")))
        self.assertEqual(sale.lines[0].taxable_value, Decimal("84.75"))

    def test_grand_total_rounds_to_the_rupee_and_reports_round_off(self):
        sale = price_sale([(product("33.33", "5.00"), Decimal("3.000"))], "27", "27")
        self.assertEqual(sale.lines[0].line_total, Decimal("99.99"))
        self.assertEqual((sale.taxable_total, sale.total_tax), (Decimal("95.23"), Decimal("4.76")))
        self.assertEqual((sale.grand_total, sale.round_off), (Decimal("100.00"), Decimal("0.01")))

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
        self.assertEqual((sale.grand_total, sale.round_off), (Decimal("300.00"), Decimal("0.01")))

    def test_fractional_quantity_rounds_gross_to_paise(self):
        sale = price_sale([(product("45.00", "0.00"), Decimal("0.333"))], "27", "27")
        self.assertEqual(sale.lines[0].line_total, Decimal("14.99"))

    def test_every_line_totals_its_gross_with_equal_cgst_and_sgst(self):
        for price in ("0.01", "1.00", "19.99", "99.99", "1234.57"):
            for rate in ("0.00", "5.00", "12.00", "18.00", "28.00"):
                for quantity in ("1.000", "3.000", "0.250"):
                    for supplier, supply in (("27", "27"), ("27", "29")):
                        gross = (Decimal(price) * Decimal(quantity)).quantize(Decimal("0.01"))
                        line = price_sale([(product(price, rate), Decimal(quantity))], supplier, supply).lines[0]
                        label = (price, rate, quantity, supply)
                        self.assertEqual(line.line_total, gross, label)
                        self.assertEqual(line.taxable_value + line.cgst_amount + line.sgst_amount + line.igst_amount, gross, label)
                        self.assertEqual(line.cgst_amount, line.sgst_amount, label)
                        self.assertGreaterEqual(line.taxable_value, 0, label)
