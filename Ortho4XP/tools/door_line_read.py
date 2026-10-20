"""THE DOOR-LINE READ — every door-line pad of a solved replay, read against
its own law (issue #798; ``constraints/door_pad``).

    venv/bin/python tools/door_line_read.py SOLVED.pkl [--json OUT.json]

``SOLVED.pkl`` is a ``tools/v2_solve_replay.py --replay ... --solved-out``
pickle.  Per door-line pad (re-derived on the pickle's own map and law,
``door_pad.door_pads``): the DOOR LINE's grade (door vertex to taxi vertex
over the line's own distance) against the apron cap it keeps, the pad's
z-SPREAD (one level: 0), and the steepest RIM EDGE — every edge of the
apron faces' own triangulation from a pad vertex to one off the pad, with
its site.
Then the stage-2 AIRSIDE GIVE (the ``door airside give`` Bands the pickle's
``stage2_bands`` carry): how many, the worst |z - stage-1 level| and how
many exceed the give; and every ``hard_conflict`` record whose head is the
door line's or the give's (§5a relaxed it: the named failure).

It measures the door law only; it counts no census defect and moves no
value.  For the population read (did airside move) use
``tools/airside_value_delta.py``.
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

#: a give exceeded by less than this is the solver's tolerance, not a miss
_TOL_M = 1e-3


def _rim_edges(pm, own: set[int]):
    """Every MESH edge (the apron faces' own triangulation, the solve's
    ``rows._face_triangles``) from a pad vertex to an apron vertex off it."""
    from auto_patch_v2.solve.rows import _face_triangles
    seen = set()
    for f in pm.faces.values():
        if f.role != "apron":
            continue
        vs = set(pm.ring_vertices(f.ring)).union(*(pm.ring_vertices(h) for h in f.holes))
        if not vs & own:
            continue
        for tri in _face_triangles(pm, f.id):
            for i in range(3):
                a, b = tri[i], tri[(i + 1) % 3]
                if (a in own) == (b in own):
                    continue
                a, b = (a, b) if a in own else (b, a)
                if (a, b) not in seen:
                    seen.add((a, b))
                    yield a, b


def _law_of(sv: dict):
    """The pickle's own law (its ``law_icao``, else its airport's)."""
    from auto_patch_v2.law import Law
    return Law.for_airport(sv.get("law_icao") or sv["icao"])


def read(sv: dict) -> dict:
    """The door-line read of one solved pickle (module docstring)."""
    from auto_patch_v2.constraints import door_pad as DP
    pm, z, ap = sv["pm"], sv["z"], sv["airport"]
    law = _law_of(sv)
    to_ll = ap.frame.transformers()[1]
    xy = lambda v: pm.vertices[v].xy                      # noqa: E731
    ll = lambda v: [round(c, 7) for c in to_ll(*xy(v))]   # noqa: E731
    pads = []
    for d in DP.door_pads(pm, law, ap):
        own = set(d.group)
        zs = [float(z[v]) for v in d.group]
        line = (abs(float(z[d.door_v]) - float(z[d.taxi_v])) / d.door_m
                if d.door_m > 0 and d.door_v >= 0 and d.taxi_v >= 0 else float("nan"))
        worst = (0.0, None, None)
        for a, b in _rim_edges(pm, own):
            L = math.dist(xy(a), xy(b))
            if L <= 0.5:
                continue
            g = abs(float(z[a]) - float(z[b])) / L
            if g > worst[0]:
                worst = (g, ll(a), ll(b))
        pads.append({"ref": d.ref, "door": [round(c, 7) for c in to_ll(*d.door)],
                     "door_line_pct": round(100 * line, 3),
                     "cap_pct": round(100 * d.door_cap, 3), "door_m": round(d.door_m, 1),
                     "spread_m": round(max(zs) - min(zs), 4),
                     "rim_edge_pct": round(100 * worst[0], 3), "rim_edge_at": worst[1],
                     "rim_edge_to": worst[2]})
    give_m = float(getattr(law.tables.structures.placement, "door_airside_give_m", 0.0))
    bands = [b for b in sv.get("stage2_bands") or ()
             if b.source.ruling.split(" (")[0].strip() == DP.GIVE_HEAD]
    dz = [(abs(float(z[b.v]) - 0.5 * (b.lo + b.hi)), b.v) for b in bands]
    worst_give = max(dz, default=(0.0, None))
    conf = [c for c in sv.get("hard_conflict") or ()
            if c.get("row") in (DP.DOOR_HEAD, DP.GIVE_HEAD)]
    return {"pads": pads,
            "give": {"give_m": give_m, "vertices": len(bands),
                     "worst_m": round(worst_give[0], 4),
                     "worst_at": None if worst_give[1] is None else ll(worst_give[1]),
                     "over_give": sum(1 for d, _v in dz if d > give_m + _TOL_M)},
            "door_conflicts": conf,
            "failures": DP.door_line_failures(conf, give_m)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("solved", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    with a.solved.open("rb") as fh:
        got = read(pickle.load(fh))
    for p in got["pads"]:
        print(f"{p['ref']} door {p['door'][0]:.6f},{p['door'][1]:.6f}: door line "
              f"{p['door_line_pct']:.2f} % (cap {p['cap_pct']:.2f} %, {p['door_m']:.0f} m), "
              f"pad spread {p['spread_m']:.3f} m, steepest rim edge "
              f"{p['rim_edge_pct']:.2f} % at {p['rim_edge_at']}")
    g = got["give"]
    print(f"airside give {g['give_m']:g} m: {g['vertices']} vertices, worst |dz| "
          f"{g['worst_m']:.3f} m at {g['worst_at']}, {g['over_give']} over the give")
    print(f"hard_conflict door/give rows: {len(got['door_conflicts'])}")
    for line in got["failures"]:
        print("  " + line)
    if a.json:
        a.json.write_text(json.dumps(got, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
