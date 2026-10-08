"""gapapron probe 2: THE 08c (6) ARM on the replay — every apron-touching gap
piece whose 08c class is APRON (probe 1's `evidence.json`: no road evidence,
or road evidence with a §37 (2) lateral share >= road_airside_edge_frac)
becomes a STAGE-1 APRON CELL (role `apron`, ref `gapapron:<k>`, kind
`gap_apron`) and is solved WITH the apron; every other piece stays a §53
late piece.  The classify stage is the tree's own; only the cells' spelling
is rewritten after it, as the mint would spell them.

usage: arm_driver.py base|arm EVIDENCE.json <v2_solve_replay args...>
  base: the remaining gap pieces are DROPPED (stage_one_map.gap_free) — the
        arm's base, written with --solved-out
  arm:  the remaining gap pieces stay; run with --late-from BASE/solved.pkl
"""
import dataclasses as _dc
import json
import sys

sys.path[:0] = ["src", ".", "tools"]
mode, ev_path = sys.argv[1], sys.argv[2]  # NOTE: a pool child re-imports this module as __mp_main__ with its own argv — guard with __main__ on the next use (the BASE/ARM verify fell back to one core; results unaffected)
APRON = {r["ref"] for r in json.load(open(ev_path))
         if r["class_08c_with_s37_share"].startswith("APRON")}
print(f"[arm_driver] mode {mode}: {len(APRON)} pieces -> stage-1 apron: {sorted(APRON)}")

import auto_patch_v2.classify as _pkg
from auto_patch_v2.law.tables import role_side
from auto_patch_v2.model.planar import is_gap_ref

_orig = _pkg.classify


def _classify(airport, law, rules=None, cache=None):
    cl = _orig(airport, law, rules, cache=cache)
    cells, k, dropped = [], 0, 0
    for c in cl.cells:
        if c.ref in APRON:
            cells.append(_dc.replace(
                c, role="apron", side=role_side(law, "apron"), kind="gap_apron",
                ref=f"gapapron:{k}",
                evidence={**dict(c.evidence), "gap_apron": 1.0, "gap_ref": c.ref}))
            k += 1
        elif mode == "base" and is_gap_ref(c.ref):
            dropped += 1
        else:
            cells.append(c)
    cells = [_dc.replace(c, id=i) for i, c in enumerate(cells)]
    print(f"[arm_driver] classify: {k} gap pieces re-spelled as apron, "
          f"{dropped} late pieces dropped (base), {len(cells)} cells")
    return _dc.replace(cl, cells=tuple(cells))


_pkg.classify = _classify
import v2_solve_replay as _r
sys.argv = [sys.argv[0], *sys.argv[3:]]
raise SystemExit(_r.main())
