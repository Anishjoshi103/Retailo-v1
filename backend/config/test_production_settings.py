import importlib
import os
from unittest import TestCase
from unittest.mock import patch


class ProductionSettingsTests(TestCase):
    def load_production_settings(self, **overrides):
        environment = {
            "DJANGO_SECRET_KEY": "production-test-secret",
            "DJANGO_ALLOWED_HOSTS": "retailo.example.com",
            "REDIS_URL": "rediss://retailo:secret@redis.example.com:6380/2",
            **overrides,
        }
        with patch.dict(os.environ, environment, clear=True):
            import config.settings.production as production

            return importlib.reload(production)

    def test_production_requires_a_shared_redis_cache(self):
        with patch.dict(
            os.environ,
            {
                "DJANGO_SECRET_KEY": "production-test-secret",
                "DJANGO_ALLOWED_HOSTS": "retailo.example.com",
            },
            clear=True,
        ):
            with self.assertRaisesMessage(RuntimeError, "REDIS_URL"):
                import config.settings.production as production

                importlib.reload(production)

    def test_production_uses_redis_for_throttle_counters(self):
        production = self.load_production_settings()

        self.assertEqual(
            production.CACHES["throttle"]["BACKEND"],
            "django.core.cache.backends.redis.RedisCache",
        )
        self.assertEqual(
            production.CACHES["throttle"]["LOCATION"],
            "rediss://retailo:secret@redis.example.com:6380/2",
        )

    def test_production_enables_https_redirect_and_hsts(self):
        production = self.load_production_settings()

        self.assertTrue(production.SECURE_SSL_REDIRECT)
        self.assertEqual(production.SECURE_HSTS_SECONDS, 31536000)
        self.assertFalse(production.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertFalse(production.SECURE_HSTS_PRELOAD)
        self.assertTrue(production.CSRF_COOKIE_SECURE)
        self.assertTrue(production.SESSION_COOKIE_SECURE)

    def test_proxy_ssl_header_is_opt_in(self):
        production = self.load_production_settings()
        self.assertFalse(hasattr(production, "SECURE_PROXY_SSL_HEADER"))

        production = self.load_production_settings(TRUST_PROXY_SSL_HEADER="true")
        self.assertEqual(
            production.SECURE_PROXY_SSL_HEADER,
            ("HTTP_X_FORWARDED_PROTO", "https"),
        )

    def test_hsts_subdomains_and_preload_can_be_enabled_explicitly(self):
        production = self.load_production_settings(
            SECURE_HSTS_INCLUDE_SUBDOMAINS="true",
            SECURE_HSTS_PRELOAD="true",
        )

        self.assertTrue(production.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertTrue(production.SECURE_HSTS_PRELOAD)
