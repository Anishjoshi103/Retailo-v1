import hashlib
import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.models import InventoryBalance, StockMovement
from apps.sales.models import Sale, SaleLine, SalePayment
from apps.sales.numbering import InvoiceNumberError, allocate_invoice_number
from apps.sales.pricing import price_sale
from apps.sales.serializers import SaleInputSerializer
from apps.tenancy.permissions import require_membership_role

SELLING_ROLES = {"owner", "admin", "manager", "cashier"}
STOCK_OVERRIDE_ROLES = {"owner", "admin", "manager"}


class SaleCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        membership = require_membership_role(
            request, SELLING_ROLES, "Cashier, manager or administrator permissions are required to sell."
        )
        tenant_id = membership.tenant_id
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 128:
            return Response({"detail": "A valid Idempotency-Key header is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SaleInputSerializer(
            data=request.data, context={"tenant_id": tenant_id, "membership_id": str(membership.pk)}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        override = data["allow_negative_stock"]
        if override and membership.role not in STOCK_OVERRIDE_ROLES:
            raise PermissionDenied("Manager permissions are required to sell below available stock.")
        branch = data["branch"]
        request_hash = self._request_hash(data)

        try:
            with transaction.atomic():
                prior = Sale.objects.for_tenant(tenant_id).filter(idempotency_key=key).first()
                if prior:
                    return self._replay(prior, request_hash)
                if not branch.state_code:
                    raise ValidationError({"branch_id": "Set the branch's GST state code before issuing invoices."})
                priced = price_sale(
                    [(line["product"], line["quantity"]) for line in data["lines"]],
                    seller_state_code=branch.state_code,
                    place_of_supply_state_code=branch.state_code,
                )
                paid = sum((p["amount"] for p in data["payments"]), Decimal("0.00"))
                if paid != priced.grand_total:
                    raise ValidationError({"payments": f"Payments must total the invoice amount {priced.grand_total}."})
                try:
                    invoice_number = allocate_invoice_number(tenant_id=tenant_id, branch=branch)
                except InvoiceNumberError as exc:
                    raise ValidationError({"branch_id": str(exc)}) from exc
                sale = Sale.objects.create(
                    tenant_id=tenant_id, branch=branch, invoice_number=invoice_number,
                    invoice_date=timezone.localdate(), seller_gstin=branch.gstin,
                    seller_state_code=branch.state_code,
                    place_of_supply_state_code=branch.state_code,
                    customer_name=data["customer_name"], taxable_total=priced.taxable_total,
                    cgst_total=priced.cgst_total, sgst_total=priced.sgst_total,
                    igst_total=priced.igst_total, total_tax=priced.total_tax,
                    round_off=priced.round_off, grand_total=priced.grand_total,
                    idempotency_key=key, request_hash=request_hash, created_by=request.user,
                )
                # Lock balances in a stable order so concurrent sales cannot deadlock.
                for line in sorted(priced.lines, key=lambda item: str(item.product.id)):
                    self._deduct_stock(tenant_id, branch, line, sale, override, request.user)
                    product = line.product
                    SaleLine.objects.create(
                        tenant_id=tenant_id, sale=sale, product=product, sku=product.sku,
                        name=product.name, hsn_code=product.hsn_code, unit=product.unit,
                        quantity=line.quantity, unit_price=line.unit_price, gst_rate=line.gst_rate,
                        taxable_value=line.taxable_value, cgst_amount=line.cgst_amount,
                        sgst_amount=line.sgst_amount, igst_amount=line.igst_amount,
                        line_total=line.line_total,
                    )
                for payment in data["payments"]:
                    SalePayment.objects.create(
                        tenant_id=tenant_id, sale=sale, method=payment["method"],
                        amount=payment["amount"], reference=payment["reference"].strip(),
                    )
        except IntegrityError as exc:
            # A competing request may have committed the same key after our lookup.
            prior = Sale.objects.for_tenant(tenant_id).filter(idempotency_key=key).first()
            if prior is not None:
                return self._replay(prior, request_hash)
            raise APIException("The sale conflicted with another request. Retry with the same Idempotency-Key.") from exc
        return Response(self._response(sale, replayed=False), status=status.HTTP_201_CREATED)

    @staticmethod
    def _request_hash(data) -> str:
        canonical = {
            "branch_id": str(data["branch"].id),
            "customer_name": data["customer_name"],
            "allow_negative_stock": data["allow_negative_stock"],
            "lines": sorted(
                ({"product_id": str(line["product_id"]), "quantity": str(line["quantity"])} for line in data["lines"]),
                key=lambda item: item["product_id"],
            ),
            "payments": sorted(
                (
                    {"method": p["method"], "amount": str(p["amount"]), "reference": p["reference"].strip()}
                    for p in data["payments"]
                ),
                key=lambda item: (item["method"], item["amount"], item["reference"]),
            ),
        }
        return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _replay(self, prior, request_hash):
        if prior.request_hash != request_hash:
            return Response({"detail": "Idempotency-Key was already used for a different sale."}, status=status.HTTP_409_CONFLICT)
        return Response(self._response(prior, replayed=True), status=status.HTTP_200_OK)

    @staticmethod
    def _deduct_stock(tenant_id, branch, line, sale, override, user):
        product = line.product
        balance = InventoryBalance.objects.for_tenant(tenant_id).select_for_update().filter(
            branch=branch, product=product
        ).first()
        on_hand = balance.quantity_on_hand if balance else Decimal("0")
        short = on_hand < line.quantity
        if short and not override:
            raise ValidationError({"lines": f"Insufficient stock for {product.sku}: {on_hand} on hand, {line.quantity} requested."})
        if balance is None:
            balance, _ = InventoryBalance.objects.for_tenant(tenant_id).get_or_create(
                tenant_id=tenant_id, branch=branch, product=product
            )
        InventoryBalance.objects.for_tenant(tenant_id).filter(pk=balance.pk).update(
            quantity_on_hand=F("quantity_on_hand") - line.quantity
        )
        StockMovement.objects.create(
            tenant_id=tenant_id, branch=branch, product=product, quantity_delta=-line.quantity,
            reason=StockMovement.Reason.SALE, reference=sale.invoice_number,
            idempotency_key=f"sale:{sale.id}:{product.id}",
            note="Sold below available stock (manager override)" if short else "",
            created_by=user,
        )

    @staticmethod
    def _response(sale, replayed):
        tenant_id = sale.tenant_id
        money = str
        return {
            "id": str(sale.id), "invoice_number": sale.invoice_number,
            "invoice_date": sale.invoice_date.isoformat(), "branch_id": str(sale.branch_id),
            "customer_name": sale.customer_name, "seller_gstin": sale.seller_gstin,
            "place_of_supply_state_code": sale.place_of_supply_state_code,
            "taxable_total": money(sale.taxable_total), "cgst_total": money(sale.cgst_total),
            "sgst_total": money(sale.sgst_total), "igst_total": money(sale.igst_total),
            "total_tax": money(sale.total_tax), "round_off": money(sale.round_off),
            "grand_total": money(sale.grand_total), "replayed": replayed,
            "lines": [
                {
                    "product_id": str(line.product_id), "sku": line.sku, "name": line.name,
                    "hsn_code": line.hsn_code, "unit": line.unit, "quantity": money(line.quantity),
                    "unit_price": money(line.unit_price), "gst_rate": money(line.gst_rate),
                    "taxable_value": money(line.taxable_value), "cgst_amount": money(line.cgst_amount),
                    "sgst_amount": money(line.sgst_amount), "igst_amount": money(line.igst_amount),
                    "line_total": money(line.line_total),
                }
                for line in SaleLine.objects.for_tenant(tenant_id).filter(sale=sale).order_by("id")
            ],
            "payments": [
                {"method": p.method, "amount": money(p.amount), "reference": p.reference}
                for p in SalePayment.objects.for_tenant(tenant_id).filter(sale=sale).order_by("id")
            ],
        }
