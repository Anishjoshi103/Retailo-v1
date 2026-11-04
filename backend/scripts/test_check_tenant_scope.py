"""Unit tests for the AST tenant scope checker."""
import unittest

from scripts.check_tenant_scope import check_source, discover_tenant_owned_models


class TenantScopeCheckerTests(unittest.TestCase):
    def test_finds_unscoped_manager_calls(self):
        errors = check_source(
            "Product.objects.filter(active=True).count()\n",
            "apps/catalog/views.py",
            {"Product"},
        )
        self.assertEqual(len(errors), 2)
        self.assertIn("apps/catalog/views.py:1: Product.objects.filter()", errors[0])
        self.assertIn("apps/catalog/views.py:1: Product.objects.count()", errors[1])

    def test_accepts_for_tenant_chain(self):
        errors = check_source(
            "Product.objects.for_tenant(tenant_id).filter(active=True).count()\n",
            "apps/catalog/views.py",
            {"Product"},
        )
        self.assertEqual(errors, [])

    def test_accepts_reasoned_escape_hatch(self):
        errors = check_source(
            'Product.objects.unscoped(reason="trusted reporting").aggregate()\n',
            "apps/catalog/reporting.py",
            {"Product"},
        )
        self.assertEqual(errors, [])

    def test_ignores_global_identity_and_non_guarded_methods(self):
        errors = check_source(
            "Tenant.objects.get(pk=tenant_id)\nProduct.objects.create(tenant_id=tenant_id)\n",
            "apps/catalog/services.py",
            {"Product"},
        )
        self.assertEqual(errors, [])

    def test_discovers_tenant_owned_model_subclasses(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "models.py").write_text(
                "class Product(TenantOwnedModel):\n    pass\n"
                "class Tenant(models.Model):\n    pass\n",
                encoding="utf-8",
            )
            self.assertEqual(discover_tenant_owned_models([root]), {"Product"})


if __name__ == "__main__":
    unittest.main()
