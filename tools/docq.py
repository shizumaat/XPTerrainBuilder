#!/usr/bin/env python3
"""docq — THE DOC QUERY: print exactly one spec section, one RULINGS
entry, or the short tool index, so a lane never greps a monolith.

Owner 2026-09-13: lanes spent 115k–170k fresh input tokens (12–16 turns)
before their first edit, slicing `design-surface-spec.md` (~123k tokens),
`object-placement-spec.md` (~64k), `RULINGS.md` (~217k) and
`tools/INDEX.md` (~69k).  The monoliths stay the source of truth (running
lanes append to them on their branches); this tool is the READ surface.

    tools/docq.py spec  '§37'            # whole §37 incl. its (n) sub-blocks
    tools/docq.py spec  '§37 (6)'        # one sub-block
    tools/docq.py spec  --list [--object]
    tools/docq.py spec  --object '§16e'  # object-placement-spec
    tools/docq.py ruling 13am            # RULINGS 2026-09-13am (+ its bullets)
    tools/docq.py ruling 2026-09-13am 13ab 13aj
    tools/docq.py index                  # one line per tool
    tools/docq.py index seat_feet        # the FULL row(s) matching a substring

Exit 1 with a named miss when nothing matches — a silent empty print is
how a lane reads the wrong law.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_DESIGN = os.path.join(ROOT, "Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md")
SPEC_OBJECT = os.path.join(ROOT, "Ortho4XP/docs/specs/auto-patch-v2/object-placement-spec.md")
RULINGS = os.path.join(ROOT, "Ortho4XP/docs/RULINGS.md")
INDEX = os.path.join(ROOT, "tools/INDEX.md")

_HEAD = re.compile(r"^(#{2,3}) (§\d+[a-z]?(?:\.\d+)?(?: \(\d+\))?)(?=\s|$)(.*)$")


def _read(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n")


# --- spec -------------------------------------------------------------------

def spec_headings(path: str) -> list[tuple[int, int, str, str]]:
    """(line, level, key, title) for every `## §N` / `### §N (k)` heading."""
    out = []
    for i, ln in enumerate(_read(path)):
        m = _HEAD.match(ln)
        if m:
            out.append((i, len(m.group(1)), m.group(2), m.group(3).strip()))
    return out


def _norm(key: str) -> str:
    key = key.strip()
    if not key.startswith("§"):
        key = "§" + key
    return re.sub(r"\s+", " ", key)


def spec_section(path: str, key: str) -> str:
    """Every block whose heading key STARTS with `key` (so '§37' returns §37,
    §37.1, §37 (5), §37 (6) … and each of their MEASURED blocks), in file
    order, each block running to the next heading of equal or higher level
    that is NOT itself a continuation of the same key."""
    key = _norm(key)
    lines = _read(path)
    heads = spec_headings(path)
    want = [h for h in heads if h[2] == key or h[2].startswith(key + " ") or h[2].startswith(key + ".")]
    if not want:
        raise SystemExit(f"docq: no spec heading matches {key!r} in {os.path.basename(path)} "
                         f"(try --list)")
    out = []
    want_lines = {w[0] for w in want}
    covered_to = -1
    for (line, _level, _k, _t) in want:
        if line < covered_to:          # already inside a printed block
            continue
        # a block ends at the NEXT heading of any level that is not itself
        # part of the request — so `§37` yields §37, §37.1, §37 (5), §37 (6)
        # and their MEASURED blocks, but never the §32 (4) block filed
        # between them
        end = len(lines)
        for (l2, _lv2, _k2, _) in heads:
            if l2 > line and l2 not in want_lines:
                end = l2
                break
        covered_to = end
        out.append("\n".join(lines[line:end]).rstrip("\n"))
    # de-duplicate overlapping ranges (a `## §37` block already contains its `###`s)
    text = "\n\n".join(out)
    return text


# --- rulings ----------------------------------------------------------------

def ruling_entry(ids: list[str]) -> str:
    lines = _read(RULINGS)
    heads = [(i, ln) for i, ln in enumerate(lines) if ln.startswith("## ")]
    out = []
    for raw in ids:
        rid = raw.strip()
        if re.fullmatch(r"\d{1,2}[a-z]{1,2}", rid):          # 13am -> 2026-09-13am
            rid = f"2026-09-{int(rid[:-len(rid.lstrip('0123456789'))]):02d}{rid.lstrip('0123456789')}"
        hits = [k for k, (i, ln) in enumerate(heads) if ln.startswith(f"## {rid} ")]
        if not hits:
            raise SystemExit(f"docq: no RULINGS entry {rid!r}")
        k = hits[-1]
        start = heads[k][0]
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        out.append("\n".join(lines[start:end]).rstrip("\n"))
    return "\n\n".join(out)


# --- index ------------------------------------------------------------------

def index_rows() -> list[tuple[str, str]]:
    r"""(path, description) per row.  Cells split on UNESCAPED ` | `
    (space-pipe-space): a `\|` or a bare `|` inside a command such as
    `[--stage planar|structures]` is not a cell boundary; a row with no
    trailing pipe still parses."""
    rows = []
    for ln in _read(INDEX):
        if not ln.startswith("| `"):
            continue
        body = ln.strip()
        body = body[1:] if body.startswith("|") else body
        body = body[:-1] if body.endswith("|") else body
        cells = [c.strip() for c in re.split(r"(?<!\\) \| ", body.strip())]
        if len(cells) < 2:
            continue
        m = re.match(r"`([^`]+)`", cells[0])
        if not m:
            continue
        rows.append((m.group(1), " | ".join(cells[1:]).strip()))
    return rows


def index_short() -> str:
    out = []
    for path, desc in index_rows():
        first = re.split(r"(?<=[.;—])\s", desc, maxsplit=1)[0]
        first = re.sub(r"\*\*", "", first)
        if len(first) > 150:
            first = first[:147].rstrip() + "…"
        out.append(f"{path}  —  {first}")
    return "\n".join(out)


def index_full(sub: str) -> str:
    hits = [f"| `{p}` | {d} |" for p, d in index_rows() if sub in p or sub in d]
    if not hits:
        raise SystemExit(f"docq: no tools/INDEX.md row matches {sub!r}")
    return "\n\n".join(hits)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("spec"); s.add_argument("key", nargs="?"); s.add_argument("--list", action="store_true"); s.add_argument("--object", action="store_true")
    r = sub.add_parser("ruling"); r.add_argument("ids", nargs="+")
    x = sub.add_parser("index"); x.add_argument("sub", nargs="?")
    a = ap.parse_args(argv)
    if a.cmd == "spec":
        path = SPEC_OBJECT if a.object else SPEC_DESIGN
        if a.list or not a.key:
            for _l, lv, k, t in spec_headings(path):
                print(("  " if lv == 3 else "") + k + "  " + t[:100])
            return 0
        print(spec_section(path, a.key)); return 0
    if a.cmd == "ruling":
        print(ruling_entry(a.ids)); return 0
    if a.cmd == "index":
        print(index_full(a.sub) if a.sub else index_short()); return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
