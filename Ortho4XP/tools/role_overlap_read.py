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
        [--min-area M2] [--top N] [--json OUT.json]

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
         min_area_m2: float = DEFAULT_MIN_AREA_M2):
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
            "over_ways": len(over_ways), "on_ways": len(on_ways),
            "stacked": len(rows), "area_m2": round(total, 1),
            "rows": rows}


def _report(res: dict, top: int) -> None:
    print(f"=== {res['patch']}")
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
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    out = []
    for f in a.files:
        res = read(f, over=a.over, on=a.on, min_area_m2=a.min_area)
        _report(res, a.top)
        out.append(res)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
        print(f"  -> {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
