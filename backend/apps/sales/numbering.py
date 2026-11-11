"""Gapless per-branch document numbers.

Invoices: ``INV-<BRANCHCODE>-<6 digit serial>``. Credit notes: ``CN-<BRANCHCODE>-<6 digit serial>``.

GST limits a document number to 16 characters of letters, digits, hyphen and slash,
unique within a financial year. The serial deliberately does not reset each year, so
numbers stay unique across years. With the ``INV-`` prefix and a 6 digit serial, a branch
code can be at most 5 characters (``INV-`` + 5 + ``-`` + 6 = 16); credit notes are shorter.
"""

import re

from django.db import connection, transaction

from apps.sales.models import CreditNoteSequence, InvoiceSequence

MAX_INVOICE_NUMBER_LENGTH = 16
_ALLOWED = re.compile(r"[A-Za-z0-9/-]+")


class InvoiceNumberError(ValueError):
    """The branch cannot issue a valid GST document number."""


def _format_number(prefix: str, label: str, branch_code: str, serial: int) -> str:
    number = f"{prefix}-{branch_code.strip().upper()}-{serial:06d}"
    if not _ALLOWED.fullmatch(number):
        raise InvoiceNumberError(
            "Branch code may contain only letters, digits, hyphen and slash to issue invoices."
        )
    if len(number) > MAX_INVOICE_NUMBER_LENGTH:
        raise InvoiceNumberError(
            f"{label} would exceed 16 characters; use a branch code of at most 5 characters."
        )
    return number


def format_invoice_number(branch_code: str, serial: int) -> str:
    return _format_number("INV", "Invoice number", branch_code, serial)


def format_credit_note_number(branch_code: str, serial: int) -> str:
    return _format_number("CN", "Credit note number", branch_code, serial)


def _allocate(sequence_model, formatter, *, tenant_id, branch) -> str:
    """Reserve the branch's next number from ``sequence_model``.

    Must run inside the same transaction that creates the document, so a failed document
    rolls the counter back and no number is ever skipped. The sequence row is locked until
    that transaction ends, which serialises concurrent documents for one branch.
    """
    if not connection.in_atomic_block:
        raise RuntimeError("Document numbers must be allocated inside transaction.atomic().")
    if branch.tenant_id != tenant_id:
        raise InvoiceNumberError("Branch does not belong to this store.")
    # The inner savepoint also undoes a first-time sequence row if the number is invalid.
    sequences = sequence_model.objects.for_tenant(tenant_id)
    with transaction.atomic():
        sequence, _ = sequences.select_for_update().get_or_create(
            tenant_id=tenant_id, branch=branch
        )
        number = formatter(branch.code, sequence.last_number + 1)
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
    return number


def allocate_invoice_number(*, tenant_id, branch) -> str:
    """Reserve the branch's next invoice number (see ``_allocate``)."""
    return _allocate(InvoiceSequence, format_invoice_number, tenant_id=tenant_id, branch=branch)


def allocate_credit_note_number(*, tenant_id, branch) -> str:
    """Reserve the branch's next credit note number (see ``_allocate``)."""
    return _allocate(CreditNoteSequence, format_credit_note_number, tenant_id=tenant_id, branch=branch)
