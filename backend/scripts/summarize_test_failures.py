"""Turn a Django/unittest log into GitHub Actions annotations.

Usage: ``python scripts/summarize_test_failures.py test-output.log``

CI only shows the raw log. This prints one ``::error`` annotation that lists each failing test
with the last line of its traceback (usually the database or assertion message), plus the tail
of the log, so a failure is readable from the run summary and from the checks API.
"""

import re
import sys
from pathlib import Path

SEPARATOR = "=" * 70
MAX_ENTRIES = 8
MAX_GROUPS = 7
MAX_LINE = 400
TAIL_LINES = 40


def _escape(text: str) -> str:
    """Escape a message for a workflow command (newlines must be encoded)."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def parse_failures(log: str) -> list[tuple[str, str]]:
    """Return ``(header, last traceback line)`` for every ERROR/FAIL block in a unittest log."""
    failures = []
    for block in log.split(SEPARATOR)[1:]:
        # The last block is followed by unittest's "Ran N tests" footer, which is not part of it.
        block = re.split(r"\n-{70}\nRan \d+ test", block)[0]
        lines = [line for line in block.strip().splitlines() if line.strip()]
        if not lines or not re.match(r"^(ERROR|FAIL):", lines[0]):
            continue
        # The final non-dashed line of the block is the exception or assertion message.
        body = [line for line in lines[1:] if not set(line.strip()) <= {"-"}]
        failures.append((lines[0].strip(), body[-1].strip() if body else ""))
    return failures


def _signature(detail: str) -> str:
    """Normalise an error line so the same problem on different tests groups together."""
    return re.sub(r"\d+|'[^']*'|\"[^\"]*\"", "#", detail)[:MAX_LINE]


def summarize(log: str) -> list[str]:
    annotations = []
    failures = parse_failures(log)
    groups: dict[str, list[tuple[str, str]]] = {}
    for header, detail in failures:
        groups.setdefault(_signature(detail), []).append((header, detail))
    ordered = sorted(groups.values(), key=len, reverse=True)
    if failures:
        overview = f"{len(failures)} failing test(s) in {len(ordered)} distinct error group(s); largest group first."
        annotations.append(f"::error title=Test failures::{_escape(overview)}")
    for index, group in enumerate(ordered[:MAX_GROUPS], start=1):
        lines = [f"{len(group)} test(s) with this error:", group[0][1][:MAX_LINE * 3], "Tests:"]
        lines += [f"- {header[:MAX_LINE]}" for header, _ in group[:MAX_ENTRIES]]
        if len(group) > MAX_ENTRIES:
            lines.append(f"... and {len(group) - MAX_ENTRIES} more")
        annotations.append(f"::error title=Error group {index}::{_escape(chr(10).join(lines))}")
    tail = "\n".join(log.strip().splitlines()[-TAIL_LINES:])
    if tail:
        annotations.append(f"::error title=End of test log::{_escape(tail[:8000])}")
    return annotations


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: summarize_test_failures.py LOGFILE", file=sys.stderr)
        return 2
    path = Path(argv[1])
    log = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    for annotation in summarize(log):
        print(annotation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
