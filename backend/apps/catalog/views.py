from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from apps.tenancy.models import Membership
from apps.tenancy.permissions import active_tenant_membership

from .models import Product
from .serializers import ProductSerializer


class ProductListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer

    def get_queryset(self):
        tenant_id = active_tenant_membership(self.request).tenant_id
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
        context["tenant_id"] = active_tenant_membership(self.request).tenant_id
        return context

    def perform_create(self, serializer):
        membership = active_tenant_membership(self.request)
        tenant_id = membership.tenant_id
        if membership.role not in {
            Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MANAGER
        }:
            raise PermissionDenied("Store manager permissions are required to create products.")
        serializer.save(tenant_id=tenant_id)
