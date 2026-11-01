from rest_framework import generics, permissions
from apps.tenancy.permissions import active_tenant_membership, require_membership_role

from .models import Supplier
from .supplier_serializers import SupplierSerializer


class SupplierListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupplierSerializer

    def get_queryset(self):
        tenant_id = active_tenant_membership(self.request).tenant_id
        queryset = Supplier.objects.for_tenant(tenant_id)
        search = self.request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q
            queryset = queryset.filter(Q(name__icontains=search) | Q(gstin__icontains=search) | Q(phone__icontains=search))
        active = self.request.query_params.get("active")
        if active == "true":
            queryset = queryset.filter(is_active=True)
        elif active == "false":
            queryset = queryset.filter(is_active=False)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant_id"] = active_tenant_membership(self.request).tenant_id
        return context

    def perform_create(self, serializer):
        membership = require_membership_role(
            self.request, {"owner", "admin", "manager"},
            "Store manager permissions are required to create suppliers.",
        )
        tenant_id = membership.tenant_id
        serializer.save(tenant_id=tenant_id)
