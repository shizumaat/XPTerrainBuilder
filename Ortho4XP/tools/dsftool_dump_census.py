"""Which DSFs can the bundled DSFTool turn into text?  (issue #568)

``venv/bin/python tools/dsftool_dump_census.py ROOT [ROOT ...] --out OUT.jsonl
[--tool PATH] [--jobs N] [--limit N] [--keep-text DIR]``

Runs ``DSFTool --dsf2text`` over every ``*.dsf`` under each ROOT (a
scenery pack, or a folder of packs) and writes one JSON row per file:
``path``, ``rc`` (negative = killed by that signal, e.g. -11 SIGSEGV),
``bytes`` of text written, ``seconds``, and the last line DSFTool said.
READ-ONLY on the inputs; the text goes to a private temp folder and is
deleted (``--keep-text DIR`` keeps the dumps that succeeded).  It never
writes the shared data repo and it is not a timing instrument.  Resumable:
paths already in OUT are skipped.  Exit status is 0 whatever DSFTool did;
the summary line counts the failures.

On macOS every crash also leaves a report under
``~/Library/Logs/DiagnosticReports``.

JUDGING A REPLACEMENT BINARY (issue #587): run it twice with ``--keep-text``
(once per tool, two folders), then

``venv/bin/python tools/dsftool_dump_census.py --diff-text OLD_DIR NEW_DIR``

prints, per ROW CLASS (the row's keyword; a ``#`` comment by its first two
words), how many rows and files differ between the two tools' dumps of the
same DSF, with one example each, and the files only one tool dumped.  The
``# file:`` comment (the input path) is not compared.  Rows are compared
in order: a file whose line count changed is reported under ``LINE COUNT``.
"""
from __future__ import annotations

import argparse
import concurrent.futures as _cf
import json
import os
import subprocess
import sys
import tempfile
import time

__all__ = ["dsf_files", "dump_one", "diff_text", "main"]

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLATFORM_DIR = {"darwin": "mac", "win32": "win"}.get(sys.platform, "lin")
_TOOL_NAME = "DSFTool.exe" if sys.platform == "win32" else "DSFTool"
DEFAULT_TOOL = os.path.join(_HERE, "..", "Utils", _PLATFORM_DIR, _TOOL_NAME)


def dsf_files(roots: list[str]) -> list[str]:
    """Every ``*.dsf`` under ``roots``, sorted."""
    out: list[str] = []
    for root in roots:
        for folder, _dirs, names in os.walk(root):
            out.extend(os.path.join(folder, n) for n in names
                       if n.lower().endswith(".dsf"))
    return sorted(out)


def dump_one(tool: str, dsf_path: str, work_dir: str, *,
             keep_dir: str | None = None, timeout: float = 120.0) -> dict:
    """One ``--dsf2text`` launch; the row described in the module text."""
    fd, text = tempfile.mkstemp(suffix=".text", dir=work_dir)
    os.close(fd)
    began = time.time()
    try:
        proc = subprocess.run([tool, "--dsf2text", dsf_path, text],
                              capture_output=True, timeout=timeout)
        rc, said = proc.returncode, (proc.stderr or proc.stdout)
    except subprocess.TimeoutExpired:
        rc, said = None, b"timed out"
    size = os.path.getsize(text) if os.path.isfile(text) else 0
    if keep_dir and rc == 0 and size:
        os.makedirs(keep_dir, exist_ok=True)
        os.replace(text, os.path.join(
            keep_dir, os.path.basename(dsf_path) + ".text"))
    elif os.path.isfile(text):
        os.remove(text)
    last = said.decode("utf-8", "replace").strip().splitlines()[-1:]
    return {"path": dsf_path, "rc": rc, "bytes": size,
            "seconds": round(time.time() - began, 2),
            "said": last[0][:200] if last else ""}


def _rows(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        return [r for r in fh.read().split("\n") if not r.startswith("# file:")]


def _row_class(row: str) -> str:
    toks = row.split()
    return " ".join(toks[:2]) if toks[:1] == ["#"] else (toks[0] if toks else "")


def diff_text(old_dir: str, new_dir: str) -> dict:
    """Two ``--keep-text`` folders compared file by file: ``identical`` and
    ``differ`` counts, ``only_old`` / ``only_new`` names, and per row class
    ``{"rows", "files", "example": [name, old row, new row]}``."""
    old, new = set(os.listdir(old_dir)), set(os.listdir(new_dir))
    out: dict = {"identical": 0, "differ": 0, "only_old": sorted(old - new),
                 "only_new": sorted(new - old), "classes": {}}
    for name in sorted(old & new):
        a, b = _rows(os.path.join(old_dir, name)), _rows(os.path.join(new_dir, name))
        if a == b:
            out["identical"] += 1
            continue
        out["differ"] += 1
        pairs = ([("LINE COUNT", f"{len(a)} rows", f"{len(b)} rows")]
                 if len(a) != len(b) else
                 [(_row_class(x), x, y) for x, y in zip(a, b) if x != y])
        for cls, x, y in pairs:
            row = out["classes"].setdefault(
                cls, {"rows": 0, "files": set(), "example": [name, x, y]})
            row["rows"] += 1
            row["files"].add(name)
    for row in out["classes"].values():
        row["files"] = sorted(row["files"])
    return out


def _print_diff(report: dict) -> None:
    print(f"{report['identical']} dumps identical, {report['differ']} differ; "
          f"only in OLD {len(report['only_old'])}, "
          f"only in NEW {len(report['only_new'])}")
    for label in ("only_old", "only_new"):
        if report[label]:
            print(f"  {label}: {' '.join(report[label][:12])}"
                  f"{' …' if len(report[label]) > 12 else ''}")
    for cls, row in sorted(report["classes"].items(),
                           key=lambda kv: -len(kv[1]["files"])):
        name, x, y = row["example"]
        print(f"  {cls!r}: {row['rows']} rows in {len(row['files'])} files"
              f" — e.g. {name}: {x.strip()!r} -> {y.strip()!r}")


def _done_paths(out_path: str) -> set[str]:
    if not os.path.isfile(out_path):
        return set()
    with open(out_path, "r", encoding="utf-8") as fh:
        return {json.loads(line)["path"] for line in fh if line.strip()}


def main(argv: list[str] | None = None) -> int:
    # The console is UTF-8 before the parser can print (#171, #125); a
    # library with a CLI pins in its entry.  Twin: test_console_encoding.
    sys.path.insert(0, os.path.join(_HERE, "..", "src"))
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("roots", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--diff-text", nargs=2, metavar=("OLD_DIR", "NEW_DIR"))
    ap.add_argument("--json", help="with --diff-text: also write the report here")
    ap.add_argument("--tool", default=DEFAULT_TOOL)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--keep-text", default=None)
    args = ap.parse_args(argv)
    if args.diff_text:
        report = diff_text(*args.diff_text)
        _print_diff(report)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=1)
        return 0
    if not args.roots or not args.out:
        ap.error("ROOT ... and --out are required (or --diff-text OLD NEW)")
    done = _done_paths(args.out)
    todo = [p for p in dsf_files(args.roots) if p not in done]
    if args.limit:
        todo = todo[:args.limit]
    failed = 0
    with tempfile.TemporaryDirectory(prefix="dsftool_census_") as work, \
            open(args.out, "a", encoding="utf-8") as fh, \
            _cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        rows = pool.map(lambda p: dump_one(args.tool, p, work,
                                           keep_dir=args.keep_text), todo)
        for row in rows:
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            failed += row["rc"] != 0 or not row["bytes"]
    print(f"{len(todo)} dumped now ({len(done)} already in {args.out}); "
          f"{failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
