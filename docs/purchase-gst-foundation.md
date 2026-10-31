# Purchase GST calculation foundation

## Scope of this slice

This module adds a deterministic, side-effect-free GST calculation primitive for purchase-document tax snapshots. It does not post stock, supplier balances, input-tax-credit ledgers, journal entries, or credit notes. Existing goods receipts and supplier returns remain inventory-only until a separate, audited posting workflow is implemented.

## Calculation contract

`calculate_gst(taxable_value, gst_rate, supplier_state_code, place_of_supply_state_code)` accepts `Decimal` values or decimal strings; binary floats are rejected. Taxable value is assumed to be exclusive of GST. State codes are two-character digit strings and must be supplied by trusted tenant GST-registration / place-of-supply configuration by the eventual API layer; this function does not infer them.

- Matching state codes: split the rate equally into CGST and SGST; IGST is zero.
- Different state codes: apply IGST at the full rate; CGST and SGST are zero.
- Each monetary tax component is rounded to two decimal places using `ROUND_HALF_UP`.
- Output monetary values are decimal strings with two places, suitable for JSON serialization without float conversion.
- Negative taxable values and rates outside 0–100 are rejected.

## Important limits

This is a calculation foundation, not a complete GST compliance engine. Before posting purchase invoices, define tenant GST registrations and effective dates, supplier GSTIN validation, supply-type/exception handling, exempt/nil-rated/non-GST items, invoice-level discounts and charges, rounding reconciliation against supplier invoices, ITC eligibility/reversal rules, and tax-professional-approved examples. A supplier return must not automatically create a supplier credit note or reverse ITC; the supplier's accepted credit note and original document linkage need their own immutable workflow.

## Verification

Focused tests cover intra-state CGST/SGST, inter-state IGST, zero rate, rounding, invalid rates/amounts, float rejection, and malformed state codes. CI should also run `python manage.py test apps.gst` and the full migration check. No successful test run is claimed by this change alone.
