"""A STATION ON A PAD THAT IS NOT HELD gets its own lower pad, tied to its
group's held block (owner RULINGS 2026-11-03b (6) Q345 a: "the buried
station gets its own cut or lower pad"; answer 2 of 2026-11-03T06:07:15Z:
at the station objects' own wall feet; spec ``rail-piece-ends-station-
spec.md`` R3; issue #1739).

``planar/covered_cut.plan_covered`` reads a lower level under a HELD block.
A station box the classifier minted as its own pad (MEASURED ENGM:
``building19#1``, 6,235 m2 at 204.13 m, inside the terminal's held block
``building24``) is no held block, so no level was ever asked of it and the
whole station volume stood under the pad.  Here every pad region a mapped
RAILWAY crosses (``covered_cut.station_corridors``) that is not itself held
is read by ``plan_covered`` in its STATION form; the level it returns is
registered as a ``low_level`` landing of the nearest held block standing
on the same pack unit (``low_level.unit_share``), so
``constraints/platform.landing_rows`` holds it rigid at that block's datum +
the floor under the station's top level -- the same datum the station's
group is seated on.  A pad whose unit holds no block keeps the tracks
buried and the reason is counted.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..model.planar import STRIP_SUFFIX, plane_ref

__all__ = ["station_split"]


def _next_plane(block: str, reg) -> str:
    k = 1
    while plane_ref(block, k) in reg.landings:
        k += 1
    return plane_ref(block, k)


def station_split(out: list, held: _t.Mapping[str, dict], st, st_reach, st_open,
                  air_polys, tree, airport, law, grid: float, counts: dict, reg,
                  cut_levels: dict) -> list:
    """``out`` with each unheld pad over a station split into its high part,
    its station level and the riser strip (module doc)."""
    from .covered_cut import plan_covered
    from .low_level import LOW_KIND
    held_regions = {}
    for r in out:
        if str(r.ref) in held and r.polygon is not None:
            held_regions.setdefault(str(r.ref), []).append(r.polygon)
    held_union = {k: unary_union(v) for k, v in held_regions.items()}
    from .low_level import unit_share
    to_xy = airport.frame.entry()
    _units: dict = {}

    from ..law.tables import design as design_law
    from .covered_cut import _top
    near = float(design_law(law).pad_frontage_m)

    def top_of(k: str) -> "float | None":
        """The held block's TOP level (``covered_cut._top``, off the tracks)."""
        B = held_union[k]
        parts = unit_share(B, airport, to_xy)[1]
        air_b = unary_union([air_polys[int(j)] for j in
                             tree.query(B.buffer(50.0), predicate="intersects")])
        return _top(parts, air_b, airport, law, to_xy, near, st_reach) if parts else None

    def unit_of(k: str):
        if k not in _units:
            _units[k] = unit_share(held_union[k], airport, to_xy)[0]
        return _units[k]
    pads: dict[str, list] = {}
    for r in out:
        ref = str(r.ref)
        if (ref in held or "/" in ref or r.polygon is None
                or getattr(r, "role", "") != "building" or not r.polygon.intersects(st)):
            continue
        pads.setdefault(ref, []).append(r)
    replaced: dict[str, list] = {}
    for ref, regs in sorted(pads.items()):
        P = unary_union([r.polygon for r in regs])
        ui = unit_share(P, airport, to_xy)[0]
        block = min((k for k, g in held_union.items()
                     if ui is not None and unit_of(k) == ui),
                    key=lambda k: held_union[k].distance(P), default=None)
        if block is None:
            counts.setdefault("station_level_refused_list", []).append(
                f"{ref}: no held block of its pack unit")
            continue
        air = unary_union([air_polys[int(j)] for j in
                           tree.query(P.buffer(50.0), predicate="intersects")])
        others = unary_union([r.polygon for r in out if str(r.ref) != ref
                              and r.polygon is not None and r.polygon.intersects(P.buffer(1.0))])
        why: list = []
        got = plan_covered(P, air, airport, law, grid, st, others, why, st_reach,
                           station=True, open_rail=st_open,
                           top=top_of(block)) if not air.is_empty else None
        if got is None:
            if why:
                counts.setdefault("station_level_refused_list", []).append(f"{ref}: {why[0]}")
            continue
        H, L, S, rec = got
        low = _next_plane(block, reg)
        tmpl = regs[0]
        replaced[ref] = ([_dc.replace(tmpl, polygon=q) for q in nonempty_polygon_parts(H)]
                         + [_dc.replace(tmpl, ref=low, polygon=q)
                            for q in nonempty_polygon_parts(L)]
                         + [_dc.replace(tmpl, ref=low + STRIP_SUFFIX, polygon=q)
                            for q in nonempty_polygon_parts(S)])
        reg.landings[low] = {"block": block, "y": rec["y_lo"], "deck": None,
                             "kind": LOW_KIND, "pad": ref, **rec}
        cut_levels[low] = (L, block, float(rec["y_lo"]))
        counts["station_levels"] = counts.get("station_levels", 0) + 1
    if not replaced:
        return out
    res: list = []
    for r in out:
        ref = str(r.ref)
        if ref in replaced:
            if replaced[ref] is not None:
                res.extend(replaced[ref])
                replaced[ref] = None
            continue
        res.append(r)
    return res
