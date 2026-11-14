"""Compile every model constraint with the SQL Server backend and reject T-SQL that it refuses.

The default test database is SQLite, which accepts SQL that SQL Server (production) rejects. This
runs in the fast job and needs no database: it only asks the mssql backend to write the DDL. It
once missed `WHERE NOT (field = '')` in filtered unique indexes, which SQL Server does not allow.
"""

import re
import unittest

from django.apps import apps
from django.db.utils import ConnectionHandler
from django.test import SimpleTestCase

# Filtered index predicates may only use simple comparisons joined by AND (and IS [NOT] NULL).
FORBIDDEN_IN_FILTERED_INDEX = re.compile(r"\b(NOT|OR|IN|LIKE|BETWEEN)\b")


def mssql_connection():
    try:
        import mssql.base  # noqa: F401  (also imports pyodbc, which needs the system ODBC library)
    except ImportError as exc:
        raise unittest.SkipTest(f"SQL Server backend not importable: {exc}") from exc
    handler = ConnectionHandler({
        "default": {
            "ENGINE": "mssql", "NAME": "unused", "USER": "unused", "PASSWORD": "unused",
            "HOST": "127.0.0.1", "PORT": "1433",
            "OPTIONS": {"driver": "ODBC Driver 18 for SQL Server"},
        }
    })
    return handler["default"]


class SqlServerConstraintCompatibilityTests(SimpleTestCase):
    def constraint_sql(self):
        connection = mssql_connection()
        editor = connection.schema_editor()
        for model in apps.get_models():
            for constraint in model._meta.constraints:
                yield f"{model._meta.label}.{constraint.name}", str(constraint.create_sql(model, editor))

    def test_every_constraint_compiles_for_sql_server(self):
        compiled = dict(self.constraint_sql())
        self.assertGreater(len(compiled), 40)
        for name, sql in compiled.items():
            self.assertTrue(sql.strip(), name)

    def test_filtered_unique_indexes_only_use_comparisons_sql_server_allows(self):
        filtered = {name: sql for name, sql in self.constraint_sql() if " WHERE " in sql}
        self.assertTrue(filtered, "expected at least one filtered unique index")
        for name, sql in filtered.items():
            predicate = sql.split(" WHERE ", 1)[1]
            predicate = re.sub(r"\bIS NOT NULL\b", "IS_NOT_NULL", predicate.upper())
            self.assertIsNone(FORBIDDEN_IN_FILTERED_INDEX.search(predicate), f"{name}: {sql}")

    def test_not_empty_unique_indexes_exist_for_the_nullable_free_text_keys(self):
        compiled = dict(self.constraint_sql())
        for name in ("inventory.StockMovement.uq_stock_move_tenant_idem", "inventory.Supplier.uq_supplier_tenant_gstin", "inventory.PurchaseInvoice.uq_purchase_invoice_supplier_number"):
            self.assertIn("> ''", compiled[name], name)


class SqlServerQueryCompatibilityTests(SimpleTestCase):
    """Grouped queries must not carry the model's default ordering into GROUP BY."""

    def compiled(self, queryset):
        connection = mssql_connection()
        # The compiler asks the server for its version; give it one so no connection is needed.
        connection.__dict__["sql_server_version"] = 2022
        connection.__dict__["to_azure_sql_db"] = False
        return queryset.query.get_compiler(connection=connection).as_sql()[0]

    def test_returned_quantity_per_sale_line_query_has_no_order_by(self):
        import uuid

        from django.db.models import Sum

        from apps.sales.models import CreditNoteLine

        queryset = (
            CreditNoteLine.objects.for_tenant(uuid.uuid4()).filter(sale_line__sale_id=uuid.uuid4())
            .order_by().values("sale_line_id").annotate(total=Sum("quantity"))
        )
        sql = self.compiled(queryset)
        self.assertIn("GROUP BY", sql)
        self.assertNotIn("ORDER BY", sql)

    def test_the_default_ordering_would_have_broken_it(self):
        """Documents why order_by() is needed: without it SQL Server gets ORDER BY on an ungrouped column."""
        import uuid

        from django.db.models import Sum

        from apps.sales.models import CreditNoteLine

        queryset = CreditNoteLine.objects.for_tenant(uuid.uuid4()).values("sale_line_id").annotate(total=Sum("quantity"))
        self.assertIn("ORDER BY", self.compiled(queryset))
