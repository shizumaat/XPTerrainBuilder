#!/usr/bin/env python3
"""brief_pack — assemble a SELF-CONTAINED lane brief so the lane reads ONE
file instead of slicing four monoliths (owner 2026-09-13: 115k–170k fresh
tokens and 12–16 turns per lane before its first edit).

    tools/brief_pack.py --lane v2roadramp --base 523faf5d \\
        --spec '§37 (6)' --spec '§37.1' --rulings 13aj 13ab \\
        --index road_terrain_conformance v2_solve_replay \\
        --frames KCLT LEMD \\
        --bars bars.md --notes notes.md > docs/briefs/v2roadramp.md

Every section is pulled VERBATIM through `tools/docq.py` (spec sections,
RULINGS entries, INDEX rows) and `tools/harness/frames.py` (registered
captures), so the session never retypes law and the lane never greps.
The pack names its base sha; the lane still merges main first (a pack
can be behind main by the time the lane starts).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCQ = os.path.join(ROOT, "tools", "docq.py")
FRAMES = os.path.join(ROOT, "tools", "harness", "frames.py")

STANDING = """\
## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.
"""


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"brief_pack: {' '.join(cmd)} failed:\n{r.stderr.strip()}")
    return r.stdout.rstrip("\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lane", required=True)
    ap.add_argument("--base", required=True, help="main sha the lane branches from")
    ap.add_argument("--title", default="")
    ap.add_argument("--spec", action="append", default=[], help="design-spec section key, repeatable")
    ap.add_argument("--ospec", action="append", default=[], help="object-spec section key, repeatable")
    ap.add_argument("--rulings", nargs="*", default=[])
    ap.add_argument("--index", nargs="*", default=[], help="INDEX row substrings")
    ap.add_argument("--frames", nargs="*", default=[], help="ICAOs whose registered captures to list")
    ap.add_argument("--bars", help="markdown file: the bars (verbatim)")
    ap.add_argument("--notes", help="markdown file: session notes / the brief body (verbatim)")
    ap.add_argument("--files", nargs="*", default=[], help="files the lane owns / may touch")
    ap.add_argument("--avoid", nargs="*", default=[], help="files other lanes own")
    a = ap.parse_args(argv)

    out = [f"# Brief pack — lane `{a.lane}`", "",
           f"Base: main `{a.base}` · generated {_dt.date.today().isoformat()} by `tools/brief_pack.py`",
           "", "Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for",
           "what is here; use `tools/docq.py` for anything else you need.", ""]
    if a.title:
        out += [f"## Task", "", a.title, ""]
    if a.notes:
        out += ["## The brief", "", open(a.notes, encoding="utf-8").read().rstrip("\n"), ""]
    if a.bars:
        out += ["## Bars", "", open(a.bars, encoding="utf-8").read().rstrip("\n"), ""]
    if a.files or a.avoid:
        out += ["## Files", ""]
        if a.files:
            out += ["Yours: " + ", ".join(f"`{f}`" for f in a.files)]
        if a.avoid:
            out += ["Other lanes' (do not touch): " + ", ".join(f"`{f}`" for f in a.avoid)]
        out += [""]
    for key in a.spec:
        out += [f"## Spec (design-surface) {key}", "", _run([sys.executable, DOCQ, "spec", key]), ""]
    for key in a.ospec:
        out += [f"## Spec (object-placement) {key}", "", _run([sys.executable, DOCQ, "spec", "--object", key]), ""]
    if a.rulings:
        out += ["## RULINGS", "", _run([sys.executable, DOCQ, "ruling", *a.rulings]), ""]
    for sub in a.index:
        out += [f"## Tool: {sub}", "", _run([sys.executable, DOCQ, "index", sub]), ""]
    for icao in a.frames:
        out += [f"## Registered frames: {icao}", "", _run([sys.executable, FRAMES, "list", icao]) or "(none registered)", ""]
    out += [STANDING]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
