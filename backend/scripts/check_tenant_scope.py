"""AST guard against unscoped manager/queryset operations on tenant-owned models.

The check is intentionally static and import-free: it runs before Django setup and
does not evaluate application code.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterable

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCANNED_ROOTS = (BACKEND_ROOT / "apps", BACKEND_ROOT / "config")
GUARDED_METHODS = {
    "get", "filter", "exclude", "all", "count", "exists", "aggregate",
    "iterator", "update", "delete", "get_or_create", "update_or_create",
    "bulk_create",
}

# Each entry must include a human-readable rationale. Keep empty unless a reviewed
# exception is truly unavoidable; tenant-scoped code should prefer for_tenant().
ALLOWLIST: dict[tuple[str, int], str] = {}


def _is_tenant_owned_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Name):
        return base.id == "TenantOwnedModel"
    if isinstance(base, ast.Attribute):
        return base.attr == "TenantOwnedModel"
    return False


def discover_tenant_owned_models(roots: Iterable[Path]) -> set[str]:
    """Find model classes directly inheriting TenantOwnedModel in app model files."""
    found: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("models.py"):
            if "migrations" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and any(
                    _is_tenant_owned_base(base) for base in node.bases
                ):
                    found.add(node.name)
    return found


def _manager_root(node: ast.AST) -> tuple[str, ast.AST] | None:
    """Return (model name, root node) when an expression descends from Model.objects."""
    current = node
    while isinstance(current, (ast.Call, ast.Attribute)):
        if isinstance(current, ast.Attribute):
            if current.attr == "objects" and isinstance(current.value, ast.Name):
                return current.value.id, current
            current = current.value
        else:
            current = current.func
    return None


def _chain_has_scope(node: ast.AST) -> bool:
    """Whether the queryset chain contains for_tenant() or a reasoned escape hatch."""
    current = node
    while isinstance(current, (ast.Call, ast.Attribute)):
        if isinstance(current, ast.Attribute):
            if current.attr in {"for_tenant", "unscoped"}:
                return True
            current = current.value
        else:
            if isinstance(current.func, ast.Attribute) and current.func.attr in {
                "for_tenant", "unscoped"
            }:
                return True
            current = current.func
    return False


def check_source(source: str, filename: str, tenant_models: set[str]) -> list[str]:
    """Return stable file:line diagnostics for unscoped manager operations."""
    tree = ast.parse(source, filename=filename)
    errors: list[str] = []
    relative = str(Path(filename))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr
        if method not in GUARDED_METHODS:
            continue
        manager = _manager_root(node.func.value)
        if manager is None:
            continue
        model_name, _ = manager
        if model_name not in tenant_models or _chain_has_scope(node.func.value):
            continue
        rationale = ALLOWLIST.get((relative, node.lineno), "")
        if not rationale.strip():
            errors.append(
                f"{relative}:{node.lineno}: {model_name}.objects.{method}() "
                "requires .for_tenant(tenant_id) or .unscoped(reason=...)"
            )
    return errors


def source_files() -> Iterable[Path]:
    for root in SCANNED_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "migrations" in path.parts or any(
                part in {"tests", "test"} for part in path.parts
            ) or path.name.startswith("test_"):
                continue
            yield path


def main() -> int:
    tenant_models = discover_tenant_owned_models(SCANNED_ROOTS)
    if not tenant_models:
        print("Tenant scope checker found no TenantOwnedModel subclasses.", file=sys.stderr)
        return 2
    errors: list[str] = []
    for path in source_files():
        try:
            source = path.read_text(encoding="utf-8")
            errors.extend(check_source(source, str(path), tenant_models))
        except (OSError, SyntaxError) as exc:
            errors.append(f"{path}: unable to inspect Python source: {exc}")
    if errors:
        print("\n".join(sorted(errors)), file=sys.stderr)
        print(f"Tenant scope checker: {len(errors)} unscoped manager call(s).", file=sys.stderr)
        return 1
    print(f"Tenant scope checker: clean; checked {len(tenant_models)} tenant-owned model classes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
