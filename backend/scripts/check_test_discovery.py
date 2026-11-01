"""Fail CI if Django silently skips test modules or test methods."""

from pathlib import Path
import re
import sys

import django
from django.apps import apps
from django.test.runner import DiscoverRunner


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_METHOD = re.compile(r"^\s*def test_[A-Za-z0-9_]+\s*\(", re.MULTILINE)


def main() -> int:
    django.setup()
    missing_packages = [
        str(Path(app.path).relative_to(BACKEND_ROOT))
        for app in apps.get_app_configs()
        if Path(app.path).is_relative_to(BACKEND_ROOT / "apps")
        and not (Path(app.path) / "__init__.py").is_file()
    ]
    if missing_packages:
        print("App directories missing __init__.py:", ", ".join(missing_packages), file=sys.stderr)
        return 1

    source_roots = [BACKEND_ROOT / "apps", BACKEND_ROOT / "config"]
    expected = sum(
        len(TEST_METHOD.findall(path.read_text(encoding="utf-8")))
        for root in source_roots
        for path in root.rglob("*.py")
        if (path.name == "tests.py" or path.name.startswith("test_"))
        and "migrations" not in path.parts
    )
    runner = DiscoverRunner(verbosity=0)
    discovered = runner.build_suite().countTestCases()
    print(f"Test discovery guard: {discovered} discovered; {expected} test_ methods found.")
    if discovered < expected:
        print("Django discovered fewer tests than exist in test modules.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
