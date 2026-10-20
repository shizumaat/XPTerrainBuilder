"""THE LOWER LEVEL OF A STEPPED UNIT'S PAD (owner RULINGS 2026-10-19ai, #809;
amends the flat-pad cut of 2026-09-30r; follows 2026-10-19y; spec
``docs/specs/low-level-pad-spec.md``).

"Where an object carries its own one-storey step, its rigid pad gets a
second, lower level along that step, tied to the airside level, and
landside roads meet the lower level."  Measured KATL east terminal
(33.641271, −84.416453): the terminal unit ``terminal_F`` stands on ONE
held block (``building31/b0``, 79,176 m²) flat at the apron's 300.76 m
while 71,302 m² of the unit's parts are authored a storey down (base
y −13 against 0 at the apron) over ground whose DEM median is 289.5 m —
the landside roads welded to the block's rim rode up 10 m with it.

THE WITNESS IS THE OBJECT.  For each HELD block (or whole held unit) the
pack unit standing on it (the plurality of part centres inside the pad)
gives a TOP level ``t`` — the median authored base ``y`` of its parts at
the welded frontage — and its LOW parts: base ``y <= t −
[building_pad] low_level_min_step_m``.  Their plan footprints, inside the
pad, closed by ``pad_frontage_m`` and kept off the airside by the same
distance, are the LOW REGION.  Only a unit whose composed base reads
STEPPED is read (``pad_blocks.unit_base``; RULINGS 2026-10-02aj (2)).

THE LEVEL IS TIED TO THE BLOCK.  The low region is minted as
``<block>/p1`` (the plane-pad grammar, ``model.planar.plane_ref``) and
registered in ``Registries.landings`` with ``kind = "low_level"``: it is an
ordinary pad (flat, priced to its own ground like every pad), and
``constraints/platform.landing_rows`` BANDS every vertex of it against the
block's DATUM COLUMN, ``D + y_lo <= z <= D + y_hi`` (hard, after stage 1 —
the airside never follows it): never below the object's lowest low part
(``y_lo``, its foundation) and at least one storey under the block
(``y_hi`` = −``low_level_min_step_m``).  The ground decides where in the
object's storey the low level sits (KATL: 289.5 m under a block solved at
300.76, the parts reaching 16.4 m down), so the landside roads meet their
own ground.  Between the two levels a RISER STRIP ``<block>/p1#strip``
(the block strip's spelling: a bank, skipped by every pad reader) of
``max(identity spacing, 2 x grid)`` — the base-profile spec's riser
(§2 (3), Q2: the steepest cell, never a 1:3 bank under a building).

The object stage never sees a second level: ``airport/placement_read``
publishes the low pad and its strip under the BLOCK's ref at the block's
plane (``model.planar.plane_origin_ref``), so the unit is seated as one
body at the airside datum — the anchor of 19y."""
from __future__ import annotations

import dataclasses as _dc
import statistics as _st
import typing as _t

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..geom.parts import nonempty_polygon_parts
from ..model.planar import STRIP_SUFFIX, plane_ref
from ..model.registries import Registries

__all__ = ["LOW_KIND", "low_level_split", "plan_low"]

#: the ``Registries.landings`` record kind of a lower level (a ramp
#: landing's record carries no kind)
LOW_KIND = "low_level"


def _unit_parts(P: Polygon, airport, to_xy) -> list:
    """``[(part, (x, y))]`` of the pack unit holding the plurality of part
    centres inside ``P`` (one unit, one authored frame)."""
    part = getattr(airport, "partition", None)
    if part is None:
        return []
    by: dict[int, list] = {}
    for ui, u in enumerate(part.units):
        for m in u.members:
            for p in m.parts:
                if getattr(p, "line", False):
                    continue
                xy = to_xy(p.lon, p.lat)
                if P.contains(Point(xy)):
                    by.setdefault(ui, []).append((p, xy))
    if not by:
        return []
    return max(by.values(), key=len)


def _ring_poly(rg, to_xy) -> "Polygon | None":
    if len(rg) < 3:
        return None
    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
    g = g if g.is_valid else g.buffer(0.0)
    return None if g.is_empty else g


def plan_low(P, air, airport, law, grid: float, others=None
             ) -> "tuple[_t.Any, _t.Any, _t.Any, dict] | None":
    """``(high, low, strip, record)`` for one held pad ``P`` (module
    docstring), or ``None`` where its unit carries no lower storey."""
    bp = law.tables.structures.building_pad
    step_min = float(getattr(bp, "low_level_min_step_m", 0.0) or 0.0)
    if step_min <= 0.0:
        return None
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    pmin = float(bp.min_area_m2)
    to_xy = airport.frame.entry()
    parts = _unit_parts(P, airport, to_xy)
    if not parts:
        return None
    front = air.buffer(near)
    top_ys = [p.base_y for p, _xy in parts
              if any((g := _ring_poly(rg, to_xy)) is not None and g.intersects(front)
                     for rg in p.rings)]
    if not top_ys:
        return None
    # THE FRONTAGE LEVEL: the base most of the frontage parts stand at (a
    # canopy edge or a roof trim at the frontage stands ABOVE it, a buried
    # sill below — neither is the floor the apron meets)
    t = min(_st.multimode(round(y) for y in top_ys))
    low_parts = [p for p, _xy in parts if p.base_y <= t - step_min]
    if not low_parts:
        return None
    polys = [g for p in low_parts for rg in p.rings
             if (g := _ring_poly(rg, to_xy)) is not None]
    if not polys:
        return None
    L = unary_union(polys).buffer(near, join_style=2).buffer(-near, join_style=2)
    L = L.intersection(P).difference(air.buffer(near, join_style=2))
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    if others is not None and not others.is_empty:
        # ANOTHER PAD the low level touches keeps its own floor (two pads
        # may sit at different floors, ``step_exemption_pad_to_pad``): the
        # riser runs along it too, never one vertex at two levels
        # (MEASURED KATL: ``building34`` / ``building36`` at the apron's level
        # shared 10 vertices with the low level and held it up)
        L = L.difference(others.buffer(w, join_style=2))
    keep = [q for q in nonempty_polygon_parts(L) if q.area >= pmin]
    # A STOREY OF THE UNIT, not a sill: the low level is a unit pad's worth
    # of ground (``[placement] cluster_pad_min_m2``, the §30 (4) bar) —
    # MEASURED KATL ``building11``: two parts 7 m down over 571 m² asked a
    # 3 m drop of ground the apron holds, and the band was relaxed
    if sum(q.area for q in keep) < float(law.tables.structures.placement.cluster_pad_min_m2):
        return None
    L = unary_union(keep)
    S = P.intersection(L.buffer(w, join_style=2)).difference(L)
    H = P.difference(L.buffer(w, join_style=2))
    if H.is_empty or H.area < pmin:
        return None                  # the frontage block must stay a block
    y_floor = min(p.base_y for p in low_parts) - t
    rec = {"top_y": round(t, 3), "y_lo": round(y_floor, 3), "y_hi": round(-step_min, 3),
           "low_parts": len(low_parts), "area_m2": round(L.area, 1),
           "ground_z": _ground(L, getattr(airport, "dem", None), near)}
    return H, L, S, rec


def _ground(L, dem, step: float) -> "float | None":
    """THE LOWER LEVEL'S OWN GROUND: the median DEM over its AREA (a grid
    of ``step`` metres, at least 400 samples' worth) — never its ring's
    mean, whose riser side stands on the slope up to the block (MEASURED
    KATL: the ring read 292.9 m, the area 289.5)."""
    import math
    if dem is None or L.is_empty:
        return None
    x0, y0, x1, y1 = L.bounds
    h = max(step, math.sqrt(L.area / 400.0))
    zs = []
    y = y0 + 0.5 * h
    while y < y1:
        x = x0 + 0.5 * h
        while x < x1:
            if L.contains(Point(x, y)):
                try:
                    z = float(dem.z(x, y))
                except Exception:  # noqa: BLE001 — off the raster
                    z = float("nan")
                if z == z:
                    zs.append(z)
            x += h
        y += h
    return round(_st.median(zs), 3) if zs else None


def low_level_split(out: list, air_polys: _t.Sequence[Polygon], airport,
                    law, grid: float, counts: dict, *, reg: Registries) -> list:
    """The pad regions ``out`` with every held block whose unit carries a
    lower storey split into its high block, its low level ``<ref>/p1`` and
    the riser strip (module docstring); each low level registered in
    ``reg.landings``."""
    from .pad_blocks import unit_base
    from ..airport.obj8_grade import STEPPED
    if (airport is None or getattr(airport, "frame", None) is None
            or not air_polys):
        return out
    held = reg.held
    tree = STRtree(list(air_polys))
    groups: dict[str, list] = {}
    for r in out:
        ref = str(r.ref)
        h = held.get(ref)
        if h is not None and not h.get("conforming") and r.polygon is not None:
            groups.setdefault(ref, []).append(r)
    done: dict[str, list | None] = {}
    for ref, regs in sorted(groups.items()):
        P = unary_union([r.polygon for r in regs])
        if P.is_empty or unit_base(P, airport)[0] != STEPPED:
            continue
        air = unary_union([air_polys[int(j)] for j in
                           tree.query(P.buffer(50.0), predicate="intersects")])
        if air.is_empty:
            continue
        others = unary_union([r.polygon for r in out if str(r.ref) != ref
                              and r.polygon is not None and r.polygon.intersects(P.buffer(1.0))])
        got = plan_low(P, air, airport, law, grid, others)
        if got is None:
            continue
        H, L, S, rec = got
        tmpl = regs[0]
        low = plane_ref(ref, 1)
        done[ref] = ([_dc.replace(tmpl, polygon=q) for q in nonempty_polygon_parts(H)]
                     + [_dc.replace(tmpl, ref=low, polygon=q) for q in nonempty_polygon_parts(L)]
                     + [_dc.replace(tmpl, ref=low + STRIP_SUFFIX, polygon=q)
                        for q in nonempty_polygon_parts(S)])
        reg.landings[low] = {"block": ref, "y": rec["y_lo"], "deck": None,
                             "kind": LOW_KIND, **rec}
    if not done:
        return out
    res: list = []
    for r in out:
        ref = str(r.ref)
        if ref in done:
            if done[ref] is not None:
                res.extend(done[ref])
                done[ref] = None
            continue
        res.append(r)
    counts["low_levels"] = sum(1 for v in reg.landings.values() if v.get("kind") == LOW_KIND)
    counts["low_level_list"] = "; ".join(
        f"{k} on {v['block']} band [{v['y_lo']:+.2f}, {v['y_hi']:+.2f}] {v['area_m2']:g} m2"
        for k, v in sorted(reg.landings.items()) if v.get("kind") == LOW_KIND)
    return res
