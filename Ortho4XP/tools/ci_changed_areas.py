"""Which CI jobs a pull request's changed files need (owner 2026-11-03).

Until 2026-11-03 ``.github/workflows/ci.yml`` ran its jobs on a pull request
only when the branch was a ``claude/batch-*`` integration branch (owner
2026-10-26, #1397).  Harness-only PR #1801 landed without its Linux run and
broke main (``stat -f`` is filesystem status on Linux).  The owner's rule
now: EVERY pull request runs the jobs its files can break.

* ``python`` (the three-platform engine suite) runs unless every changed
  file is DOCS-ONLY: a file outside ``Ortho4XP/`` that is under ``docs/`` or
  ends in ``.md``, and whose name no engine test names.  The second half
  keeps the rule honest without a list: ``tests/test_glossary_parity.py``
  reads ``docs/glossary.md``, so a change to it runs the suite.  Anything
  under ``Ortho4XP/`` (src, tools, tests, its docs and RULINGS twins),
  ``scripts/``, ``tools/``, ``.github/``, ``Sources/`` and ``Tests/`` (the
  layout-parity and wire-protocol twins read the Swift) always runs it.
* ``swift`` (macOS ``swift build`` / ``swift test``) runs for ``Sources/``,
  ``Tests/``, ``Resources/``, ``Package.swift`` / ``Package.resolved``,
  ``scripts/``, ``.github/``, and for an engine file the Swift names
  (``Ortho4XP/tests/fixtures/...``, ``src/O4_Version.py``): the Swift tests
  read the shared fixtures and the engine version.

No base (a push to main, ``workflow_dispatch``) runs everything.

Usage (from the repo root; standard library only, so it runs on a bare
runner)::

    python3 Ortho4XP/tools/ci_changed_areas.py --base BASE_SHA --head HEAD_SHA

prints ``python=true|false`` and ``swift=true|false`` (the lines
``$GITHUB_OUTPUT`` takes) and a summary on stderr.  Twin:
``Ortho4XP/tests/test_ci_workflow_triggers.py``.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: Path prefixes the Swift job builds or tests.
SWIFT_PREFIXES = ("Sources/", "Tests/", "Resources/", "scripts/", ".github/",
                  "Package.swift", "Package.resolved")


def _texts(root: Path, pattern: str) -> str:
    if not root.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(root.rglob(pattern)))


def docs_only(path: str, test_text: str) -> bool:
    """True when ``path`` cannot break the engine suite."""
    if path.startswith("Ortho4XP/"):
        return False
    if not (path.startswith("docs/") or path.endswith(".md")):
        return False
    return path.rsplit("/", 1)[-1] not in test_text


def swift_reads(path: str, swift_text: str) -> bool:
    """True when ``path`` is one the Swift job builds or a Swift file names."""
    if path.startswith(SWIFT_PREFIXES):
        return True
    if not path.startswith("Ortho4XP/"):
        return False
    rel = path[len("Ortho4XP/"):]
    if rel in swift_text:
        return True
    parts = path.split("/")
    return any(f'"{"/".join(parts[:i])}"' in swift_text
               for i in range(2, len(parts)))


def areas(paths: list[str], test_text: str, swift_text: str) -> dict[str, bool]:
    """``{"python": bool, "swift": bool}`` for one change set."""
    return {
        "python": any(not docs_only(p, test_text) for p in paths),
        "swift": any(swift_reads(p, swift_text) for p in paths),
    }


def changed_paths(base: str, head: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"],
                         cwd=REPO, capture_output=True, text=True, check=True)
    return [p for p in out.stdout.splitlines() if p.strip()]


def main(argv=None) -> int:
    # The console is UTF-8 before anything prints (#171): one derivation site.
    sys.path.insert(0, str(REPO / "Ortho4XP" / "src"))
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--base", default="", help="base sha; empty = run everything")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)
    if not args.base:
        result = {"python": True, "swift": True}
        print("no base (push or dispatch): every job runs", file=sys.stderr)
    else:
        paths = changed_paths(args.base, args.head)
        result = areas(paths,
                       _texts(REPO / "Ortho4XP" / "tests", "*.py"),
                       _texts(REPO / "Tests", "*.swift") + _texts(REPO / "Sources", "*.swift"))
        print(f"{len(paths)} changed file(s): {result}", file=sys.stderr)
        for p in paths[:50]:
            print(f"  {p}", file=sys.stderr)
    for key, value in result.items():
        print(f"{key}={'true' if value else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
