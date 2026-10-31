from decimal import Decimal

from django.test import SimpleTestCase

from apps.gst.tax import calculate_gst


class CalculateGstTests(SimpleTestCase):
    def test_intra_state_splits_tax_equally_between_cgst_and_sgst(self):
        result = calculate_gst(Decimal("1000.00"), Decimal("18.00"), "27", "27")

        self.assertEqual(result["supply_type"], "intra_state")
        self.assertEqual(result["cgst_rate"], "9.00")
        self.assertEqual(result["sgst_rate"], "9.00")
        self.assertEqual(result["igst_rate"], "0.00")
        self.assertEqual(result["cgst_amount"], "90.00")
        self.assertEqual(result["sgst_amount"], "90.00")
        self.assertEqual(result["igst_amount"], "0.00")
        self.assertEqual(result["total_amount"], "1180.00")

    def test_inter_state_uses_igst_only(self):
        result = calculate_gst("1000.00", "5.00", "27", "29")

        self.assertEqual(result["supply_type"], "inter_state")
        self.assertEqual(result["cgst_amount"], "0.00")
        self.assertEqual(result["sgst_amount"], "0.00")
        self.assertEqual(result["igst_rate"], "5.00")
        self.assertEqual(result["igst_amount"], "50.00")
        self.assertEqual(result["total_amount"], "1050.00")

    def test_rounds_each_tax_component_to_paise_half_up(self):
        result = calculate_gst("0.05", "18.00", "27", "27")

        self.assertEqual(result["cgst_amount"], "0.00")
        self.assertEqual(result["sgst_amount"], "0.00")
        self.assertEqual(result["total_tax"], "0.00")

    def test_zero_rate_has_no_tax(self):
        result = calculate_gst("125.50", "0", "27", "27")

        self.assertEqual(result["total_tax"], "0.00")
        self.assertEqual(result["total_amount"], "125.50")

    def test_rejects_negative_taxable_value(self):
        with self.assertRaisesMessage(ValueError, "taxable_value cannot be negative"):
            calculate_gst("-1.00", "5.00", "27", "27")

    def test_rejects_out_of_range_rate(self):
        with self.assertRaisesMessage(ValueError, "gst_rate must be between 0 and 100"):
            calculate_gst("100.00", "101", "27", "27")

    def test_rejects_float_money_input(self):
        with self.assertRaisesMessage(ValueError, "floats are not accepted"):
            calculate_gst(100.0, "18.00", "27", "27")

    def test_rejects_malformed_state_code(self):
        with self.assertRaisesMessage(ValueError, "supplier_state_code must be a two-digit state code string"):
            calculate_gst("100.00", "18.00", "Maharashtra", "27")
