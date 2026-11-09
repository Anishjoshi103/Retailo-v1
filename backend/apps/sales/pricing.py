"""Server-side invoice pricing: line GST via apps.gst, then a rupee-rounded grand total.

Prices are tax-exclusive (``Product.selling_price`` is the taxable unit price) and are
always read from the catalogue, never accepted from the client.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from apps.gst.tax import calculate_gst

PAISE = Decimal("0.01")
RUPEE = Decimal("1")
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class PricedLine:
    product: object
    quantity: Decimal
    unit_price: Decimal
    gst_rate: Decimal
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class PricedSale:
    lines: list[PricedLine]
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    total_tax: Decimal
    round_off: Decimal
    grand_total: Decimal


def price_sale(
    items: Iterable[tuple[object, Decimal]], seller_state_code: str, place_of_supply_state_code: str
) -> PricedSale:
    """Price ``(product, quantity)`` pairs; each product supplies ``selling_price``/``gst_rate``."""
    lines: list[PricedLine] = []
    for product, quantity in items:
        unit_price = Decimal(product.selling_price)  # type: ignore[attr-defined]
        gst_rate = Decimal(product.gst_rate)  # type: ignore[attr-defined]
        taxable = (quantity * unit_price).quantize(PAISE, rounding=ROUND_HALF_UP)
        gst = calculate_gst(taxable, gst_rate, seller_state_code, place_of_supply_state_code)
        cgst = Decimal(gst["cgst_amount"])
        sgst = Decimal(gst["sgst_amount"])
        igst = Decimal(gst["igst_amount"])
        lines.append(PricedLine(
            product=product, quantity=quantity, unit_price=unit_price, gst_rate=gst_rate,
            taxable_value=taxable, cgst_amount=cgst, sgst_amount=sgst, igst_amount=igst,
            line_total=taxable + cgst + sgst + igst,
        ))
    taxable_total = sum((line.taxable_value for line in lines), ZERO)
    cgst_total = sum((line.cgst_amount for line in lines), ZERO)
    sgst_total = sum((line.sgst_amount for line in lines), ZERO)
    igst_total = sum((line.igst_amount for line in lines), ZERO)
    total_tax = cgst_total + sgst_total + igst_total
    exact = taxable_total + total_tax
    grand_total = exact.quantize(RUPEE, rounding=ROUND_HALF_UP).quantize(PAISE)
    return PricedSale(
        lines=lines, taxable_total=taxable_total, cgst_total=cgst_total, sgst_total=sgst_total,
        igst_total=igst_total, total_tax=total_tax, round_off=grand_total - exact,
        grand_total=grand_total,
    )
