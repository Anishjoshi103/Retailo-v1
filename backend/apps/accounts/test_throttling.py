import tempfile
import uuid
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant
from config.settings.base import THROTTLE_RATES

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"
RESET = "/api/v1/auth/password-reset/request"
RESET_CONFIRM = "/api/v1/auth/password-reset/confirm"
VERIFY = "/api/v1/auth/verify-email"


def rates(**overrides):
    """Every scope effectively unlimited, except the ones a test turns down."""
    return {**{scope: "100000/min" for scope in THROTTLE_RATES}, **overrides}


class ThrottleTestCase(TestCase):
    def setUp(self):
        caches["throttle"].clear()
        self.addCleanup(caches["throttle"].clear)
        self.clock = [1_000_000.0]
        timer = mock.patch.object(SimpleRateThrottle, "timer", staticmethod(lambda: self.clock[0]))
        timer.start()
        self.addCleanup(timer.stop)

    def limit(self, **overrides):
        patch = mock.patch.object(SimpleRateThrottle, "THROTTLE_RATES", rates(**overrides))
        patch.start()
        self.addCleanup(patch.stop)

    def login(self, email="asha@example.test", ip="10.0.0.1", **headers):
        return APIClient().post(LOGIN, {"email": email, "password": "wrong-password-1"}, format="json", REMOTE_ADDR=ip, **headers)


class LoginThrottleTests(ThrottleTestCase):
    def test_repeated_attempts_on_one_account_from_one_address_are_limited(self):
        self.limit(login_ip_email="3/min")
        statuses = [self.login().status_code for _ in range(5)]
        self.assertEqual(statuses, [401, 401, 401, 429, 429])

    def test_the_limit_response_has_the_standard_shape_and_a_retry_after(self):
        self.limit(login_ip_email="1/min")
        self.login()
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "throttled")
        self.assertGreater(int(response["Retry-After"]), 0)

    def test_one_attacker_cannot_lock_an_account_out_for_other_addresses_or_other_accounts(self):
        self.limit(login_ip_email="2/min")
        for _ in range(3):
            self.login(ip="10.0.0.1")
        self.assertEqual(self.login(ip="10.0.0.1").status_code, 429)
        self.assertEqual(self.login(ip="10.0.0.2").status_code, 401)  # same account, a different address
        self.assertEqual(self.login(email="other@example.test", ip="10.0.0.1").status_code, 401)  # other account

    def test_the_email_is_normalised_so_case_and_spaces_do_not_evade_the_limit(self):
        self.limit(login_ip_email="2/min")
        self.login(email="Asha@Example.test")
        self.login(email="  asha@example.TEST ")
        self.assertEqual(self.login(email="ASHA@example.test").status_code, 429)

    def test_one_address_trying_many_accounts_is_limited_overall(self):
        self.limit(login_ip="4/min")
        statuses = [self.login(email=f"user{i}@example.test").status_code for i in range(6)]
        self.assertEqual(statuses, [401, 401, 401, 401, 429, 429])

    def test_the_window_expires(self):
        self.limit(login_ip_email="2/min")
        self.login()
        self.login()
        self.assertEqual(self.login().status_code, 429)
        self.clock[0] += 61
        self.assertEqual(self.login().status_code, 401)

    def test_requests_without_a_usable_email_are_still_limited_by_address(self):
        self.limit(login_ip="2/min")
        client = APIClient()
        for payload in ({}, {"email": 123}, {"password": "x"}):
            client.post(LOGIN, payload, format="json", REMOTE_ADDR="10.0.0.9")
        self.assertEqual(client.post(LOGIN, {}, format="json", REMOTE_ADDR="10.0.0.9").status_code, 429)

    def test_malformed_json_is_still_a_400_and_still_counts_against_the_address(self):
        self.limit(login_ip="2/min")
        client = APIClient()
        statuses = [client.post(LOGIN, "{not json", content_type="application/json", REMOTE_ADDR="10.0.0.3").status_code for _ in range(3)]
        self.assertEqual(statuses, [400, 400, 429])


class ClientAddressTests(ThrottleTestCase):
    def forwarded(self, header, remote="172.18.0.2"):
        return self.login(ip=remote, HTTP_X_FORWARDED_FOR=header)

    def rest_framework(self, proxies):
        return override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": proxies})

    def test_behind_one_proxy_the_client_is_the_right_most_forwarded_address(self):
        self.limit(login_ip_email="2/min")
        with self.rest_framework(1):
            # A client cannot dodge the limit by inventing a different first entry: nginx appends the real address.
            self.forwarded("1.1.1.1, 9.9.9.9")
            self.forwarded("2.2.2.2, 9.9.9.9")
            self.assertEqual(self.forwarded("3.3.3.3, 9.9.9.9").status_code, 429)
            self.assertEqual(self.forwarded("1.1.1.1, 8.8.8.8").status_code, 401)  # a genuinely different client

    def test_without_trusted_proxies_the_forwarded_header_is_ignored(self):
        self.limit(login_ip_email="2/min")
        with self.rest_framework(0):
            self.forwarded("1.1.1.1", remote="10.0.0.1")
            self.forwarded("2.2.2.2", remote="10.0.0.1")
            self.assertEqual(self.forwarded("3.3.3.3", remote="10.0.0.1").status_code, 429)
            self.assertEqual(self.forwarded("1.1.1.1", remote="10.0.0.2").status_code, 401)

    def test_the_proxy_count_comes_from_the_environment_with_a_safe_default(self):
        self.assertEqual(settings.REST_FRAMEWORK["NUM_PROXIES"], 0)


class RegistrationAndResetThrottleTests(ThrottleTestCase):
    def test_registration_is_limited_per_address(self):
        self.limit(register_ip="2/hour")
        client = APIClient()
        statuses = [client.post(REGISTER, {}, format="json", REMOTE_ADDR="10.0.0.4").status_code for _ in range(3)]
        self.assertEqual(statuses, [400, 400, 429])
        self.assertEqual(client.post(REGISTER, {}, format="json", REMOTE_ADDR="10.0.0.5").status_code, 400)

    def test_password_reset_emails_to_one_mailbox_are_limited_whatever_the_address(self):
        self.limit(reset_email="2/hour")
        client = APIClient()
        sent = [client.post(RESET, {"email": "asha@example.test"}, format="json", REMOTE_ADDR=f"10.0.1.{i}").status_code for i in range(3)]
        self.assertEqual(sent[2], 429)
        self.assertNotIn(429, sent[:2])
        self.assertNotEqual(client.post(RESET, {"email": "ravi@example.test"}, format="json", REMOTE_ADDR="10.0.1.9").status_code, 429)

    def test_password_reset_is_limited_per_address(self):
        self.limit(reset_ip="2/hour")
        client = APIClient()
        statuses = [client.post(RESET, {"email": f"u{i}@example.test"}, format="json", REMOTE_ADDR="10.0.2.1").status_code for i in range(3)]
        self.assertEqual(statuses[2], 429)

    def test_token_guessing_is_limited_on_reset_confirmation_and_email_verification(self):
        self.limit(token_ip="2/hour")
        client = APIClient()
        for path in (RESET_CONFIRM, VERIFY):
            caches["throttle"].clear()
            statuses = [client.post(path, {"token": "x", "uid": "y", "password": "z"}, format="json", REMOTE_ADDR="10.0.3.1").status_code for _ in range(3)]
            self.assertEqual(statuses[2], 429, path)
            self.assertNotIn(429, statuses[:2], path)


class StaffInviteThrottleTests(ThrottleTestCase):
    def setUp(self):
        super().setUp()
        self.tenant = Tenant.objects.create(name="Store A", slug="store-a")
        self.branch = Branch.objects.create(tenant=self.tenant, name="Main", code="MAIN", state_code="27")
        user = get_user_model().objects.create_user(username="owner@example.test", email="owner@example.test", password="Correct-horse-battery-1")
        member = Membership.objects.create(tenant=self.tenant, user=user, role="owner")
        BranchAccess.objects.create(membership=member, branch=self.branch)
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(member.id)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def invite(self, email):
        return self.client.post("/api/v1/staff", {"email": email, "role": "cashier", "branch_ids": [str(self.branch.id)]}, format="json")

    def test_invitations_are_limited_per_signed_in_user_but_listing_is_not(self):
        self.limit(staff_invite="2/hour")
        self.assertEqual(self.invite("a@example.test").status_code, 201)
        self.assertEqual(self.invite("b@example.test").status_code, 201)
        blocked = self.invite("c@example.test")
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(get_user_model().objects.filter(email="c@example.test").count(), 0)
        for _ in range(5):
            self.assertEqual(self.client.get("/api/v1/staff").status_code, 200)

    def test_resending_an_invitation_shares_the_same_limit(self):
        self.limit(staff_invite="2/hour")
        created = self.invite("a@example.test").json()
        self.assertEqual(self.client.post(f"/api/v1/staff/{created['id']}/resend-invite").status_code, 202)
        self.assertEqual(self.client.post(f"/api/v1/staff/{created['id']}/resend-invite").status_code, 429)

    def test_the_limit_is_per_user_not_shared(self):
        self.limit(staff_invite="1/hour")
        self.assertEqual(self.invite("a@example.test").status_code, 201)
        self.assertEqual(self.invite("b@example.test").status_code, 429)
        admin = get_user_model().objects.create_user(username="admin@example.test", email="admin@example.test", password="Correct-horse-battery-1")
        member = Membership.objects.create(tenant=self.tenant, user=admin, role="admin")
        BranchAccess.objects.create(membership=member, branch=self.branch)
        refresh = RefreshToken.for_user(admin)
        refresh["tenant_id"] = str(self.tenant.id)
        refresh["membership_id"] = str(member.id)
        other = APIClient()
        other.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        response = other.post("/api/v1/staff", {"email": f"{uuid.uuid4().hex[:6]}@example.test", "role": "cashier", "branch_ids": [str(self.branch.id)]}, format="json")
        self.assertEqual(response.status_code, 201)


@override_settings(CACHES={**settings.CACHES})
class ConfigurationTests(TestCase):
    def test_every_throttled_scope_has_a_rate(self):
        from apps.accounts import throttles

        scopes = {cls.scope for cls in vars(throttles).values() if isinstance(cls, type) and getattr(cls, "scope", None)}
        self.assertEqual(scopes, set(THROTTLE_RATES))

    def test_production_counters_live_in_a_cache_shared_by_the_workers(self):
        from config.settings import base

        backend = base.CACHES["throttle"]["BACKEND"]
        self.assertTrue(backend.endswith("filebased.FileBasedCache"), backend)
        self.assertGreaterEqual(base.CACHES["throttle"]["OPTIONS"]["MAX_ENTRIES"], 100000)

    def test_the_suite_itself_uses_effectively_unlimited_rates(self):
        self.assertTrue(all(rate.startswith("100000/") for rate in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].values()))


class FileCacheThrottleTests(ThrottleTestCase):
    """The production counter store (a directory of files) must really count across workers."""

    def file_caches(self, directory):
        return {**settings.CACHES, "throttle": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": directory, "OPTIONS": {"MAX_ENTRIES": 100000},
        }}

    def test_the_throttle_limits_requests_when_counters_are_stored_in_files(self):
        self.limit(login_ip_email="2/min")
        with tempfile.TemporaryDirectory() as directory, override_settings(CACHES=self.file_caches(directory)):
            statuses = [self.login().status_code for _ in range(4)]
        self.assertEqual(statuses, [401, 401, 429, 429])

    def test_two_workers_share_one_set_of_counters(self):
        from django.core.cache.backends.filebased import FileBasedCache

        with tempfile.TemporaryDirectory() as directory:
            worker_a = FileBasedCache(directory, {"OPTIONS": {"MAX_ENTRIES": 100000}})
            worker_b = FileBasedCache(directory, {"OPTIONS": {"MAX_ENTRIES": 100000}})
            worker_a.set("throttle_login_ip_email_x", [1.0, 2.0], 60)
            self.assertEqual(worker_b.get("throttle_login_ip_email_x"), [1.0, 2.0])
