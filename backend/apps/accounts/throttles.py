"""Rate limits for sign-in, registration, password reset, token checks and staff invitations.

Each class counts requests per key (client address, email, or signed-in user) in the shared
``throttle`` cache and answers 429 with a ``Retry-After`` header once the rate in
``settings.THROTTLE_RATES`` is exceeded. Keying sign-in on address *and* email means someone
hammering one account cannot lock it out for everyone else, only from their own address.
"""

import hashlib
import json

from django.core.cache import caches
from django.http.request import RawPostDataException
from rest_framework.throttling import SimpleRateThrottle


def _request_email(request) -> str | None:
    """The email in a JSON request body, normalised, or None if there is none to key on.

    The raw body is read directly rather than through ``request.data``: a malformed body then simply
    has no email to key on, and the view still parses (and rejects) it exactly as it always did, so
    throttling never changes how a bad request is answered.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, RawPostDataException):
        return None
    value = payload.get("email") if isinstance(payload, dict) else None
    if not isinstance(value, str):
        return None
    value = value.strip().casefold()
    return value[:254] or None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


class _KeyedThrottle(SimpleRateThrottle):
    """Base: subclasses set ``scope`` and say what to key on; ``None`` means do not throttle."""

    @property
    def cache(self):
        return caches["throttle"]

    def identifier(self, request) -> str | None:
        raise NotImplementedError

    def get_cache_key(self, request, view):
        ident = self.identifier(request)
        return self.cache_format % {"scope": self.scope, "ident": ident} if ident else None


class _IpThrottle(_KeyedThrottle):
    def identifier(self, request):
        return self.get_ident(request)


class _EmailThrottle(_KeyedThrottle):
    def identifier(self, request):
        email = _request_email(request)
        return _digest(email) if email else None


class _IpEmailThrottle(_KeyedThrottle):
    def identifier(self, request):
        email = _request_email(request)
        return f"{self.get_ident(request)}|{_digest(email)}" if email else None


class _UserThrottle(_KeyedThrottle):
    def identifier(self, request):
        user = getattr(request, "user", None)
        return str(user.pk) if user is not None and user.is_authenticated else None


class LoginIpEmailThrottle(_IpEmailThrottle):
    scope = "login_ip_email"


class LoginIpThrottle(_IpThrottle):
    scope = "login_ip"


class RegisterIpThrottle(_IpThrottle):
    scope = "register_ip"


class PasswordResetEmailThrottle(_EmailThrottle):
    scope = "reset_email"


class PasswordResetIpThrottle(_IpThrottle):
    scope = "reset_ip"


class TokenIpThrottle(_IpThrottle):
    scope = "token_ip"


class StaffInviteThrottle(_UserThrottle):
    scope = "staff_invite"
