#!/usr/bin/env python3
"""PER-UNIT PAD SPAN — how far apart are the building pads one FOOTPRINT
UNIT's bodies actually stand on?  (spec ``object-placement-spec.md``
§16g (1)/(7); owner RULINGS 2026-09-14c item 1, attributed 14g.)

THE QUESTION NOTHING ELSE ASKS.  ``harness/census.py`` prices grade law
and reports ZERO for an object seated 23 m above its own pad;
``obj8_split_report`` prints a body's anchor and its own ground but never
asks whether the bodies sharing ONE unit's datum stand on pads that
disagree; ``role_overlap_read`` is an area sweep.  This is the unit-vs-pad
reading §16g (7) was written on: at HECA 1.0.331 seventeen units held
bodies whose pads span more than 1 m — `fu:38:20` alone 978 bodies over
136 pads spanning 34.8 m — because the unit chained on PART BOXES, and
its DECK member then gave 96.20 to 1,509 bodies.

    venv/bin/python tools/pad_span_census.py PLACEMENT.json GRADED.json
        REBAKE.json [--over M] [--top N] [--json OUT]

``PLACEMENT.json`` is either ``o4_v2_placement_<ICAO>.json`` (the written
plan) or an ``obj8_split_report --json`` dump: both carry ``splits`` with
the body records, and the reader takes whichever shape it is given.

**IT MEASURES NO LAW AND COUNTS NO DEFECTS.**  The pads are the emitted
design surface's own ``building`` faces, each at ``median(z)`` over its
ring — the same plane ``footprint_unit`` reads through
``anchor_rule.pad_plurality`` — and a body is ON a pad when one of its
components' FEET falls inside the ring.  The join is the part id, never
a proximity match.  ``--over`` (default 1.0 m) is the listing floor 14g
stated its bar in, not a threshold with any standing.

Promoted 2026-09-14 from scout `v2heca331`'s scratchpad ``padspan.py`` on
its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g
attribution and then lane `v2connector` round 3's before/after.
Twin: ``tests/test_pad_span_census.py``.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys


def _pads(graded: dict):
    """The emitted ``building`` faces as ``(ring metres, ref, median z)``."""
    v = {x[0]: (x[1], x[2], x[3]) for x in graded["vertices"]}
    lat0 = 0.0
    n = 0
    for f in graded["faces"]:
        for i in f["ring"]:
            lat0 += v[i][0]
            n += 1
    lat0 = lat0 / n if n else 0.0
    r = math.radians(lat0)
    my = 111_132.954 - 559.822 * math.cos(2 * r) + 1.175 * math.cos(4 * r)
    mx = 111_412.84 * math.cos(r) - 93.5 * math.cos(3 * r)
    out = []
    for f in graded["faces"]:
        if f.get("role") != "building":
            continue
        ring = [(v[i][1] * mx, v[i][0] * my) for i in f["ring"]]
        if len(ring) < 3:
            continue
        zs = sorted(v[i][2] for i in f["ring"])
        out.append((ring, str(f.get("ref") or f.get("id")),
                    zs[len(zs) // 2]))
    return out, mx, my


def _inside(ring, x, y) -> bool:
    hit = False
    j = len(ring) - 1
    for i, a in enumerate(ring):
        b = ring[j]
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                hit = not hit
        j = i
    return hit


def census(placement: dict, graded: dict, rebake: dict, over_m: float = 1.0):
    pads, mx, my = _pads(graded)
    pad_box = []
    for ring, ref, z in pads:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        pad_box.append((min(xs), min(ys), max(xs), max(ys)))
    parts_of = {}
    for u in rebake["units"]:
        for m in u["members"]:
            parts_of[m["id"]] = {p[1]: p for p in m["parts"]}
    unit_pads = collections.defaultdict(set)
    unit_bodies = collections.Counter()
    for sp in placement.get("splits", ()):
        ref = sp.get("placement", sp)
        mid = "dsf:obj%d" % int(ref["index"])
        bc = parts_of.get(mid, {})
        for b in sp["bodies"]:
            uid = b.get("unit_of") or ""
            if not uid:
                continue
            unit_bodies[uid] += 1
            for c in b.get("components", ()):
                p = bc.get(c)
                if not p:
                    continue
                for f in (p[10] if len(p) > 10 else ()):
                    x, y = f[1] * mx, f[0] * my
                    for j, (x0, y0, x1, y1) in enumerate(pad_box):
                        if x0 <= x <= x1 and y0 <= y <= y1 \
                                and _inside(pads[j][0], x, y):
                            unit_pads[uid].add(j)
    rows = []
    for uid, js in unit_pads.items():
        zs = sorted(pads[j][2] for j in js)
        if len(zs) < 2:
            continue
        rows.append({"unit": uid, "pads": len(js), "bodies": unit_bodies[uid],
                     "span_m": round(zs[-1] - zs[0], 3),
                     "z_min": round(zs[0], 2), "z_max": round(zs[-1], 2)})
    rows.sort(key=lambda r: -r["span_m"])
    over = [r for r in rows if r["span_m"] > over_m]
    return {"units_with_a_unit_of": len(unit_bodies),
            "units_on_two_or_more_pads": len(rows),
            "over_m": over_m, "units_over": len(over),
            "bodies_in_units_over": sum(r["bodies"] for r in over),
            "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("placement")
    ap.add_argument("graded")
    ap.add_argument("rebake")
    ap.add_argument("--over", type=float, default=1.0)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    res = census(json.load(open(a.placement)), json.load(open(a.graded)),
                 json.load(open(a.rebake)), a.over)
    print(f"units carrying a unit_of: {res['units_with_a_unit_of']}; "
          f"standing on >= 2 building pads: {res['units_on_two_or_more_pads']}")
    print(f"units whose members' PADS SPAN > {a.over:.2f} m: "
          f"{res['units_over']}  ({res['bodies_in_units_over']} bodies)")
    print(f"{'unit':<26}{'pads':>6}{'bodies':>8}{'span':>10}   pad z")
    for r in res["rows"][:a.top]:
        if r["span_m"] <= a.over:
            break
        print(f"{r['unit']:<26}{r['pads']:>6}{r['bodies']:>8}"
              f"{r['span_m']:>9.2f} m   {r['z_min']:.2f} .. {r['z_max']:.2f}")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
        print("->", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
