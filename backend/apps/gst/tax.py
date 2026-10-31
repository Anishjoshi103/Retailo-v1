""""Deterministic GST calculation primitives for server-side document snapshots.

These helpers calculate tax only. They do not post stock, supplier balances, or accounting entries.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import TypedDict

MONEY_QUANTUM = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


class GstBreakdown(TypedDict):
    taxable_value: str
    gst_rate: str
    cgst_rate: str
    sgst_rate: str
    igst_rate: str
    cgst_amount: str
    sgst_amount: str
    igst_amount: str
    total_tax: str
    total_amount: str
    supply_type: str


def _decimal(value: Decimal | str, field_name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, str)):
        raise ValueError(f"{field_name} must be a Decimal or decimal string; floats are not accepted.")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid decimal value.") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite.")
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _money_string(value: Decimal) -> str:
    return format(_money(value), ".2f")


def calculate_gst(
    taxable_value: Decimal | str,
    gst_rate: Decimal | str,
    supplier_state_code: str,
    place_of_supply_state_code: str,
) -> GstBreakdown:
    """Calculate an exclusive-of-tax GST breakdown using the place of supply.

    State codes are compared as strings so leading zeroes are preserved. This
    function intentionally does not infer a state from GSTIN or product data.
    Taxable value is normalized to paise before tax is calculated. Tax is
    rounded to paise with ROUND_HALF_UP for each applicable component.
    """
    taxable = _decimal(taxable_value, "taxable_value")
    rate = _decimal(gst_rate, "gst_rate")
    if taxable < 0:
        raise ValueError("taxable_value cannot be negative.")
    if rate < 0 or rate > 100:
        raise ValueError("gst_rate must be between 0 and 100.")

    # Use the same paise-precision taxable value in both the snapshot and tax
    # calculation so the returned components reconcile deterministically.
    taxable = _money(taxable)

    for field_name, code in (
        ("supplier_state_code", supplier_state_code),
        ("place_of_supply_state_code", place_of_supply_state_code),
    ):
        if not isinstance(code, str) or len(code) != 2 or not code.isdigit():
            raise ValueError(f"{field_name} must be a two-digit state code string.")

    intra_state = supplier_state_code == place_of_supply_state_code
    if intra_state:
        cgst_rate = rate / Decimal("2")
        sgst_rate = rate / Decimal("2")
        igst_rate = ZERO
        cgst_amount = _money(taxable * cgst_rate / HUNDRED)
        sgst_amount = _money(taxable * sgst_rate / HUNDRED)
        igst_amount = ZERO
        supply_type = "intra_state"
    else:
        cgst_rate = ZERO
        sgst_rate = ZERO
        igst_rate = rate
        cgst_amount = ZERO
        sgst_amount = ZERO
        igst_amount = _money(taxable * igst_rate / HUNDRED)
        supply_type = "inter_state"

    total_tax = cgst_amount + sgst_amount + igst_amount
    return {
        "taxable_value": _money_string(taxable),
        "gst_rate": format(rate, ".2f"),
        "cgst_rate": format(cgst_rate, ".2f"),
        "sgst_rate": format(sgst_rate, ".2f"),
        "igst_rate": format(igst_rate, ".2f"),
        "cgst_amount": _money_string(cgst_amount),
        "sgst_amount": _money_string(sgst_amount),
        "igst_amount": _money_string(igst_amount),
        "total_tax": _money_string(total_tax),
        "total_amount": _money_string(taxable + total_tax),
        "supply_type": supply_type,
    }
