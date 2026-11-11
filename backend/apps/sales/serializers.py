from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product
from apps.sales.models import SalePayment
from apps.tenancy.access import membership_can_access_branch
from apps.tenancy.models import Branch, Membership

MAX_LINES = 200
MAX_PAYMENTS = 10


class SaleLineInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))


class SalePaymentInputSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=SalePayment.Method.choices)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class SaleInputSerializer(serializers.Serializer):
    """Prices and tax are never client-supplied; only products, quantities and tenders are."""

    branch_id = serializers.UUIDField()
    customer_name = serializers.CharField(max_length=180, required=False, allow_blank=True, default="")
    allow_negative_stock = serializers.BooleanField(required=False, default=False)
    lines = SaleLineInputSerializer(many=True, min_length=1, max_length=MAX_LINES)
    payments = SalePaymentInputSerializer(many=True, min_length=1, max_length=MAX_PAYMENTS)

    def validate(self, attrs):
        tenant_id = self.context["tenant_id"]
        membership = Membership.objects.filter(
            pk=self.context["membership_id"], tenant_id=tenant_id, is_active=True,
            tenant__status="active",
        ).first()
        branch = Branch.objects.for_tenant(tenant_id).filter(
            pk=attrs["branch_id"], is_active=True
        ).first()
        if membership is None or branch is None or not membership_can_access_branch(
            membership, attrs["branch_id"]
        ):
            raise serializers.ValidationError({"branch_id": "Select a branch assigned to your membership."})
        product_ids = [line["product_id"] for line in attrs["lines"]]
        if len(set(product_ids)) != len(product_ids):
            raise serializers.ValidationError({"lines": "Each product may appear only once; combine quantities."})
        products = {
            product.id: product
            for product in Product.objects.for_tenant(tenant_id).filter(pk__in=product_ids, is_active=True)
        }
        if len(products) != len(product_ids):
            raise serializers.ValidationError({"lines": "Select active products in your store."})
        attrs["branch"] = branch
        for line in attrs["lines"]:
            line["product"] = products[line["product_id"]]
        attrs["customer_name"] = attrs["customer_name"].strip()
        return attrs


class ReturnLineInputSerializer(serializers.Serializer):
    sale_line_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))


class ReturnInputSerializer(serializers.Serializer):
    """Return items from one sale. Amounts are never client-supplied; they are reversed from the sale."""

    reason = serializers.CharField(max_length=200, trim_whitespace=True)
    lines = ReturnLineInputSerializer(many=True, min_length=1, max_length=MAX_LINES)

    def validate_lines(self, lines):
        ids = [line["sale_line_id"] for line in lines]
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError("Each item may appear only once; combine quantities.")
        return lines
