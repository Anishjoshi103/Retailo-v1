import logging
import uuid
from smtplib import SMTPException
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.text import slugify
from rest_framework import status

from config.api_errors import api_error_response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenancy.models import Branch, Membership, Tenant

logger = logging.getLogger(__name__)

REFRESH_COOKIE = "retailo_refresh"
EMAIL_VERIFICATION_SALT = "retailo.accounts.email-verification.v1"
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24


def _cookie_options():
    return {
        "httponly": True,
        "secure": not settings.DEBUG and not getattr(settings, "IS_TEST_ENV", False),
        "samesite": getattr(settings, "AUTH_REFRESH_COOKIE_SAMESITE", "Lax"),
        "path": "/api/v1/auth/",
        "max_age": int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
    }


def _set_refresh_cookie(response, token):
    response.set_cookie(REFRESH_COOKIE, str(token), **_cookie_options())


def _clear_refresh_cookie(response):
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth/", samesite=getattr(settings, "AUTH_REFRESH_COOKIE_SAMESITE", "Lax"))


def _origin_is_allowed(request):
    origin = request.headers.get("Origin")
    if not origin:
        return True
    expected = f"{request.scheme}://{request.get_host()}"
    return origin.rstrip("/") == expected.rstrip("/")


def _frontend_url(path, query=None):
    base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("FRONTEND_BASE_URL must be configured to send account emails.")
    return f"{base}{path}" + (f"?{urlencode(query)}" if query else "")


def _send_account_email(*, subject, message, recipient):
    sender = getattr(settings, "DEFAULT_FROM_EMAIL", "")
    if not sender:
        raise RuntimeError("DEFAULT_FROM_EMAIL must be configured to send account emails.")
    send_mail(subject, message, sender, [recipient], fail_silently=False)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        store_name = str(request.data.get("store_name", "")).strip()
        email = str(request.data.get("email", "")).strip().casefold()
        password = request.data.get("password", "")
        if not store_name or len(store_name) > 120 or "@" not in email or not isinstance(password, str) or len(password) < 12:
            return api_error_response(code="validation_error", message="Enter a valid store name, email, and password of at least 12 characters.", status_code=status.HTTP_400_BAD_REQUEST, request=request)
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            # Keep duplicate and new-address responses indistinguishable.
            return Response({"detail": "If this address can be registered, verification instructions will be sent."}, status=status.HTTP_202_ACCEPTED)
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=email, email=email, password=password, is_active=False)
                base_slug = slugify(store_name)[:65].strip("-") or "store"
                slug = f"{base_slug}-{uuid.uuid4().hex[:10]}"
                tenant = Tenant.objects.create(name=store_name, slug=slug)
                Membership.objects.create(tenant=tenant, user=user, role=Membership.Role.OWNER, is_active=True)
                Branch.objects.create(tenant=tenant, name="Main Branch", code="MAIN", is_active=True)
                token = signing.dumps({"user_id": str(user.pk)}, salt=EMAIL_VERIFICATION_SALT)
                verify_url = _frontend_url("/auth/verify-email", {"token": token})
                _send_account_email(
                    subject="Verify your Retailo account",
                    message=f"Verify your Retailo account within 24 hours by opening:\n\n{verify_url}\n\nIf you did not request this, you can ignore this email.",
                    recipient=email,
                )
        except (IntegrityError, ValueError, RuntimeError, OSError, SMTPException):
            logger.exception("Registration setup or verification email delivery failed")
            return Response({"detail": "If this address can be registered, verification instructions will be sent."}, status=status.HTTP_202_ACCEPTED)
        return Response({"detail": "If this address can be registered, verification instructions will be sent."}, status=status.HTTP_202_ACCEPTED)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.data.get("token", "")
        try:
            payload = signing.loads(token, salt=EMAIL_VERIFICATION_SALT, max_age=EMAIL_VERIFICATION_MAX_AGE)
            user = get_user_model().objects.get(pk=payload["user_id"], is_active=False)
        except (signing.BadSignature, signing.SignatureExpired, KeyError, TypeError, ValueError, get_user_model().DoesNotExist):
            return Response(api_error_response(code="invalid_verification_token", message="Verification link is invalid or expired.", status_code=status.HTTP_400_BAD_REQUEST, request=request))
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response({"detail": "Email verified. You can now sign in."}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email", "")).strip().casefold()
        user = get_user_model().objects.filter(email__iexact=email, is_active=True).order_by("pk").first() if email else None
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = _frontend_url("/auth/password-reset/confirm", {"uid": uid, "token": token})
            try:
                _send_account_email(
                    subject="Reset your Retailo password",
                    message=f"Reset your Retailo password by opening this link. The link becomes invalid after your password changes.\n\n{reset_url}\n\nIf you did not request this, ignore this email.",
                    recipient=user.email,
                )
            except (RuntimeError, ValueError, OSError, SMTPException):
                logger.exception("Password reset email delivery failed")
        return Response({"detail": "If an active account matches this address, password reset instructions will be sent."}, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        password = request.data.get("password", "")
        if not isinstance(password, str) or len(password) < 12:
            return Response(api_error_response(code="validation_error", message="Password must be at least 12 characters.", status_code=status.HTTP_400_BAD_REQUEST, request=request))
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = get_user_model().objects.get(pk=user_id, is_active=True)
        except (ValueError, TypeError, get_user_model().DoesNotExist):
            user = None
        if user is None or not default_token_generator.check_token(user, token):
            return Response(api_error_response(code="invalid_password_reset_token", message="Password reset link is invalid or expired.", status_code=status.HTTP_400_BAD_REQUEST, request=request))
        user.set_password(password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password reset successfully. You can now sign in."}, status=status.HTTP_200_OK)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email", "")).strip().casefold()
        password = request.data.get("password", "")
        if not email or not isinstance(password, str) or not password:
            return Response(api_error_response(code="invalid_credentials", message="Email or password is incorrect.", status_code=status.HTTP_401_UNAUTHORIZED, request=request))
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).order_by("pk").first()
        authenticated = authenticate(request, username=user.get_username(), password=password) if user else None
        if authenticated is None or not authenticated.is_active:
            return Response(api_error_response(code="invalid_credentials", message="Email or password is incorrect.", status_code=status.HTTP_401_UNAUTHORIZED, request=request))
        membership = Membership.objects.filter(user=authenticated, is_active=True, tenant__status="active").select_related("tenant").order_by("created_at", "id").first()
        if membership is None:
            return Response(api_error_response(code="no_active_store", message="This account is not assigned to an active store.", status_code=status.HTTP_403_FORBIDDEN, request=request))
        refresh = RefreshToken.for_user(authenticated)
        refresh["tenant_id"] = str(membership.tenant_id)
        refresh["membership_id"] = str(membership.id)
        response = Response({"access": str(refresh.access_token)}, status=status.HTTP_200_OK)
        _set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _origin_is_allowed(request):
            return Response(api_error_response(code="origin_not_allowed", message="Origin is not allowed.", status_code=status.HTTP_403_FORBIDDEN, request=request))
        raw_token = request.COOKIES.get(REFRESH_COOKIE)
        if not raw_token:
            return Response(api_error_response(code="refresh_unavailable", message="Refresh session is unavailable.", status_code=status.HTTP_401_UNAUTHORIZED, request=request))
        try:
            refresh = RefreshToken(raw_token)
            user_id = refresh.get("user_id")
            tenant_id = refresh.get("tenant_id")
            membership_id = refresh.get("membership_id")
            User = get_user_model()
            user = User.objects.filter(pk=user_id, is_active=True).first()
            membership = Membership.objects.filter(pk=membership_id, user=user, tenant_id=tenant_id, is_active=True, tenant__status="active").first() if user else None
            if user is None or membership is None:
                raise TokenError("Invalid session membership")
            if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS", False):
                refresh.blacklist()
                replacement = RefreshToken.for_user(user)
                replacement["tenant_id"] = str(membership.tenant_id)
                replacement["membership_id"] = str(membership.id)
                response = Response({"access": str(replacement.access_token)}, status=status.HTTP_200_OK)
                _set_refresh_cookie(response, replacement)
                return response
            return Response({"access": str(refresh.access_token)}, status=status.HTTP_200_OK)
        except (TokenError, KeyError, TypeError, ValueError):
            response = Response(api_error_response(code="invalid_refresh_session", message="Refresh session is invalid or expired.", status_code=status.HTTP_401_UNAUTHORIZED, request=request))
            _clear_refresh_cookie(response)
            return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _origin_is_allowed(request):
            return Response(api_error_response(code="origin_not_allowed", message="Origin is not allowed.", status_code=status.HTTP_403_FORBIDDEN, request=request))
        raw_token = request.COOKIES.get(REFRESH_COOKIE)
        if raw_token:
            try:
                RefreshToken(raw_token).blacklist()
            except (TokenError, AttributeError, KeyError, TypeError, ValueError):
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership_id = request.auth.get("membership_id") if request.auth else None
        tenant_id = request.auth.get("tenant_id") if request.auth else None
        membership = Membership.objects.filter(pk=membership_id, tenant_id=tenant_id, user=request.user, is_active=True, tenant__status="active").select_related("tenant").first()
        if membership is None:
            return Response(api_error_response(code="no_active_store", message="No active store membership.", status_code=status.HTTP_403_FORBIDDEN, request=request))
        return Response({
            "id": str(request.user.pk),
            "email": request.user.email,
            "display_name": request.user.get_full_name() or request.user.get_username(),
            "tenant": {"id": str(membership.tenant_id), "name": membership.tenant.name},
            "role": membership.role,
        })
