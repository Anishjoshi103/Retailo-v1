from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    RegisterView,
    VerifyEmailView,
)

urlpatterns = [
    path("register", RegisterView.as_view(), name="auth-register"),
    path("verify-email", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("password-reset/request", PasswordResetRequestView.as_view(), name="auth-password-reset-request"),
    path("password-reset/confirm", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("refresh", RefreshView.as_view(), name="auth-refresh"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("me", MeView.as_view(), name="auth-me"),
]
