"""Sales reports for owners, admins, managers and accountants (financial data; cashiers are refused)."""

from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sales.models import CreditNote, Sale, SalePayment
from apps.tenancy.access import authorized_branches, membership_can_access_branch
from apps.tenancy.listing import uuid_param
from apps.tenancy.permissions import require_membership_role

REPORT_ROLES = {"owner", "admin", "manager", "accountant"}
MAX_RANGE_DAYS = 366
PAISE = Decimal("0.01")
ZERO = Decimal("0.00")

# Both Sale and CreditNote carry these totals under the same names.
TOTAL_FIELDS = {
    "taxable_total": "taxable_total", "cgst_total": "cgst_total", "sgst_total": "sgst_total",
    "igst_total": "igst_total", "total_tax": "total_tax", "round_off": "round_off", "grand_total": "grand_total",
}


def _money(value) -> str:
    return str((value if value is not None else ZERO).quantize(PAISE))


def _date_param(params, name: str, default: date) -> date:
    raw = params.get(name)
    if not raw:
        return default
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({name: "Use the format YYYY-MM-DD."}) from exc


def _totals(queryset) -> dict:
    """Count and money totals of a queryset of sales or credit notes."""
    aggregates = {key: Sum(field) for key, field in TOTAL_FIELDS.items()}
    # aggregate() ignores the model's default ordering, so no ORDER BY can leak in.
    row = queryset.aggregate(count=Count("id"), **aggregates)
    return {"count": row["count"], **{key: _money(row[key]) for key in TOTAL_FIELDS}}


class SalesSummaryReportView(APIView):
    """Sales, returns, tax and tenders for a date range and one or all of the caller's branches."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        membership = require_membership_role(
            request, REPORT_ROLES, "Sales reports are available to owners, administrators, managers and accountants."
        )
        today = timezone.localdate()
        date_from = _date_param(request.query_params, "date_from", today)
        # No end date means a one-day report for the start date (today by default).
        date_to = _date_param(request.query_params, "date_to", date_from)
        if date_to < date_from:
            raise ValidationError({"date_to": "The end date is before the start date."})
        # Counted inclusively: 2025-01-01 to 2025-12-31 is 365 days.
        if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
            raise ValidationError({"date_to": f"Choose a range of at most {MAX_RANGE_DAYS} days."})

        branches = authorized_branches(membership)
        branch_id = uuid_param(request.query_params, "branch_id")
        if branch_id is not None:
            if not membership_can_access_branch(membership, branch_id):
                raise PermissionDenied("You do not have access to the requested branch.")
            branches = branches.filter(pk=branch_id)

        tenant_id = membership.tenant_id
        sales = Sale.objects.for_tenant(tenant_id).filter(
            branch__in=branches, invoice_date__gte=date_from, invoice_date__lte=date_to
        )
        returns = CreditNote.objects.for_tenant(tenant_id).filter(
            branch__in=branches, credit_note_date__gte=date_from, credit_note_date__lte=date_to
        )
        sales_totals = _totals(sales)
        return_totals = _totals(returns)

        payments = (
            SalePayment.objects.for_tenant(tenant_id)
            .filter(sale__branch__in=branches, sale__invoice_date__gte=date_from, sale__invoice_date__lte=date_to)
            .order_by().values("method").annotate(amount=Sum("amount"), count=Count("id")).order_by("method")
        )
        days: dict[date, dict] = {}
        for row in sales.order_by().values("invoice_date").annotate(count=Count("id"), total=Sum("grand_total")):
            day = days.setdefault(row["invoice_date"], {"sales_count": 0, "sales": ZERO, "returns_count": 0, "returns": ZERO})
            day["sales_count"], day["sales"] = row["count"], row["total"]
        for row in returns.order_by().values("credit_note_date").annotate(count=Count("id"), total=Sum("grand_total")):
            day = days.setdefault(row["credit_note_date"], {"sales_count": 0, "sales": ZERO, "returns_count": 0, "returns": ZERO})
            day["returns_count"], day["returns"] = row["count"], row["total"]

        def net(key):
            return _money(Decimal(sales_totals[key]) - Decimal(return_totals[key]))

        return Response({
            "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
            "branch_id": str(branch_id) if branch_id else None, "branch_count": branches.count(),
            "sales": sales_totals,
            "returns": return_totals,
            "net": {"taxable_total": net("taxable_total"), "total_tax": net("total_tax"), "grand_total": net("grand_total")},
            # Refunds are always cash, so cash in hand is cash sales less returns.
            "payments": [{"method": row["method"], "amount": _money(row["amount"]), "count": row["count"]} for row in payments],
            "by_day": [
                {
                    "date": day.isoformat(), "sales_count": values["sales_count"], "sales_total": _money(values["sales"]),
                    "returns_count": values["returns_count"], "returns_total": _money(values["returns"]),
                    "net_total": _money(values["sales"] - values["returns"]),
                }
                for day, values in sorted(days.items())
            ],
        })
