from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenancy.models import Membership

REFRESH_COOKIE = "retailo_refresh"


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
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/api/v1/auth/",
        samesite=getattr(settings, "AUTH_REFRESH_COOKIE_SAMESITE", "Lax"),
    )


def _origin_is_allowed(request):
    origin = request.headers.get("Origin")
    if not origin:
        return True
    expected = f"{request.scheme}://{request.get_host()}"
    return origin.rstrip("/") == expected.rstrip("/")


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email", "")).strip().casefold()
        password = request.data.get("password", "")
        if not email or not isinstance(password, str) or not password:
            return Response({"detail": "Email or password is incorrect."}, status=status.HTTP_401_UNAUTHORIZED)

        User = get_user_model()
        user = User.objects.filter(email__iexact=email).order_by("pk").first()
        authenticated = authenticate(request, username=user.get_username(), password=password) if user else None
        if authenticated is None or not authenticated.is_active:
            return Response({"detail": "Email or password is incorrect."}, status=status.HTTP_401_UNAUTHORIZED)

        membership = Membership.objects.filter(user=authenticated, is_active=True, tenant__status="active").select_related("tenant").order_by("created_at", "id").first()
        if membership is None:
            return Response({"detail": "This account is not assigned to an active store."}, status=status.HTTP_403_FORBIDDEN)

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
            return Response({"detail": "Origin is not allowed."}, status=status.HTTP_403_FORBIDDEN)
        raw_token = request.COOKIES.get(REFRESH_COOKIE)
        if not raw_token:
            return Response({"detail": "Refresh session is unavailable."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            refresh = RefreshToken(raw_token)
            user_id = refresh.get("user_id")
            tenant_id = refresh.get("tenant_id")
            membership_id = refresh.get("membership_id")
            User = get_user_model()
            user = User.objects.filter(pk=user_id, is_active=True).first()
            membership = Membership.objects.filter(
                pk=membership_id, user=user, tenant_id=tenant_id, is_active=True, tenant__status="active"
            ).first() if user else None
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
            response = Response({"access": str(refresh.access_token)}, status=status.HTTP_200_OK)
            return response
        except (TokenError, KeyError, TypeError, ValueError):
            response = Response({"detail": "Refresh session is invalid or expired."}, status=status.HTTP_401_UNAUTHORIZED)
            _clear_refresh_cookie(response)
            return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _origin_is_allowed(request):
            return Response({"detail": "Origin is not allowed."}, status=status.HTTP_403_FORBIDDEN)
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
        membership = Membership.objects.filter(
            pk=membership_id,
            tenant_id=tenant_id,
            user=request.user,
            is_active=True,
            tenant__status="active",
        ).select_related("tenant").first()
        if membership is None:
            return Response({"detail": "No active store membership."}, status=status.HTTP_403_FORBIDDEN)
        return Response({
            "id": str(request.user.pk),
            "email": request.user.email,
            "display_name": request.user.get_full_name() or request.user.get_username(),
            "tenant": {"id": str(membership.tenant_id), "name": membership.tenant.name},
            "role": membership.role,
        })
