from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.access import membership_can_access_branch
from apps.tenancy.branch_serializers import BranchGstIdentitySerializer
from apps.tenancy.models import Branch
from apps.tenancy.permissions import require_membership_role


class BranchDetailView(APIView):
    """Owner/admin update of a branch's GST identity (GSTIN and state code)."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, branch_id):
        membership = require_membership_role(
            request, {"owner", "admin"},
            "Store administrator permissions are required to change branch GST details.",
        )
        # Unknown, foreign-tenant and ungranted branches are indistinguishable.
        if not membership_can_access_branch(membership, branch_id):
            raise NotFound("Branch not found.")
        branch = Branch.objects.for_tenant(membership.tenant_id).filter(pk=branch_id).first()
        if branch is None:
            raise NotFound("Branch not found.")
        serializer = BranchGstIdentitySerializer(instance=branch, data=request.data)
        serializer.is_valid(raise_exception=True)
        branch.gstin = serializer.validated_data["gstin"]
        branch.state_code = serializer.validated_data["state_code"]
        branch.save(update_fields=["gstin", "state_code", "updated_at"])
        return Response({
            "id": str(branch.id), "name": branch.name, "code": branch.code,
            "gstin": branch.gstin, "state_code": branch.state_code,
        })
