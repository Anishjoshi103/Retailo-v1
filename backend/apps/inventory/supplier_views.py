from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from apps.tenancy.models import Membership

from .models import Supplier
from .supplier_serializers import SupplierSerializer
from .views import active_tenant_membership


class SupplierListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupplierSerializer

    def get_queryset(self):
        tenant_id = active_tenant_membership(self.request)
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
        context["tenant_id"] = active_tenant_membership(self.request)
        return context

    def perform_create(self, serializer):
        tenant_id = active_tenant_membership(self.request)
        membership_id = self.request.auth.get("membership_id") if self.request.auth else None
        membership = Membership.objects.filter(pk=membership_id, tenant_id=tenant_id, user=self.request.user, is_active=True).first()
        if membership is None or membership.role not in {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MANAGER}:
            raise PermissionDenied("Store manager permissions are required to create suppliers.")
        serializer.save(tenant_id=tenant_id)
