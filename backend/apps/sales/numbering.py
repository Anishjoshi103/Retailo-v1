"""Gapless per-branch invoice numbers: ``INV-<BRANCHCODE>-<6 digit serial>``.

GST limits an invoice number to 16 characters of letters, digits, hyphen and slash,
unique within a financial year. The serial deliberately does not reset each year, so
numbers stay unique across years. With the fixed ``INV-`` prefix and a 6 digit serial,
a branch code can be at most 5 characters (``INV-`` + 5 + ``-`` + 6 = 16).
"""

import re

from django.db import connection, transaction

from apps.sales.models import InvoiceSequence

MAX_INVOICE_NUMBER_LENGTH = 16
_ALLOWED = re.compile(r"[A-Za-z0-9/-]+")


class InvoiceNumberError(ValueError):
    """The branch cannot issue a valid GST invoice number."""


def format_invoice_number(branch_code: str, serial: int) -> str:
    number = f"INV-{branch_code.strip().upper()}-{serial:06d}"
    if not _ALLOWED.fullmatch(number):
        raise InvoiceNumberError(
            "Branch code may contain only letters, digits, hyphen and slash to issue invoices."
        )
    if len(number) > MAX_INVOICE_NUMBER_LENGTH:
        raise InvoiceNumberError(
            "Invoice number would exceed 16 characters; use a branch code of at most 5 characters."
        )
    return number


def allocate_invoice_number(*, tenant_id, branch) -> str:
    """Reserve the branch's next invoice number.

    Must run inside the same transaction that creates the sale, so a failed sale rolls
    the counter back and no number is ever skipped. The sequence row is locked until
    that transaction ends, which serialises concurrent sales for one branch.
    """
    if not connection.in_atomic_block:
        raise RuntimeError("allocate_invoice_number() must run inside transaction.atomic().")
    if branch.tenant_id != tenant_id:
        raise InvoiceNumberError("Branch does not belong to this store.")
    # The inner savepoint also undoes a first-time sequence row if the number is invalid.
    sequences = InvoiceSequence.objects.for_tenant(tenant_id)
    with transaction.atomic():
        sequence, _ = sequences.select_for_update().get_or_create(
            tenant_id=tenant_id, branch=branch
        )
        number = format_invoice_number(branch.code, sequence.last_number + 1)
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
    return number
