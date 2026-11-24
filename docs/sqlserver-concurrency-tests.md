# SQL Server concurrency tests

The sales concurrency integration tests live in `backend/apps/sales/test_concurrency.py`.
They use `TransactionTestCase`, independent worker threads/connections, and a start barrier
so requests overlap against the configured database.

Run them against SQL Server with the same settings used by CI:

```sh
cd backend
DJANGO_SETTINGS_MODULE=config.settings.ci_mssql python manage.py test apps.sales.test_concurrency --verbosity 2
```

The tests intentionally skip on SQLite: SQLite does not provide the row-level
`SELECT ... FOR UPDATE` behavior these scenarios are designed to verify.

Scenarios covered:

- Two sales each request more stock than can be fulfilled together; exactly one may post.
- Two returns race to return the same sold quantity; exactly one credit note may post.
- Two concurrent successful sales on one branch receive distinct sequential invoice numbers.

The assertions cover response statuses, persisted document counts, final stock balances, and
the exact invoice number sequence. The SQL Server CI job runs the full Django test suite, so
these tests are included automatically.
