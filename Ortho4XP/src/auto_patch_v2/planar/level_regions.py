"""THE LOWER-LEVEL REGIONS FROM OBJECT WITNESSES (round 4; #1852, #1717;
owner RULINGS 2026-11-03b Q340 a, 2026-11-04a (4)/(11); spec
``docs/specs/two-level-regions-20261103.md`` §2.1 / §2.2, round-4 review).

``planar/low_level`` reads a lower level only off a HELD, non-conforming
block whose unit's composed base reads STEPPED (or whose group reads a
stand-side floor), and ``planar/low_extent`` grows only a level that
exists.  A unit whose walls stand a storey under its own zero on a pad that
is no stepped block -- a station box on a §20 conforming pad, far from any
stand -- states a lower level nobody reads.  MEASURED KIAH (capture
kiahstation): ``KIAH_Trainstation2.obj`` (unit 60) on ``building88``, its
two walled parts' feet at y -3.93; the unreachable apron piece beside it
(``pav62#beyond1``, DEM 25.0) stayed welded to Terminal D's rim at 28.77.

W1, WALLS BELOW THE ZERO (:func:`level_seeds`).  A unit's walled parts
(``[placement] chain_min_height_m``) that are no supports
(``geom/foot_planes.is_support``) whose densest ``PLANE_BAND_M`` foot plane
stands at least ``[building_pad] low_level_min_step_m`` under the unit's
zero ``z0`` -- its stand-side airside floor where the stands read one
(``low_level.stand_floor``), else its authored zero, the plane the object
stage seats it at on its pad -- are a LEVEL SEED: their rings are its
footprint, ``z0 - y_feet`` its stated depth.  The OBJECT is the witness;
the DEM alone never makes one (KATL ``building30``).

STEP (b), THE PIECES TOUCHING A SEED (:func:`seed_levels`).  Every
unreachable pavement piece (``planar/reach_after_pads``' and
``planar/reach_under_covers``' ``#beyond``) the footprint touches, less the
pads and a riser's width and the airside and ``pad_frontage_m``, is the
seed's lower level, ``depth`` under the LEVEL A beside it (spec §3, Q342 a):
``<block>/p<k>`` (kind ``low_level``) of the held block the piece fronts --
the nearest whose datum the block plan predicts (``Registries.held``
``datum_pred``) -- at ``y_lo = -depth`` under that block's datum
(``constraints/platform.landing_rows``), with its riser strip along the
pads and every open edge (``low_extent._riser``, Q341 a).  MEASURED KIAH:
``pav62#beyond1`` fronts Terminal D (``building94``, D 28.77), so its floor
is 24.84 over a DEM of 25.0.  THE GROUND CONFIRMS IT (#1115): the piece's
DEM median must stand nearer that floor than the block's datum (under
``D - depth / 2``) -- a storey over level ground mints nothing.  A seed
whose footprint is already a lower level, or a piece no predicted block
fronts within ``pad_frontage_m`` and a riser, mints nothing and is
counted.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area
from ..law.tables import role_side
from ..model.planar import STRIP_SUFFIX, plane_of, plane_ref
from ..model.registries import Registries

__all__ = ["LevelSeed", "level_seeds", "region_depths", "seed_levels"]

#: the ``witness`` word of a seed level's record
WALLS_WITNESS = "walls"


class LevelSeed(_t.NamedTuple):
    """One object witness of lower ground: its plan ``footprint`` (frame
    xy), the partition ``unit``, the unit's zero ``z0`` and lower foot plane
    ``y_feet`` (authored y), the stated ``depth`` (``z0 - y_feet``) and the
    walled parts read."""

    footprint: _t.Any
    unit: int
    z0: float
    y_feet: float
    depth: float
    parts: int


def level_seeds(airport, classification, law) -> "tuple[tuple[LevelSeed, ...], list[str]]":
    """``(seeds, notes)``: the W1 seeds of the airport (module docstring),
    read off the pack partition and the classification's airside cells --
    before the structures pass."""
    part = getattr(airport, "partition", None)
    if part is None or classification is None or not classification.cells:
        return (), []
    from .low_level import _stands_xy
    bp = law.tables.structures.building_pad
    step = float(getattr(bp, "low_level_min_step_m", 0.0) or 0.0)
    if step <= 0.0:
        return (), []
    air = [Polygon(c.ring, c.holes) for c in classification.cells
           if len(c.ring) >= 3 and role_side(law, c.role) == "airside"]
    air = [p if p.is_valid else p.buffer(0.0) for p in air]
    tree = STRtree(air) if air else None
    to_xy = airport.frame.entry()
    stands = _stands_xy(airport, to_xy)
    seeds: list[LevelSeed] = []
    notes: list[str] = []
    for ui, u in enumerate(part.units):
        parts = [(p, to_xy(p.lon, p.lat)) for m in u.members for p in m.parts
                 if not getattr(p, "line", False)]
        got = _unit_seed(ui, parts, tree, air, stands, law, to_xy, step)
        if got is None:
            continue
        F, z0, y_feet, n = got
        seeds.append(LevelSeed(F, ui, round(z0, 3), round(y_feet, 3), round(z0 - y_feet, 3), n))
        notes.append(f"unit {ui} depth {z0 - y_feet:.2f} ({n} walled parts, "
                     f"{F.area:.0f} m2)")
    return tuple(seeds), notes


def _unit_seed(ui, parts, tree, air, stands, law, to_xy, step: float):
    """``(footprint, z0, y_feet, low parts)`` of one unit's walls below its
    zero, or ``None``."""
    from ..airport.airside_group_seat import PLANE_BAND_M
    from ..geom.foot_planes import is_support
    from .low_level import _densest, _ring_poly, stand_floor
    if not parts:
        return None
    wall_min = float(law.tables.structures.placement.chain_min_height_m)
    z0 = 0.0
    if tree is not None and stands:
        xs = [xy[0] for _p, xy in parts]
        ys = [xy[1] for _p, xy in parts]
        hit = tree.query(box(min(xs), min(ys), max(xs), max(ys)).buffer(60.0))
        if len(hit):
            sf = stand_floor(parts, unary_union([air[int(j)] for j in hit]), stands, law, to_xy)
            if sf is not None:
                z0 = float(sf[0])
    low, feet = [], []
    for p, _xy in parts:
        rings = [g for rg in p.rings if (g := _ring_poly(rg, to_xy)) is not None]
        fy = sorted(float(f[2]) for f in (getattr(p, "feet", ()) or ()))
        if (fy and float(getattr(p, "height_m", 0.0) or 0.0) >= wall_min
                and not is_support(p, law) and _densest(fy, PLANE_BAND_M)[1] <= z0 - step):
            low.extend(rings)
            feet.extend(fy)
    if not low:
        return None
    F = valid_area(unary_union(low))
    if F.is_empty:
        return None
    _n, y_feet = _densest(sorted(feet), PLANE_BAND_M)
    return F, z0, float(y_feet), len(low)



def _ground(g, dem, step: float):
    from .low_level import _ground as ground
    return ground(g, dem, step)



def seed_levels(regs: list, reg: Registries, seeds: _t.Sequence[LevelSeed], air_all, airport,
                law, grid: float, counts: dict, beyond: _t.Sequence = ()) -> list:
    """``regs`` (the pad regions, the levels minted) with each seed's lower
    level over the unreachable pieces it touches minted beside them (module
    docstring, step (b)); each piece registered in ``reg.landings``."""
    from .low_extent import _riser
    from .low_level import LOW_KIND
    counts["level_seeds"] = len(seeds)
    if not seeds or not beyond:
        return regs
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    by_ref: dict[str, list] = {}
    for r in regs:
        if r.polygon is not None and not r.polygon.is_empty:
            by_ref.setdefault(str(r.ref), []).append(r)
    lows = valid_area(unary_union([r.polygon for ref, rs in by_ref.items()
                                   if reg.landings.get(ref, {}).get("kind") == LOW_KIND
                                   for r in rs]))
    held = {ref: unary_union([r.polygon for r in by_ref[ref]]) for ref in reg.held
            if ref in by_ref}
    pads = valid_area(unary_union([r.polygon for rs in by_ref.values() for r in rs]))
    air = valid_area(unary_union([r.polygon for r in air_all if r.polygon is not None]))
    n_k: dict[str, int] = {}
    for ref in [*reg.landings, *by_ref]:
        po = plane_of(ref)
        if po is not None:
            n_k[po[0]] = max(n_k.get(po[0], 0), po[1])
    made: list = []
    notes: list[str] = []
    dem = getattr(airport, "dem", None)
    for s in seeds:
        F = s.footprint
        if not lows.is_empty and lows.intersection(F).area >= 0.5 * F.area:
            continue                       # already a lower level (low_level / low_extent)
        cand = [g for g in beyond if g.distance(F) <= near]
        if not cand:
            continue
        keep_off = valid_area(unary_union([pads.buffer(w, join_style=2),
                                           air.buffer(near, join_style=2)]))
        qs = nonempty_polygon_parts(valid_area(valid_area(unary_union(cand))
                                               .difference(keep_off)))
        smalls = [g for g in qs if g.area < pmin]
        for q in qs:
            if q.area < pmin:
                continue
            block = _front_block(q, held, reg.held, near + w)
            if block is None:
                notes.append(f"unit {s.unit}: a {q.area:.0f} m2 piece fronts no predicted block")
                continue
            D = float(reg.held[block]["datum_pred"])
            g = _ground(q, dem, 2.0)
            if g is None or g > D - 0.5 * s.depth:
                # THE GROUND CONFIRMS IT (#1115): a storey over level ground
                notes.append(f"unit {s.unit}: ground {g} over {block}'s D {D:.2f} - "
                             f"{s.depth:.2f}/2")
                continue
            n_k[block] = n_k.get(block, 0) + 1
            ref = plane_ref(block, n_k[block])
            S = _riser(q, pads, air, w, near, smalls)
            tmpl = by_ref[block][0]
            made.append(_dc.replace(tmpl, ref=ref, polygon=q))
            made.extend(_dc.replace(tmpl, ref=ref + STRIP_SUFFIX, polygon=e)
                        for e in nonempty_polygon_parts(S))
            reg.landings[ref] = {"block": block, "y": -s.depth, "y_lo": -s.depth,
                                 "y_hi": -step, "y_feet": s.y_feet, "top_y": s.z0,
                                 "deck": None, "kind": LOW_KIND, "witness": WALLS_WITNESS,
                                 "low_parts": s.parts, "area_m2": round(q.area, 1),
                                 "ground_z": g, "ground_high_z": round(D, 3),
                                 "seed_unit": s.unit}
            pads = unary_union([pads, q.buffer(w, join_style=2)])
            notes.append(f"{ref} of unit {s.unit} y {-s.depth:+.2f} {q.area:.0f} m2 "
                         f"(floor {D - s.depth:.2f}, DEM {g})")
    if notes:
        counts["level_seed_list"] = "; ".join(notes)
    counts["level_seed_levels"] = sum(1 for v in reg.landings.values()
                                      if v.get("witness") == WALLS_WITNESS)
    return regs + made


def _front_block(q, polys: dict, held: dict, reach: float) -> "str | None":
    """The held block the piece ``q`` fronts: of the blocks whose datum the
    block plan predicts, the one sharing the most of ``q``'s rim within
    ``reach`` (the riser and keep-off between them)."""
    ring = q.buffer(reach, join_style=2)
    best, length = None, 0.0
    for ref, g in polys.items():
        if held.get(ref, {}).get("datum_pred") is None or g.distance(q) > reach:
            continue
        a = g.intersection(ring).area
        if a > length:
            best, length = ref, a
    return best


def region_depths(regs: list, reg: Registries, law, grid: float, counts: dict) -> list:
    """STEPS (f) AND §3, ONE REGION, ONE DEPTH (spec §2.2 step 7, §3; Q342 a):
    the lower levels that touch -- a riser's width apart or across one's
    riser strip -- are held at ONE zero (one group's witnesses and top,
    ``planar/group_low``; or one block's datum) and whose floors (``y_lo``)
    lie within one ``PLANE_BAND_M`` (one floor, as the foot-plane reader
    reads one) are one region, and stand at one depth: the area-weighted
    median of their own stated floors.  The riser strip between two of them
    is the region's floor, never a step inside it.  MEASURED LFPG T2
    (capture lfpg6): the corridor ``building35/p2`` (143,204 m2, the central
    buildings' bottom 6.97 m under the group's zero) and the trench pads
    ``building34/35/51/64/p1`` (7.37-7.39 m) behind 0.4 m risers inside the
    one corridor.  Floors a band or more apart keep their object step
    (KATL ``building46``: the terminal's lower storey at -13.03, the apron
    walls' bottoms at -11.51 and -9.70, 27h).

    A covered cut's level is the cut's own (``planar/covered_cut``) and
    joins no region."""
    from .covered_cut import WITNESS as _COVERED
    from .low_level import LOW_KIND
    lows = {r: v for r, v in reg.landings.items() if v.get("kind") == LOW_KIND
            and v.get("witness") != _COVERED and v.get("y_lo") is not None}
    if len(lows) < 2:
        return regs
    from ..airport.airside_group_seat import PLANE_BAND_M
    band = float(PLANE_BAND_M)
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    polys: dict[str, list] = {}
    for r in regs:
        if str(r.ref) in lows and r.polygon is not None and not r.polygon.is_empty:
            polys.setdefault(str(r.ref), []).append(r.polygon)
    geo = {k: unary_union(v) for k, v in polys.items()}
    refs = sorted(geo)
    parent = {k: k for k in refs}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            if (_zero(lows[a]) == _zero(lows[b]) and geo[a].distance(geo[b]) <= 1.5 * w
                    and abs(float(lows[a]["y_lo"]) - float(lows[b]["y_lo"])) <= band):
                parent[find(a)] = find(b)
    comps: dict[str, list[str]] = {}
    for k in refs:
        comps.setdefault(find(k), []).append(k)
    joined: dict[str, str] = {}
    notes: list[str] = []
    for members in comps.values():
        ys = {round(float(lows[k]["y_lo"]), 3) for k in members}
        if len(members) < 2:
            continue
        y = _area_median([(float(lows[k]["y_lo"]), geo[k].area) for k in members])
        for k in members:
            rec = lows[k]
            if rec.get("y_feet") is not None:
                rec["y_feet"] = round(float(rec["y_feet"]) + y - float(rec["y_lo"]), 3)
            rec["y"] = rec["y_lo"] = round(y, 3)
            rec["region_of"] = members[0]
            joined[k + STRIP_SUFFIX] = k
        notes.append(f"{'+'.join(members)} y {y:+.2f} (was {sorted(ys)})")
    if not notes:
        return regs
    counts["level_regions"] = len(notes)
    counts["level_region_list"] = "; ".join(notes)
    return _strips_inside(regs, joined, geo, 1.5 * w)


def _zero(rec: dict) -> tuple:
    """What a lower level is held at: its group's witnesses and top, else
    its block's datum."""
    if rec.get("air_xy"):
        return ("group", tuple(rec["air_xy"]), rec.get("top_y"))
    return ("block", rec.get("block"))


def _area_median(pairs: list) -> float:
    """The area-weighted median of ``(y, area)``."""
    s = sorted(pairs)
    half, acc = 0.5 * sum(a for _y, a in s), 0.0
    for y, a in s:
        acc += a
        if acc >= half:
            return y
    return s[-1][0]


def _strips_inside(regs: list, joined: dict, geo: dict, near: float) -> list:
    """``regs`` with the part of every joined level's riser strip that lies
    within ``near`` of ANOTHER member of its region re-reffed to the level
    itself (the region's floor, no riser inside it)."""
    members = set(joined.values())
    out: list = []
    for r in regs:
        lvl = joined.get(str(r.ref))
        if lvl is None or r.polygon is None or r.polygon.is_empty:
            out.append(r)
            continue
        others = [geo[m] for m in members if m != lvl and m in geo
                  and geo[m].distance(r.polygon) <= near]
        if not others:
            out.append(r)
            continue
        inner = valid_area(r.polygon.intersection(unary_union(others).buffer(near, join_style=2)))
        rest = valid_area(r.polygon.difference(inner))
        out.extend(_dc.replace(r, ref=lvl, polygon=g) for g in nonempty_polygon_parts(inner))
        out.extend(_dc.replace(r, polygon=g) for g in nonempty_polygon_parts(rest))
    return out
