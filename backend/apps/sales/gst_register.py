"""GST sales register: the tables an accountant files a GSTR-1 style return from.

Three tables, all net of returns for the period and covering the branches the caller may see:

* ``rates``: taxable value and tax by place of supply and tax rate (B2C small supplies).
* ``hsn``: HSN-wise summary with net quantity, value, taxable value and tax.
* ``documents``: first and last invoice and credit note numbers per branch, and how many were issued.

Everything is summed from the posted invoice and credit note lines, so it always agrees with the sales
summary. It is a working aid, not tax advice: every figure should be reviewed before filing.
"""

import csv
from decimal import Decimal
from io import StringIO

from django.db.models import Count, Max, Min, Sum
from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sales.models import CreditNote, CreditNoteLine, Sale, SaleLine
from apps.sales.report_views import PAISE, ZERO, report_scope

# Official unit quantity codes (UQC) for the units a product can have.
UQC = {"each": "NOS", "kg": "KGS", "g": "GMS", "l": "LTR", "ml": "MLT", "m": "MTR", "pack": "PAC"}
QUANTITY_PLACES = Decimal("0.001")
TABLES = ("rates", "hsn", "documents")
MONEY_KEYS = ("taxable", "cgst", "sgst", "igst", "value")


def _money(value: Decimal) -> str:
    return str(value.quantize(PAISE))


def _blank() -> dict:
    return {"taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO, "value": ZERO, "quantity": Decimal("0")}


def _grouped(lines, keys: tuple[str, ...]) -> dict:
    """Sum lines per group; the group is the tuple of values of ``keys``."""
    rows = (
        lines.order_by().values(*keys)
        .annotate(
            taxable=Sum("taxable_value"), cgst=Sum("cgst_amount"), sgst=Sum("sgst_amount"),
            igst=Sum("igst_amount"), value=Sum("line_total"), quantity=Sum("quantity"),
        )
    )
    return {tuple(row[key] for key in keys): row for row in rows}


def _accumulate(totals: dict, group: tuple, row: dict, sign: int) -> None:
    entry = totals.setdefault(group, _blank())
    for key in (*MONEY_KEYS, "quantity"):
        entry[key] += sign * (row[key] or Decimal("0"))


def build_register(membership, date_from, date_to, branches) -> dict:
    tenant_id = membership.tenant_id
    sale_lines = SaleLine.objects.for_tenant(tenant_id).filter(
        sale__branch__in=branches, sale__invoice_date__gte=date_from, sale__invoice_date__lte=date_to
    )
    credit_lines = CreditNoteLine.objects.for_tenant(tenant_id).filter(
        credit_note__branch__in=branches, credit_note__credit_note_date__gte=date_from,
        credit_note__credit_note_date__lte=date_to,
    )

    # ---- rates: by place of supply and rate; sales positive, returns negative
    sales_by_rate = _grouped(sale_lines, ("sale__place_of_supply_state_code", "gst_rate"))
    returns_by_rate = _grouped(credit_lines, ("credit_note__place_of_supply_state_code", "gst_rate"))
    rates: dict[tuple, dict] = {}
    for group, row in sales_by_rate.items():
        _accumulate(rates, group, row, 1)
    for group, row in returns_by_rate.items():
        _accumulate(rates, group, row, -1)
    rate_rows = []
    for (place, rate), net in sorted(rates.items(), key=lambda item: (item[0][0], item[0][1])):
        sold, returned = sales_by_rate.get((place, rate)), returns_by_rate.get((place, rate))
        rate_rows.append({
            "place_of_supply": place, "gst_rate": str(rate.quantize(PAISE)),
            "taxable_value": _money(net["taxable"]), "igst": _money(net["igst"]), "cgst": _money(net["cgst"]),
            "sgst": _money(net["sgst"]), "cess": "0.00",
            "sales_taxable_value": _money(sold["taxable"] or ZERO) if sold else "0.00",
            "returns_taxable_value": _money(returned["taxable"] or ZERO) if returned else "0.00",
        })

    # ---- hsn: by HSN code, unit and rate
    hsn_keys = ("hsn_code", "unit", "gst_rate")
    sold_hsn = _grouped(sale_lines, hsn_keys)
    returned_hsn = _grouped(credit_lines, hsn_keys)
    hsn: dict[tuple, dict] = {}
    for group, row in sold_hsn.items():
        _accumulate(hsn, group, row, 1)
    for group, row in returned_hsn.items():
        _accumulate(hsn, group, row, -1)
    names = {
        (row["hsn_code"], row["unit"], row["gst_rate"]): row["name"]
        for row in sale_lines.order_by().values("hsn_code", "unit", "gst_rate").annotate(name=Min("name"))
    }
    hsn_rows = []
    for (code, unit, rate), net in sorted(hsn.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
        hsn_rows.append({
            "hsn_code": code, "description": names.get((code, unit, rate), ""), "uqc": UQC.get(unit, "OTH"),
            "quantity": str(net["quantity"].quantize(QUANTITY_PLACES)), "total_value": _money(net["value"]),
            "taxable_value": _money(net["taxable"]), "igst": _money(net["igst"]), "cgst": _money(net["cgst"]),
            "sgst": _money(net["sgst"]), "cess": "0.00", "gst_rate": str(rate.quantize(PAISE)),
        })

    # ---- documents: number ranges per branch
    documents = []
    for label, queryset, number, branch_path in (
        ("Invoices for outward supply", Sale.objects.for_tenant(tenant_id).filter(branch__in=branches, invoice_date__gte=date_from, invoice_date__lte=date_to), "invoice_number", "branch__code"),
        ("Credit notes", CreditNote.objects.for_tenant(tenant_id).filter(branch__in=branches, credit_note_date__gte=date_from, credit_note_date__lte=date_to), "credit_note_number", "branch__code"),
    ):
        rows = queryset.order_by().values(branch_path).annotate(first=Min(number), last=Max(number), total=Count("id")).order_by(branch_path)
        for row in rows:
            documents.append({
                "document_type": label, "series": row[branch_path], "from": row["first"], "to": row["last"],
                "total": row["total"], "cancelled": 0,
            })

    totals = {key: _money(sum((entry[key] for entry in rates.values()), ZERO)) for key in ("taxable", "cgst", "sgst", "igst")}
    totals["total_tax"] = _money(sum((entry["cgst"] + entry["sgst"] + entry["igst"] for entry in rates.values()), ZERO))
    return {
        "rates": rate_rows, "hsn": hsn_rows, "documents": documents,
        "totals": {"taxable_value": totals["taxable"], "cgst": totals["cgst"], "sgst": totals["sgst"], "igst": totals["igst"], "total_tax": totals["total_tax"]},
        "missing_hsn_lines": sale_lines.filter(hsn_code="").count(),
    }


class GstRegisterView(APIView):
    """JSON register for the screen. Owners, admins, managers and accountants only."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        membership, date_from, date_to, branches, branch_id = report_scope(request)
        register = build_register(membership, date_from, date_to, branches)
        return Response({
            "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
            "branch_id": str(branch_id) if branch_id else None, "branch_count": branches.count(), **register,
        })


def _safe(text) -> str:
    """Stop a spreadsheet treating a text cell as a formula (CSV injection)."""
    value = str(text)
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


CSV_COLUMNS = {
    "rates": (
        ("Place of supply (state code)", "place_of_supply", True), ("Tax rate %", "gst_rate", False), ("Taxable value", "taxable_value", False),
        ("IGST", "igst", False), ("CGST", "cgst", False), ("SGST/UTGST", "sgst", False), ("Cess", "cess", False),
    ),
    "hsn": (
        ("HSN", "hsn_code", True), ("Description", "description", True), ("UQC", "uqc", False), ("Total quantity", "quantity", False),
        ("Total value", "total_value", False), ("Taxable value", "taxable_value", False), ("IGST", "igst", False),
        ("CGST", "cgst", False), ("SGST/UTGST", "sgst", False), ("Cess", "cess", False), ("Tax rate %", "gst_rate", False),
    ),
    "documents": (
        ("Document type", "document_type", True), ("Series (branch)", "series", True), ("From", "from", True), ("To", "to", True),
        ("Total number", "total", False), ("Cancelled", "cancelled", False),
    ),
}


class GstRegisterCsvView(APIView):
    """One register table as a CSV download: ``?table=rates|hsn|documents`` plus the usual date and branch filters."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        membership, date_from, date_to, branches, _branch_id = report_scope(request)
        table = request.query_params.get("table", "")
        if table not in TABLES:
            raise ValidationError({"table": f"Choose one of: {', '.join(TABLES)}."})
        rows = build_register(membership, date_from, date_to, branches)[table]
        buffer = StringIO()
        writer = csv.writer(buffer)
        columns = CSV_COLUMNS[table]
        writer.writerow([header for header, _key, _text in columns])
        for row in rows:
            writer.writerow([_safe(row[key]) if text else row[key] for _header, key, text in columns])
        response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="gst-{table}-{date_from.isoformat()}-to-{date_to.isoformat()}.csv"'
        return response
