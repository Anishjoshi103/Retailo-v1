"""Credit note pricing: reverse a sale line's tax for a returned quantity.

For each component (taxable value, CGST, SGST, IGST) the amount returned *so far* is the
original line's amount x (cumulative quantity returned / quantity sold), rounded half-up
to paise. A return is the difference between the running totals after and before it. This
makes repeated partial returns telescope to the original line exactly (the final return
takes the exact remainder), never go negative and never exceed the sale, and keeps
CGST == SGST because the original had equal halves.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from apps.sales.pricing import PAISE, RUPEE, ZERO


def cumulative_share(amount: Decimal, returned_quantity: Decimal, sold_quantity: Decimal) -> Decimal:
    """Portion of ``amount`` attributable to ``returned_quantity`` of ``sold_quantity``."""
    if returned_quantity >= sold_quantity:
        return amount
    return (amount * returned_quantity / sold_quantity).quantize(PAISE, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ReturnedLine:
    sale_line: object
    quantity: Decimal
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class PricedReturn:
    lines: list[ReturnedLine]
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    total_tax: Decimal
    round_off: Decimal
    grand_total: Decimal


def price_return_line(sale_line, returned_before: Decimal, quantity: Decimal) -> ReturnedLine:
    """Amounts for returning ``quantity`` more of ``sale_line`` after ``returned_before``."""
    sold = sale_line.quantity
    after = returned_before + quantity

    def part(amount: Decimal) -> Decimal:
        return cumulative_share(amount, after, sold) - cumulative_share(amount, returned_before, sold)

    taxable = part(sale_line.taxable_value)
    cgst = part(sale_line.cgst_amount)
    sgst = part(sale_line.sgst_amount)
    igst = part(sale_line.igst_amount)
    return ReturnedLine(
        sale_line=sale_line, quantity=quantity, taxable_value=taxable, cgst_amount=cgst,
        sgst_amount=sgst, igst_amount=igst, line_total=taxable + cgst + sgst + igst,
    )


def price_return(items: Iterable[tuple[object, Decimal, Decimal]]) -> PricedReturn:
    """Price ``(sale_line, returned_before, quantity)`` items into credit note totals.

    The refund is the exact total rounded half-up to the rupee, like the invoice it reverses,
    so returning every line of a sale refunds exactly the invoice's grand total.
    """
    lines = [price_return_line(sale_line, before, quantity) for sale_line, before, quantity in items]
    taxable_total = sum((line.taxable_value for line in lines), ZERO)
    cgst_total = sum((line.cgst_amount for line in lines), ZERO)
    sgst_total = sum((line.sgst_amount for line in lines), ZERO)
    igst_total = sum((line.igst_amount for line in lines), ZERO)
    total_tax = cgst_total + sgst_total + igst_total
    exact = taxable_total + total_tax
    grand_total = exact.quantize(RUPEE, rounding=ROUND_HALF_UP).quantize(PAISE)
    return PricedReturn(
        lines=lines, taxable_total=taxable_total, cgst_total=cgst_total, sgst_total=sgst_total,
        igst_total=igst_total, total_tax=total_tax, round_off=grand_total - exact, grand_total=grand_total,
    )
