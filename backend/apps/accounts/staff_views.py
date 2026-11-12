"""Staff management: owners and admins invite people, set roles and branches, deactivate access.

An invited person gets an active account with no usable password and an emailed
set-your-password link (the same signed token the password-reset flow uses), so they can
sign in only after proving they own the mailbox. Each login resolves to the user's oldest
active store, so an email that already has an account is refused rather than silently
adding a second store the person could never switch to.
"""

import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.views import _frontend_url, _send_account_email
from apps.tenancy.access import authorized_branches
from apps.tenancy.models import BranchAccess, Membership
from apps.tenancy.permissions import require_membership_role

logger = logging.getLogger(__name__)

STAFF_MANAGERS = {"owner", "admin"}
# Roles each manager may assign to, and therefore also change or deactivate. Nobody can
# create an owner, and an admin cannot touch other admins or the owner.
ASSIGNABLE_ROLES = {
    "owner": {"admin", "manager", "cashier", "accountant"},
    "admin": {"manager", "cashier", "accountant"},
}
CREATABLE_ROLES = ["admin", "manager", "cashier", "accountant"]
MAX_BRANCHES = 50


class StaffInviteSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    display_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="", trim_whitespace=True)
    role = serializers.ChoiceField(choices=CREATABLE_ROLES)
    branch_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=MAX_BRANCHES)

    def validate_email(self, value):
        return value.strip().casefold()


class StaffUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=CREATABLE_ROLES, required=False)
    branch_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=MAX_BRANCHES, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide role, branch_ids and/or is_active.")
        return attrs


def _can_manage(actor, target) -> bool:
    return actor.pk != target.pk and target.role in ASSIGNABLE_ROLES.get(actor.role, set())


def _active_grants(tenant_id):
    return Prefetch(
        "branch_accesses",
        queryset=BranchAccess.objects.filter(is_active=True, branch__is_active=True, branch__tenant_id=tenant_id),
        to_attr="active_grants",
    )


def _serialize_member(member, actor):
    user = member.user
    return {
        "id": str(member.id),
        "email": user.email,
        "display_name": user.first_name,
        "role": member.role,
        "is_active": member.is_active,
        # No usable password yet: the person has been invited but has not set one.
        "invited": not user.has_usable_password(),
        "branch_ids": [str(grant.branch_id) for grant in getattr(member, "active_grants", [])],
        "is_self": member.pk == actor.pk,
        "can_manage": _can_manage(actor, member),
        "created_at": member.created_at.isoformat(),
    }


def _load_member(tenant_id, membership_id):
    member = (
        Membership.objects.filter(pk=membership_id, tenant_id=tenant_id)
        .select_related("user", "tenant").prefetch_related(_active_grants(tenant_id)).first()
    )
    if member is None:
        raise NotFound("Member not found.")
    return member


def _requested_branches(actor, branch_ids):
    """Branches the caller may grant: only ones they hold themselves, active and in their store."""
    requested = set(branch_ids)
    allowed = set(authorized_branches(actor).values_list("id", flat=True))
    if not requested <= allowed:
        raise ValidationError({"branch_ids": "Select branches assigned to your membership."})
    return requested


def _send_invite(member) -> bool:
    user = member.user
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = _frontend_url("/auth/password-reset/confirm", {"uid": uid, "token": token})
    days = max(1, int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200)) // 86400)
    role = Membership.Role(member.role).label
    try:
        _send_account_email(
            subject=f"You have been added to {member.tenant.name} on Retailo",
            message=(
                f"You have been added to {member.tenant.name} on Retailo as {role}.\n\n"
                f"Set your password to get started:\n{link}\n\n"
                f"The link works for {days} days. If it expires, use 'Forgot password' with this email address.\n\n"
                "If you were not expecting this, you can ignore this email."
            ),
            recipient=user.email,
        )
    except (RuntimeError, ValueError, OSError, SMTPException):
        logger.exception("Staff invitation email delivery failed")
        return False
    return True


class StaffListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        actor = require_membership_role(request, STAFF_MANAGERS, "Store administrator permissions are required to manage staff.")
        members = (
            Membership.objects.filter(tenant_id=actor.tenant_id)
            .select_related("user").prefetch_related(_active_grants(actor.tenant_id)).order_by("created_at", "id")
        )
        return Response([_serialize_member(member, actor) for member in members])

    def post(self, request):
        actor = require_membership_role(request, STAFF_MANAGERS, "Store administrator permissions are required to manage staff.")
        serializer = StaffInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["role"] not in ASSIGNABLE_ROLES[actor.role]:
            raise PermissionDenied("You cannot assign that role.")
        branch_ids = _requested_branches(actor, data["branch_ids"])
        User = get_user_model()
        try:
            with transaction.atomic():
                if User.objects.filter(email__iexact=data["email"]).exists() or User.objects.filter(username__iexact=data["email"]).exists():
                    return Response({"detail": "This email address already has an account."}, status=status.HTTP_409_CONFLICT)
                user = User(username=data["email"], email=data["email"], first_name=data["display_name"], is_active=True)
                user.set_unusable_password()
                user.save()
                member = Membership.objects.create(tenant_id=actor.tenant_id, user=user, role=data["role"])
                BranchAccess.objects.bulk_create([BranchAccess(membership=member, branch_id=branch_id) for branch_id in branch_ids])
        except IntegrityError:
            return Response({"detail": "This email address already has an account."}, status=status.HTTP_409_CONFLICT)
        logger.info("staff invited tenant=%s actor=%s member=%s role=%s", actor.tenant_id, actor.pk, member.pk, member.role)
        invite_sent = _send_invite(Membership.objects.select_related("user", "tenant").get(pk=member.pk))
        created = _load_member(actor.tenant_id, member.pk)
        return Response({**_serialize_member(created, actor), "invite_sent": invite_sent}, status=status.HTTP_201_CREATED)


class StaffDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, membership_id):
        actor = require_membership_role(request, STAFF_MANAGERS, "Store administrator permissions are required to manage staff.")
        target = _load_member(actor.tenant_id, membership_id)
        if target.pk == actor.pk:
            raise PermissionDenied("You cannot change your own access.")
        if not _can_manage(actor, target):
            raise PermissionDenied("You do not have permission to change this member.")
        serializer = StaffUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "role" in data and data["role"] not in ASSIGNABLE_ROLES[actor.role]:
            raise PermissionDenied("You cannot assign that role.")
        with transaction.atomic():
            if "branch_ids" in data:
                self._apply_branches(actor, target, _requested_branches(actor, data["branch_ids"]))
            changed = []
            if "role" in data and data["role"] != target.role:
                target.role = data["role"]
                changed.append("role")
            if "is_active" in data and data["is_active"] != target.is_active:
                target.is_active = data["is_active"]
                changed.append("is_active")
            if changed:
                target.save(update_fields=changed)
        logger.info("staff updated tenant=%s actor=%s member=%s fields=%s", actor.tenant_id, actor.pk, target.pk, sorted(data))
        return Response(_serialize_member(_load_member(actor.tenant_id, membership_id), actor))

    @staticmethod
    def _apply_branches(actor, target, requested):
        """Set the target's grants within the branches the actor can see; leave the rest alone."""
        actor_ids = set(authorized_branches(actor).values_list("id", flat=True))
        existing = {access.branch_id: access for access in BranchAccess.objects.filter(membership=target)}
        kept_outside = {bid for bid, access in existing.items() if access.is_active and bid not in actor_ids}
        if not (kept_outside | requested):
            raise ValidationError({"branch_ids": "A member needs access to at least one branch."})
        for branch_id in requested:
            access = existing.get(branch_id)
            if access is None:
                BranchAccess.objects.create(membership=target, branch_id=branch_id)
            elif not access.is_active:
                access.is_active = True
                access.save(update_fields=["is_active"])
        for branch_id, access in existing.items():
            if branch_id in actor_ids and branch_id not in requested and access.is_active:
                access.is_active = False
                access.save(update_fields=["is_active"])


class StaffResendInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, membership_id):
        actor = require_membership_role(request, STAFF_MANAGERS, "Store administrator permissions are required to manage staff.")
        target = _load_member(actor.tenant_id, membership_id)
        if not _can_manage(actor, target):
            raise PermissionDenied("You do not have permission to change this member.")
        if target.user.has_usable_password():
            return Response({"detail": "This person has already set a password."}, status=status.HTTP_409_CONFLICT)
        return Response({"invite_sent": _send_invite(target)}, status=status.HTTP_202_ACCEPTED)
