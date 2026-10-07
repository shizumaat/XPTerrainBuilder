"""THE ROW CLASSES of a census (``census.py --class``): every ADJUDICATED
row bucketed by WHAT ITS TWO WAYS ARE — standing pavement, a mapped-road
ribbon, a §55 gap part (inside one part, a lot | ramp of one step part on
their breakline, two parts ACROSS A KNIFE, two pieces) — and, in the two
grade families, by whether the pair stands over its cap by more than the
last stage's own floor (the patch sidecar's ``late_stage.floor_m``).

WHY (spec §55 (7), (15)): a family delta says a class moved by N; the
acceptance of the gap stage asks WHICH N — the rows the floor welds, the
rows a knife declares, the rows a ribbon carries — and a STOP on a family
outside its predicted band is reported "with the rows classed".  Promoted
from a lane scratch script on its second use (gaps7's ``rows_class.py``).

The classes read the row's OWN ways (``census.row_ways``) and the ref
spellings' ONE readers (``model.planar.is_gap_ref`` / ``is_osm_ribbon_ref``
/ ``gap_parts_across_knife`` / ``gap_step_part``): nothing is re-derived.
"""
from __future__ import annotations

from typing import Optional

__all__ = ["FLOOR_FAMILIES", "way_kind", "row_class", "class_table", "format_class_tables"]

#: The families whose rows are split against the floor: the two that price
#: a pavement pair at a grade and carry a cap on the row.
FLOOR_FAMILIES = ("within_shape", "pavement_over_road_cap")


def _planar():
    from auto_patch_v2.model import planar
    return planar


def way_kind(ref) -> str:
    """``part`` (a §55 gap part), ``ribbon`` (a mapped-road ribbon) or
    ``standing`` (everything the earlier stages solved)."""
    mp = _planar()
    return "part" if mp.is_gap_ref(ref) else "ribbon" if mp.is_osm_ribbon_ref(ref) else "standing"


def _ref(way) -> str:
    return str((getattr(way, "tags", None) or {}).get("ref") or getattr(way, "ref", "") or "")


def row_class(family: str, ref_a: str, ref_b: str, *, magnitude_m: Optional[float] = None,
              cap_pct: Optional[float] = None, distance_m: Optional[float] = None,
              floor_m: float = 0.0) -> str:
    """The bucket of one row (module docstring)."""
    mp = _planar()
    ka, kb = way_kind(ref_a), way_kind(ref_b)
    if ka == kb == "part":
        a, b = ref_a.split("#")[0], ref_b.split("#")[0]
        if a == b:
            k = "inside one part"
        elif mp.gap_parts_across_knife(a, b):
            k = "two parts ACROSS A KNIFE"
        elif mp.gap_step_part(a) == mp.gap_step_part(b):
            k = "lot | ramp of one part (breakline)"
        else:
            k = "two pieces"
    elif "part" in (ka, kb):
        k = "part | " + (kb if ka == "part" else ka)
    elif ka == kb == "ribbon":
        k = "ribbon (follower or not)"
    else:
        k = " | ".join(sorted((ka, kb)))
    if (floor_m > 0.0 and family in FLOOR_FAMILIES and k != "standing | standing"
            and cap_pct and distance_m and magnitude_m is not None):
        over = magnitude_m - cap_pct / 100.0 * distance_m
        k += " — over the cap by <= the floor" if over <= floor_m else " — over the cap by > the floor"
    return k


def class_table(cg, all_rows, floor_m: float = 0.0) -> dict:
    """``{family: [{"class", "n", "worst": {...}}, ...]}`` over the
    ADJUDICATED rows of ``all_rows`` (``[(family, row), ...]``, the census's
    own population), largest bucket first."""
    out: dict = {}
    for family, r in all_rows:
        if not cg.row_adjudicated(family, r):
            continue
        wa = getattr(r, "way_a", None) or getattr(r, "way_v", None)
        wb = getattr(r, "way_b", None) or getattr(r, "way_e", None)
        mag = float(cg.row_magnitude(r))
        dist = getattr(r, "distance_m", None)
        k = row_class(family, _ref(wa), _ref(wb), magnitude_m=mag,
                      cap_pct=getattr(r, "cap_pct", None), distance_m=dist, floor_m=floor_m)
        b = out.setdefault(family, {}).setdefault(k, {"class": k, "n": 0, "worst": None})
        b["n"] += 1
        if b["worst"] is None or mag > b["worst"]["magnitude_m"]:
            b["worst"] = {"magnitude_m": round(mag, 4),
                          "distance_m": round(float(dist), 3) if dist is not None else None,
                          "lat": getattr(r, "lat", None), "lon": getattr(r, "lon", None),
                          "refs": [_ref(wa), _ref(wb)], "side": cg.row_side(r)}
    return {fam: sorted(b.values(), key=lambda x: (-x["n"], x["class"]))
            for fam, b in out.items()}


def format_class_tables(reports: list) -> list[str]:
    """The printed block: per patch, per family with rows, the buckets;
    with several patches the FIRST is the base and each later family line
    carries its delta against it."""
    lines: list[str] = []
    base = {fam: sum(b["n"] for b in bs)
            for fam, bs in (reports[0].get("row_classes") or {}).items()} if reports else {}
    for i, rep in enumerate(reports):
        table = rep.get("row_classes")
        if table is None:
            continue
        lines.append(f"\n=== ROW CLASSES (adjudicated rows by what they stand on; floor "
                     f"{rep.get('row_class_floor_m', 0.0):g} m): {rep['patch']} ===")
        for fam, buckets in table.items():
            n = sum(b["n"] for b in buckets)
            delta = f" (first patch {base.get(fam, 0)}, delta {n - base.get(fam, 0):+d})" if i else ""
            lines.append(f"  {fam}: {n}{delta}")
            for b in buckets:
                w = b["worst"]
                at = (f"{w['lat']:.7f}, {w['lon']:.7f}" if w["lat"] is not None
                      and w["lon"] is not None else "-")
                lines.append(f"    {b['n']:6d}  {b['class']}; worst {w['magnitude_m']:.2f} m over "
                             f"{w['distance_m'] or 0:.1f} m at {at} [{w['refs'][0]} | {w['refs'][1]}]")
    return lines
