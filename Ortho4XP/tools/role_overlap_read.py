"""ROLE OVERLAP READ — how much of one emitted class STANDS ON another.

THE QUESTION, AND WHY NO EXISTING TOOL ANSWERS IT.  A ruling of the form
"the gap-fill spine must stop at groundside pavement" (RULINGS
2026-08-30, "GROUNDSIDE_PAVEMENT IS A GAP-FILL BLOCKER") is accepted or
refused on ONE number: the square metres of one role/ref class standing
on the footprint of another.  ``harness/census.py`` prices PAIRS OF
VALUES, so a face lying flat on top of a lot breaks no grade law and
reports zero rows however wrong it is; ``osm_site.py`` answers one
coordinate and ``arm_site_read.py`` one named place; ``void_census.py``
asks enclave topology and ``lattice_overlap_read.py`` asks CONTAINMENT
of the two role-less membrane classes by LENGTH.  None sweeps a patch
for the AREA one role class covers of another.  This is that sweep.

**It measures no law and counts no defects.**  Geometry, the metre
frame and the role-carrying rings come from the harness library itself
(``check_grade._parse_osm`` / ``_ll_to_m_factory`` about the sidecar's
own anchor) — imported, never re-spelled, which is the census-wrapper
precedent; defect counts come from ``harness/census.py`` and nowhere
else.  A patch without its ``.axes.json`` sidecar is REFUSED: without
the anchor there is no metre frame, and an area in the wrong frame is a
number that looks right and is not.

MEASURED BASIS (HECA round 6b/6c).  On the round-6b closing arm
``r6b_arm``: ``graded_strip:gap_fill_spine`` over ``groundside_pavement``
= 18 strips / 26,778 m², of which two faces carried 24,286 m² (3190 over
lot 2813 by 13,656 m², 70 % of its own area; 3192 over 2814 by
10,630 m², 63 %).  The same read over ``service_road`` /
``service_junction`` — 34 strips / 25,073 m² — is what said the class
was not one ruling's alone.  Promoted from the round-6b lane scratchpad
per RULINGS ``7e90032`` (second use).

    venv/bin/python tools/role_overlap_read.py PATCH.osm [PATCH.osm ...]
        --over ROLE[:REF] --on ROLE[:REF][,ROLE[:REF]...]
        [--pad M] [--beyond] [--site LAT,LON] [--min-area M2] [--top N]
        [--json OUT.json]

THE SAME READ AT ARM'S LENGTH (``--pad`` / ``--beyond``, Batch 4a).  An
OWNERSHIP question is an overlap question against a GROWN region: RULINGS
31b leaves auto_patch the road family "within
``SERVICE_ROAD_PAVEMENT_NEAR_M`` of aircraft pavement", so the far
population is this same sweep against the ON union buffered by ``--pad``,
reported as its COMPLEMENT — the OVER ways that do not reach it, totalled
and split by ref (a ref-less ring is slice-born; a ref names its minter).
``--site LAT,LON`` answers a named place in the OVER class's own terms.
Measured basis (Batch 4a, merged-main HECA control ``lt2c_heca_arm``):
``service_junction`` beyond 25 m of the airside roles = 1,526 of 1,777
rings / 473,248 m², of which 1,325 ref-less / 435,882 m².

Run from ``Ortho4XP/``.  Several patches are reported separately — that
is the arm-vs-arm read.  An overlap under ``--min-area`` (default
1.0 m², the emit rounding, not a law threshold) is not a stack.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MIN_AREA_M2 = 1.0


def _selector(spec: str):
    """``"role"`` or ``"role:ref"`` -> a predicate over a parsed way."""
    role, _, ref = str(spec).partition(":")
    role = role.strip()
    ref = ref.strip()

    def _match(w) -> bool:
        if role and w.role != role:
            return False
        if ref and w.ref != ref:
            return False
        return True
    return _match


def read(path, *, over: str, on: str,
         min_area_m2: float = DEFAULT_MIN_AREA_M2,
         pad_m: float = 0.0, beyond: bool = False, sites=()):
    """``{...}`` for one emitted patch — the OVER class's stack on the
    ON class.

    Reports ``over_ways`` / ``on_ways`` (the populations), ``stacked``
    (how many OVER ways stand on the ON union by more than
    ``min_area_m2``), ``area_m2`` (their total) and ``rows``, one entry
    per stacked way: its own area, the area over, the fraction, and the
    ON shapes it stands on, largest first.
    """
    import check_grade as CG
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    path = Path(path)
    side_path = Path(str(path) + ".axes.json")
    if not side_path.exists():
        raise SystemExit(
            f"REFUSING: {path} has no .axes.json sidecar — without the "
            f"anchor there is no metre frame to measure areas in.")
    nodes, ways = CG._parse_osm(path)
    side = json.loads(side_path.read_text())
    anchor = tuple(side["anchor"])
    to_m = CG._ll_to_m_factory(nodes, anchor)

    over_match = _selector(over)
    on_matches = [_selector(s) for s in str(on).split(",") if s.strip()]

    def _poly(w):
        pts = [to_m(*nodes[n]) for n in w.nids if n in nodes]
        if len(pts) < 4:
            return None
        try:
            p = Polygon(pts)
            if not p.is_valid:
                p = p.buffer(0)
        except Exception:                                 # pragma: no cover
            return None
        return None if p.is_empty else p

    over_ways, on_ways = [], []
    for w in ways:
        p = None
        if over_match(w):
            p = _poly(w)
            if p is not None:
                over_ways.append((w, p))
        if any(m(w) for m in on_matches):
            p = _poly(w) if p is None else p
            if p is not None:
                on_ways.append((w, p))

    on_union = (unary_union([p for _w, p in on_ways]) if on_ways else None)
    # ── THE PADDED FRAME AND ITS COMPLEMENT (``--pad`` / ``--beyond``) ──
    # An OWNERSHIP question is the same read at arm's length: "how much of
    # this class lies FURTHER THAN M METRES from that one".  RULINGS
    # 31b states auto_patch's remaining road ownership exactly that way
    # (within SERVICE_ROAD_PAVEMENT_NEAR_M of aircraft pavement), so the
    # far population is this tool's own overlap read against the ON union
    # GROWN by ``--pad``, reported as the ways that do NOT reach it.
    on_padded = on_union
    if on_union is not None and float(pad_m) > 0.0:
        try:
            on_padded = on_union.buffer(float(pad_m))
        except Exception:                                 # pragma: no cover
            on_padded = on_union
    beyond_rows, beyond_by_ref, site_rows = [], {}, []
    if beyond:
        for w, p in over_ways:
            try:
                near = (on_padded is not None
                        and p.intersects(on_padded))
            except Exception:                             # pragma: no cover
                near = True
            if near:
                continue
            lls = [nodes[n] for n in w.nids if n in nodes]
            lat = sum(x[0] for x in lls) / len(lls) if lls else None
            lon = sum(x[1] for x in lls) / len(lls) if lls else None
            key = w.ref or "(none)"
            agg = beyond_by_ref.setdefault(key, {"ways": 0, "area_m2": 0.0})
            agg["ways"] += 1
            agg["area_m2"] += p.area
            beyond_rows.append({"way": w.wid,
                                "shapeID": w.tags.get("shapeID"),
                                "ref": w.ref,
                                "own_area_m2": round(p.area, 1),
                                "lat": round(lat, 7) if lat else None,
                                "lon": round(lon, 7) if lon else None})
        beyond_rows.sort(key=lambda r: -r["own_area_m2"])
        for agg in beyond_by_ref.values():
            agg["area_m2"] = round(agg["area_m2"], 1)
    # ── SITES: the named place, answered in the OVER class's own terms ──
    for (slat, slon) in sites:
        from shapely.geometry import Point
        pt = Point(*to_m(float(slat), float(slon)))
        hit = None
        for w, p in over_ways:
            try:
                if p.covers(pt):
                    hit = (w, p)
                    break
            except Exception:                             # pragma: no cover
                continue
        d_on = None
        if on_union is not None:
            try:
                d_on = round(float(pt.distance(on_union)), 2)
            except Exception:                             # pragma: no cover
                d_on = None
        row = {"lat": float(slat), "lon": float(slon),
               "dist_to_on_m": d_on,
               "in_over_class": hit is not None}
        if hit is not None:
            w, p = hit
            row.update({"way": w.wid, "ref": w.ref,
                        "shapeID": w.tags.get("shapeID"),
                        "own_area_m2": round(p.area, 1)})
            if on_union is not None:
                try:
                    row["ring_dist_to_on_m"] = round(
                        float(p.distance(on_union)), 2)
                except Exception:                         # pragma: no cover
                    pass
        site_rows.append(row)
    rows = []
    total = 0.0
    for w, p in over_ways:
        if on_union is None:
            break
        try:
            a = p.intersection(on_union).area
        except Exception:                                 # pragma: no cover
            continue
        if a <= float(min_area_m2):
            continue
        total += a
        hits = []
        for w2, p2 in on_ways:
            try:
                if not p.intersects(p2):
                    continue
                a2 = p.intersection(p2).area
            except Exception:                             # pragma: no cover
                continue
            if a2 > float(min_area_m2):
                hits.append({"way": w2.wid,
                             "shapeID": w2.tags.get("shapeID"),
                             "area_m2": round(a2, 1)})
        hits.sort(key=lambda h: -h["area_m2"])
        rows.append({"way": w.wid, "shapeID": w.tags.get("shapeID"),
                     "own_area_m2": round(p.area, 1),
                     "over_area_m2": round(a, 1),
                     "over_frac": round(a / p.area, 4) if p.area else None,
                     "on": hits})
    rows.sort(key=lambda r: -r["over_area_m2"])
    return {"patch": str(path), "anchor": list(anchor),
            "over": over, "on": on, "min_area_m2": float(min_area_m2),
            "pad_m": float(pad_m),
            "over_ways": len(over_ways), "on_ways": len(on_ways),
            "over_area_m2": round(sum(p.area for _w, p in over_ways), 1),
            "stacked": len(rows), "area_m2": round(total, 1),
            "beyond": bool(beyond),
            "beyond_ways": len(beyond_rows),
            "beyond_area_m2": round(
                sum(r["own_area_m2"] for r in beyond_rows), 1),
            "beyond_by_ref": beyond_by_ref,
            "beyond_rows": beyond_rows,
            "sites": site_rows,
            "rows": rows}


def _report(res: dict, top: int) -> None:
    print(f"=== {res['patch']}")
    if res.get("beyond"):
        print(f"  {res['over']} BEYOND {res['pad_m']:g} m of {res['on']}: "
              f"{res['beyond_ways']} of {res['over_ways']} way(s), "
              f"{res['beyond_area_m2']:,.0f} m2 of "
              f"{res['over_area_m2']:,.0f} m2")
        for ref, agg in sorted(res["beyond_by_ref"].items(),
                               key=lambda kv: -kv[1]["area_m2"]):
            print(f"    ref {ref:>16}  {agg['ways']:5d} way(s)  "
                  f"{agg['area_m2']:12,.0f} m2")
        for r in res["beyond_rows"][:top]:
            print(f"    way {r['way']:>8} ref {str(r['ref'] or ''):>10}  "
                  f"{r['own_area_m2']:10,.0f} m2  at {r['lat']},{r['lon']}")
    for s in res.get("sites", ()):
        where = (f"way {s['way']} ref '{s.get('ref')}' "
                 f"({s['own_area_m2']:,.0f} m2, ring "
                 f"{s.get('ring_dist_to_on_m')} m from the ON class)"
                 if s["in_over_class"] else "NOT in the OVER class")
        print(f"  site {s['lat']},{s['lon']}: {where}; the POINT is "
              f"{s['dist_to_on_m']} m from the ON class")
    if res.get("beyond"):
        return
    print(f"  {res['over']} over {res['on']}: {res['stacked']} of "
          f"{res['over_ways']} way(s) stand on {res['on_ways']} way(s), "
          f"{res['area_m2']:.0f} m2 total "
          f"(floor {res['min_area_m2']:g} m2)")
    for r in res["rows"][:top]:
        on = ", ".join(f"{h['shapeID'] or h['way']}:{h['area_m2']:.0f}"
                       for h in r["on"][:3])
        print(f"    way {r['way']:>8} shape {str(r['shapeID']):>6}  own "
              f"{r['own_area_m2']:9.0f} m2  over {r['over_area_m2']:9.0f} "
              f"m2 ({100.0 * (r['over_frac'] or 0.0):4.0f} %)  on {on}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Area of one emitted role/ref class standing on "
                    "another, per patch.")
    ap.add_argument("files", nargs="+", help="emitted patch .osm "
                                             "(its .axes.json is required)")
    ap.add_argument("--over", required=True,
                    help="the class that STANDS ON, as ROLE or ROLE:REF")
    ap.add_argument("--on", required=True,
                    help="the class STOOD ON, comma list of ROLE[:REF]")
    ap.add_argument("--min-area", type=float, default=DEFAULT_MIN_AREA_M2)
    ap.add_argument("--pad", type=float, default=0.0,
                    help="grow the ON union by M metres before reading "
                         "(the OWNERSHIP frame: RULINGS 31b's contact "
                         "scope is SERVICE_ROAD_PAVEMENT_NEAR_M of "
                         "aircraft pavement)")
    ap.add_argument("--beyond", action="store_true",
                    help="report the COMPLEMENT: the OVER ways that do "
                         "NOT reach the (padded) ON union, totalled and "
                         "split by ref — the far-population read")
    ap.add_argument("--site", action="append", default=[],
                    metavar="LAT,LON",
                    help="a named place: which OVER way covers it (if "
                         "any) and how far it is from the ON class")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    sites = [tuple(float(v) for v in s.split(",")) for s in a.site]
    out = []
    for f in a.files:
        res = read(f, over=a.over, on=a.on, min_area_m2=a.min_area,
                   pad_m=a.pad, beyond=a.beyond, sites=sites)
        _report(res, a.top)
        out.append(res)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
        print(f"  -> {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
