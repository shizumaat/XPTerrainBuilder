"""THE DECK PROBE — one read of every pack deck off a ``--solved-out``
pickle (``tools/v2_solve_replay.py --replay ... --solved-out PKL``; deck
redesign, #1717).

    venv/bin/python tools/deck_probe.py PKL [--object OID] [--near M]
        [--vertex V ...] [--json OUT]

Prints, per deck object of ``PlanarMap.decks``: its witness, family, cut and
carried route; per end line its anchor (level, pinned / yielding, the
solved level at the pinned vertex, stage 1's anchor beside it) and the worst
station off the anchor level; then every HARD row over the materiality
floor (0.02 m) that touches a vertex within ``--near`` metres (default 5)
of a deck ring or on an end line — the "no NOT SETTLED row within 5 m of
any deck" bar — and the row fingerprint (count and sha of every row).
``--vertex``: one vertex's roles, z, DEM, its stage-1 twin and every hard
row on it with its violation.  Writes nothing but ``--json``.

Promoted from the deckanchor lanes' scratch probes (``deckA/probe.py``,
``unsettled.py``, ``attr.py``) on their second use (tool discipline,
RULINGS 7e90032)."""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

#: a hard row is NOT SETTLED over this many metres (the solve's own floor)
SETTLED_M = 0.02


def station_offsets(anchors, z) -> list[dict]:
    """Per anchor: its record and the worst station off its level."""
    out = []
    for a in anchors:
        dev = [(abs(float(z[s]) - float(a.z_m)), s) for s in a.stations]
        worst = max(dev, default=(0.0, None))
        out.append({"object": a.object_id, "end": a.end, "v": a.v, "z_m": round(float(a.z_m), 3),
                    "solved": round(float(z[a.v]), 3), "family": a.family, "ref": a.ref,
                    "pinned": bool(a.pinned), "yielding": bool(a.yielding),
                    "cut": a.cut, "note": a.note, "stations": len(a.stations),
                    "worst_station_m": round(worst[0], 3), "worst_station": worst[1]})
    return out


def near_vertices(vertices, rings, stations, near_m: float) -> set[int]:
    """The vertices within ``near_m`` of any ring (``vertices``: id -> xy)
    and every end-line station."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    polys = [Polygon(r).buffer(near_m) for r in rings if len(r) >= 3]
    out = set(stations)
    if polys:
        u = prep(unary_union(polys))
        out |= {v for v, xy in vertices.items() if u.contains(Point(xy))}
    return out


def unsettled_rows(rows, near: set[int], z, is_hard, violation, row_vertices,
                   floor_m: float = SETTLED_M) -> list[dict]:
    """Every hard row over ``floor_m`` touching ``near``, worst first."""
    out = []
    for r in rows:
        if not is_hard(r):
            continue
        vs = list(row_vertices(r))
        if not near.intersection(vs):
            continue
        m = float(violation(r, z))
        if m > floor_m:
            out.append({"m": round(m, 3), "kind": type(r).__name__, "generator": r.source.generator,
                        "ruling": r.source.ruling, "inputs": str(r.source.inputs), "v": vs[:6]})
    return sorted(out, key=lambda q: -q["m"])


def fingerprint(rows) -> tuple[int, str]:
    """``(count, sha16)`` of the row set (order-free)."""
    h = hashlib.sha256()
    reprs = sorted(repr(r) for r in rows)
    for s in reprs:
        h.update(s.encode())
    return len(reprs), h.hexdigest()[:16]


def _vertex(pm, pm1, cs, z, v: int, is_hard, violation, row_vertices) -> dict:
    vx = pm.vertices[v]
    at1 = {tuple(q.xy): k for k, q in pm1.vertices.items()} if pm1 is not None else {}
    t = at1.get(tuple(vx.xy))
    rows = [{"m": round(float(violation(r, z)), 3), "kind": type(r).__name__,
             "generator": r.source.generator, "ruling": r.source.ruling[:70],
             "inputs": str(r.source.inputs)}
            for r in cs.rows() if v in row_vertices(r) and is_hard(r)]
    return {"v": v, "xy": list(vx.xy), "z": round(float(z[v]), 3), "dem": vx.dem_z,
            "roles": sorted(pm.roles_at(v)), "s1_twin": t,
            "s1_roles": sorted(pm1.roles_at(t)) if t is not None else None, "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pkl", type=Path)
    ap.add_argument("--object", default=None)
    ap.add_argument("--near", type=float, default=5.0)
    ap.add_argument("--vertex", type=int, nargs="*", default=())
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    warnings.simplefilter("ignore")
    import numpy as np
    from auto_patch_v2.law import Law
    from auto_patch_v2.solve.design_roles import hard_rulings, is_hard
    from auto_patch_v2.solve.pin_yield import _violation_m, row_vertices
    with a.pkl.open("rb") as fh:
        d = pickle.load(fh)
    pm, cs, z, pm1 = d["pm"], d["cs"], np.asarray(d["z"], float), d.get("pm_s1")
    heads = hard_rulings(Law.for_airport(pm.icao))

    def hard(r) -> bool:
        return is_hard(heads, r)
    decks = [db for db in getattr(pm, "decks", ()) or ()
             if a.object is None or db.object_id == a.object]
    anchors = [x for x in getattr(pm, "deck_anchors", ()) or ()
               if a.object is None or x.object_id == a.object]
    s1 = {(x.object_id, x.end): x for x in (getattr(pm1, "deck_anchors", ()) or ())} \
        if pm1 is not None else {}
    res: dict = {"decks": [{"object": db.object_id, "family": db.family, "witness": db.witness,
                            "cut": db.cut, "route": db.route_ref} for db in decks]}
    print("decks", len(decks), [(q["object"], q["family"], q["witness"], q["cut"], q["route"])
                                for q in res["decks"]])
    res["anchors"] = station_offsets(anchors, z)
    for q in res["anchors"]:
        b = s1.get((q["object"], q["end"]))
        q["s1_z_m"] = None if b is None else round(float(b.z_m), 3)
        print(f"  {q['object']} {q['end']} v{q['v']} z {q['z_m']:.3f} solved {q['solved']:.3f} "
              f"fam {q['family']} ref {q['ref']} pin {q['pinned']} yld {q['yielding']} "
              f"cut {q['cut']} | stations {q['stations']} worst {q['worst_station_m']:.3f} "
              f"(v{q['worst_station']}) | s1 {q['s1_z_m']} | {q['note'][:80]}")
    near = near_vertices({v: vx.xy for v, vx in pm.vertices.items()}, [db.ring for db in decks],
                         {s for x in anchors for s in x.stations}, a.near)
    res["unsettled"] = unsettled_rows(cs.rows(), near, z, hard, _violation_m, row_vertices)
    print(f"hard rows over {SETTLED_M} m within {a.near:g} m of a deck: {len(res['unsettled'])}")
    for q in res["unsettled"][:40]:
        print(f"  {q['m']:.3f} {q['kind']} {q['generator']} {q['ruling'][:60]} {q['inputs'][:60]} "
              f"v{q['v']}")
    res["vertices"] = [_vertex(pm, pm1, cs, z, v, hard, _violation_m, row_vertices)
                       for v in a.vertex]
    for q in res["vertices"]:
        print(f"v{q['v']} xy {q['xy']} z {q['z']} dem {q['dem']} roles {q['roles']} "
              f"| s1 v{q['s1_twin']} {q['s1_roles']}")
        for r in q["rows"]:
            print(f"   {r['m']:+.3f} {r['kind']} {r['generator']} {r['ruling']} {r['inputs']}")
    n, sha = fingerprint(cs.rows())
    res["rows"] = {"count": n, "sha": sha}
    print("rows", n, "sha", sha)
    if a.json:
        a.json.write_text(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
