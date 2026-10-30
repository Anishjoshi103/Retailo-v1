from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from apps.tenancy.models import Membership
from .models import Product
from .serializers import ProductSerializer


def active_tenant_membership(request):
    auth = request.auth
    tenant_id = auth.get("tenant_id") if auth else None
    membership_id = auth.get("membership_id") if auth else None
    if not tenant_id or not membership_id or not Membership.objects.filter(
        pk=membership_id, tenant_id=tenant_id, user=request.user, is_active=True, tenant__status="active"
    ).exists():
        raise PermissionDenied("An active store membership is required.")
    return tenant_id


class ProductListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer

    def get_queryset(self):
        tenant_id = active_tenant_membership(self.request)
        queryset = Product.objects.for_tenant(tenant_id)
        search = self.request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q
            queryset = queryset.filter(Q(name__icontains=search) | Q(sku__icontains=search) | Q(barcode__icontains=search))
        if self.request.query_params.get("active") == "true":
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant_id"] = active_tenant_membership(self.request)
        return context

    def perform_create(self, serializer):
        tenant_id = active_tenant_membership(self.request)
        membership_id = self.request.auth.get("membership_id")
        membership = Membership.objects.filter(
            pk=membership_id, tenant_id=tenant_id, user=self.request.user, is_active=True
        ).first()
        if membership is None or membership.role not in {
            Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MANAGER
        }:
            raise PermissionDenied("Store manager permissions are required to create products.")
        serializer.save(tenant_id=tenant_id)
