# SQL Server notes

Production runs on SQL Server (`mssql-django`, ODBC Driver 18). The fast CI job tests on in-memory
SQLite, which accepts SQL that SQL Server rejects, so there are two safety nets:

- **`Backend tests on SQL Server`** (CI): starts SQL Server 2022 and runs the whole backend suite
  with `config.settings.ci_mssql`. Locally, set `DATABASE_PASSWORD` (and `DATABASE_HOST` if not
  `127.0.0.1`) and run `DJANGO_SETTINGS_MODULE=config.settings.ci_mssql python manage.py test`.
- **`apps/tenancy/test_sqlserver_compatibility.py`** (fast job, no database): compiles every model
  constraint and the known grouped queries with the SQL Server backend and rejects T-SQL it refuses.

When CI fails, `scripts/summarize_test_failures.py` turns the log into annotations on the run (one per
distinct error, with the failing tests), which are readable without downloading logs.

## Things that behave differently on SQL Server

| Do not | Why | Do instead |
|---|---|---|
| `condition=~Q(field="")` on a `UniqueConstraint` | Filtered indexes cannot use `NOT`, `OR`, `IN`, `LIKE` | `condition=Q(field__gt="")` |
| `.values("x").annotate(Sum(...))` on a model with `Meta.ordering` | The default `ORDER BY` is appended to the grouped query and SQL Server rejects an ungrouped column | add `.order_by()` first |
| Retyping a primary key that other columns depend on in a migration | `ALTER COLUMN` fails while a unique constraint depends on the referencing column | create the final schema directly, as for `token_blacklist` |
| Comparing decimal sums exactly in a `CheckConstraint` | SQLite stores decimals as floats | compare against `Round(sum, 2)` |

`token_blacklist` (simplejwt) uses its own single migration in `apps/accounts/token_blacklist_migrations`
because the library's migration 0008 retypes IDs, which SQL Server rejects. It keeps the name
`0001_initial` so databases that already ran the library's migrations see nothing to apply. If simplejwt
changes its models, regenerate it (the comment above `MIGRATION_MODULES` in `settings/base.py` says how).

## Still not covered

The row locks (`select_for_update`) now execute on SQL Server in the tests, but the tests are
single-threaded, so concurrent behaviour (two cashiers selling at once, two returns of one sale) is not
yet exercised.
