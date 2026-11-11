from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.sales.pricing import price_sale
from apps.sales.returns import cumulative_share, price_return, price_return_line


def sale_line(quantity, taxable, cgst, sgst, igst="0.00"):
    return SimpleNamespace(
        quantity=Decimal(quantity), taxable_value=Decimal(taxable), cgst_amount=Decimal(cgst),
        sgst_amount=Decimal(sgst), igst_amount=Decimal(igst),
    )


def totals(line):
    return (line.taxable_value, line.cgst_amount, line.sgst_amount, line.igst_amount)


class ReturnPricingTests(SimpleTestCase):
    def test_returning_the_whole_line_reverses_it_exactly(self):
        original = sale_line("2.000", "169.50", "15.25", "15.25")
        line = price_return_line(original, Decimal("0"), Decimal("2.000"))
        self.assertEqual(totals(line), (Decimal("169.50"), Decimal("15.25"), Decimal("15.25"), Decimal("0.00")))
        self.assertEqual(line.line_total, Decimal("200.00"))

    def test_partial_returns_telescope_to_the_original_line(self):
        original = sale_line("2.000", "169.50", "15.25", "15.25")
        first = price_return_line(original, Decimal("0"), Decimal("1.000"))
        second = price_return_line(original, Decimal("1.000"), Decimal("1.000"))
        self.assertEqual(totals(first), (Decimal("84.75"), Decimal("7.63"), Decimal("7.63"), Decimal("0.00")))
        self.assertEqual(totals(second), (Decimal("84.75"), Decimal("7.62"), Decimal("7.62"), Decimal("0.00")))
        self.assertEqual(first.line_total + second.line_total, Decimal("200.00"))

    def test_any_split_of_the_quantity_sums_exactly_and_never_goes_negative(self):
        cases = [
            ("3.000", "95.23", "2.38", "2.38", ["1", "1", "1"]),
            ("3.000", "95.23", "2.38", "2.38", ["0.5", "2.5"]),
            ("1.000", "84.74", "7.63", "7.63", ["0.333", "0.333", "0.334"]),
            ("7.000", "1234.57", "55.55", "55.55", ["1", "2", "0.001", "3.999"]),
            ("5.000", "0.07", "0.01", "0.01", ["1", "1", "1", "1", "1"]),
            ("2.500", "10.00", "0.50", "0.50", ["0.1"] * 25),
        ]
        for quantity, taxable, cgst, sgst, parts in cases:
            original = sale_line(quantity, taxable, cgst, sgst)
            returned = Decimal("0")
            sums = [Decimal("0")] * 4
            for part in parts:
                line = price_return_line(original, returned, Decimal(part))
                returned += Decimal(part)
                self.assertTrue(all(value >= 0 for value in totals(line)), (quantity, part))
                self.assertEqual(line.cgst_amount, line.sgst_amount, (quantity, part))
                sums = [a + b for a, b in zip(sums, totals(line))]
            self.assertEqual(returned, Decimal(quantity))
            self.assertEqual(tuple(sums), totals(original), (quantity, parts))

    def test_inter_state_igst_is_reversed_too(self):
        original = sale_line("2.000", "169.50", "0.00", "0.00", "30.50")
        first = price_return_line(original, Decimal("0"), Decimal("1.000"))
        second = price_return_line(original, Decimal("1.000"), Decimal("1.000"))
        self.assertEqual(first.igst_amount + second.igst_amount, Decimal("30.50"))

    def test_cumulative_share_never_exceeds_the_amount(self):
        self.assertEqual(cumulative_share(Decimal("10.00"), Decimal("5.000"), Decimal("3.000")), Decimal("10.00"))
        self.assertEqual(cumulative_share(Decimal("10.00"), Decimal("1.000"), Decimal("3.000")), Decimal("3.33"))

    def test_refund_rounds_to_the_rupee_with_a_signed_round_off(self):
        original = sale_line("2.000", "169.50", "15.25", "15.25")
        priced = price_return([(original, Decimal("0"), Decimal("1.000"))])
        self.assertEqual(priced.total_tax, Decimal("15.26"))
        self.assertEqual((priced.grand_total, priced.round_off), (Decimal("100.00"), Decimal("-0.01")))

    def test_returning_a_whole_sale_refunds_exactly_its_grand_total(self):
        products = [
            (SimpleNamespace(selling_price=Decimal("100.00"), gst_rate=Decimal("18.00")), Decimal("2.000")),
            (SimpleNamespace(selling_price=Decimal("33.33"), gst_rate=Decimal("5.00")), Decimal("3.000")),
            (SimpleNamespace(selling_price=Decimal("19.99"), gst_rate=Decimal("12.00")), Decimal("0.750")),
        ]
        sale = price_sale(products, "27", "27")
        items = [
            (sale_line(str(line.quantity), str(line.taxable_value), str(line.cgst_amount), str(line.sgst_amount), str(line.igst_amount)), Decimal("0"), line.quantity)
            for line in sale.lines
        ]
        refund = price_return(items)
        self.assertEqual(refund.grand_total, sale.grand_total)
        self.assertEqual((refund.taxable_total, refund.total_tax), (sale.taxable_total, sale.total_tax))
        self.assertEqual(refund.round_off, sale.round_off)
