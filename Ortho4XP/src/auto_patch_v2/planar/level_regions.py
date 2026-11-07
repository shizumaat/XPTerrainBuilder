"""THE LOWER-LEVEL REGIONS FROM OBJECT WITNESSES (round 4; #1852, #1717;
owner RULINGS 2026-11-03b Q340 a, 2026-11-04a (4)/(11); owner 2026-11-04T18:31Z
/ 18:42Z; spec ``docs/specs/two-level-regions-20261103.md`` §2.1 / §2.2 / §16).

``planar/low_level`` reads a lower level only off a HELD, non-conforming
block whose unit's composed base reads STEPPED (or whose group reads a
stand-side floor), and ``planar/low_extent`` grows only a level that
exists.  A pack object the mapped roads run THROUGH -- a station over the
terminal roads -- states a lower level nobody reads.  MEASURED KIAH (capture
kiahstation): ``KIAH_Trainstation2.obj`` (unit 60) on the §20 conforming pad
``building88``; its walls' feet at y -3.93; two service roads and the
primary terminal drive run 76 m through it; the pad held them at 28.0 m, the
station's zero.  Owner (18:42Z): "the KIAH area under the train station is
mostly parallel roadways with a sidewalk in between, should all be flat at
one level. It has to be low enough vehicles can pass under it, so 5m
minimum below the station."

W1, WALLS BELOW THE ZERO (:func:`level_seeds`), read ONCE in
``planar/build``.  A unit's walled parts (``[placement]
chain_min_height_m``) that are no supports (``geom/foot_planes.is_support``)
whose densest ``PLANE_BAND_M`` foot plane stands at least ``[building_pad]
low_level_min_step_m`` under the unit's zero ``z0`` -- its stand-side floor
where the stands read one, else its authored zero, the plane the object
stage seats it at -- are a LEVEL SEED: their rings its footprint, ``z0 -
y_feet`` its stated depth.  The OBJECT is the witness; the DEM never makes
one (KATL ``building30``).  The at-grade mapped roads
(``road_yield.road_carriageways``) crossing the footprint are its PASSAGE,
and the object's underside over them (``planar/level_underside``) its roof.

THE REGION UNDER THE OBJECT (:func:`seed_levels`).  A seed with a passage is
a building the roads run under: the pad it stands on, cut by
``low_level.level_cut`` (closed by ``pad_frontage_m``, the roads over it
taken in, kept that distance off the airside and a riser off the other
pads, the frontage band left as the block), is ONE flat lower level at the
seed's depth -- ``<block>/p<k>`` (kind ``low_level``, witness ``passage``)
of its own pad's block (the datum its zero is seated at; else the predicted
block it fronts), ``y_lo = -depth`` under that datum
(``constraints/platform.landing_rows``).  The roof is read against
``[tunnel] clearance_m``: where the object's soffit over the passage stands
less than that above its wall feet the level is still minted at the walls'
depth and the note reports the clearance (owner 2026-11-04T20:47Z: "set
wall depth and object seating based on the objects sizes").  A seed with
no passage (a basement, a lower storey over level ground) mints nothing.
The unreachable pieces the level touches (``#beyond``) are its floor too
(step (b)), each a riser off the pads; every road leaving the region runs
out to its ground (``planar/cut_runout`` roads, step 8).

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

__all__ = ["level_seeds", "region_depths", "seed_levels"]

#: the ``witness`` word of a passage level's record
PASSAGE_WITNESS = "passage"


class LevelSeed(_t.NamedTuple):
    """One object witness of lower ground: its plan ``footprint`` (frame
    xy), the partition ``unit``, the unit's zero ``z0`` and lower foot plane
    ``y_feet`` (authored y), the stated ``depth`` (``z0 - y_feet``), the
    walled parts read, the at-grade roads' carriageways through it
    (``passage``, or ``None``) and the object's ``underside`` over them
    (``level_underside.underside_over``, or ``None``)."""

    footprint: _t.Any
    unit: int
    z0: float
    y_feet: float
    depth: float
    parts: int
    passage: _t.Any = None
    underside: _t.Any = None
    #: the witness kind (W1 ``"walls"``, the only one built)
    kind: str = "walls"


def level_seeds(airport, classification, law, cache=None
                ) -> "tuple[tuple[LevelSeed, ...], list[str]]":
    """``(seeds, notes)``: the W1 seeds of the airport (module docstring),
    read off the pack partition, the classification's airside cells and the
    mapped roads (``cache``: the object reads' ``ResourceCache``, for the
    underside) -- before the structures pass."""
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
    roads = _carriageways(airport, law)
    seeds: list[LevelSeed] = []
    notes: list[str] = []
    for ui, u in enumerate(part.units):
        parts = [(p, to_xy(p.lon, p.lat)) for m in u.members for p in m.parts
                 if not getattr(p, "line", False)]
        got = _unit_seed(ui, parts, tree, air, stands, law, to_xy, step)
        if got is None:
            continue
        F, z0, y_feet, n = got
        passage = roads(F)
        under = None
        if passage is not None:
            from .level_underside import underside_over
            under = underside_over(u.members, cache, to_xy, passage, y_feet)
        seeds.append(LevelSeed(F, ui, round(z0, 3), round(y_feet, 3), round(z0 - y_feet, 3), n,
                               passage, under))
        notes.append(f"unit {ui} depth {z0 - y_feet:.2f} ({n} walled parts, {F.area:.0f} m2"
                     + (f", passage {passage.area:.0f} m2, soffit "
                        f"{(under or {}).get('soffit_y')}" if passage is not None else "")
                     + ")")
    return tuple(seeds), notes


def _carriageways(airport, law) -> _t.Callable[[_t.Any], _t.Any]:
    """``F -> `` the at-grade mapped roads' carriageways
    (``road_yield.road_carriageways``) across the footprint ``F``, or
    ``None`` where none crosses it."""
    from .road_yield import road_carriageways
    ways = list(road_carriageways(getattr(airport, "osm_ways", ()) or (), law))
    rtree = STRtree([line for line, _h in ways]) if ways else None

    def through(F):
        if rtree is None:
            return None
        hit = [ways[int(j)] for j in rtree.query(F, predicate="intersects")]
        cuts = [valid_area(line.buffer(h, cap_style="flat").intersection(F)) for line, h in hit]
        cuts = [g for g in cuts if not g.is_empty and g.area > 0.0]
        return valid_area(unary_union(cuts)) if cuts else None
    return through


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
    """``regs`` (the pad regions, the levels minted) with the pad under every
    seed with a passage cut into its one flat lower level (module
    docstring); each level registered in ``reg.landings``.  ``beyond``: the
    unreachable pieces, the level's floor where they touch it (step (b),
    :func:`_pieces`)."""
    from .low_level import LOW_KIND, level_cut
    counts["level_seeds"] = len(seeds)
    cands = [s for s in seeds if s.passage is not None]
    if not cands:
        return regs
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    clear = float(law.tables.structures.tunnel.clearance_m)
    by_ref: dict[str, list] = {}
    for r in regs:
        if r.polygon is not None and not r.polygon.is_empty:
            by_ref.setdefault(str(r.ref), []).append(r)
    air = valid_area(unary_union([r.polygon for r in air_all if r.polygon is not None]))
    n_k: dict[str, int] = {}
    for ref in [*reg.landings, *by_ref]:
        po = plane_of(ref)
        if po is not None:
            n_k[po[0]] = max(n_k.get(po[0], 0), po[1])
    notes: list[str] = []
    dem = getattr(airport, "dem", None)
    through = _carriageways(airport, law)

    def roads_of(f):
        return through(f.buffer(2.0 * w, join_style=2)) or Polygon()
    levels: dict[str, tuple] = {}
    gaps: dict[str, _t.Any] = {}
    for s in cands:
        pref = _pad_of(s.footprint, by_ref, reg)
        if pref is None:
            notes.append(f"unit {s.unit}: its passage stands on no pad")
            continue
        if any(reg.landings.get(str(r.ref), {}).get("kind") == LOW_KIND for r in by_ref[pref]):
            continue                       # the pad is already split into levels
        P = valid_area(unary_union([r.polygon for r in by_ref[pref]]))
        P1 = P.buffer(1.0)
        others = valid_area(unary_union([g.polygon for k, rs in by_ref.items() if k != pref
                                         for g in rs if g.polygon.intersects(P1)]))
        A = valid_area(air.intersection(P.buffer(50.0)))
        cut = level_cut(P, s.footprint, A, others, law, grid, 0.0, airport, grow=False,
                        whole=True)
        if cut is None:
            notes.append(f"unit {s.unit}: no level left on {pref} off the airside")
            continue
        H, L, S = cut
        polys = {k: valid_area(unary_union([r.polygon for r in rs])) for k, rs in by_ref.items()
                 if k != pref and k in reg.held}
        # the object is seated on its own pad: its zero is that block's datum,
        # and the level hangs off it -- the frontage band the cut leaves keeps
        # it, so the airside it welds to never follows the level (MEASURED
        # KIAH replay, the level tied to the Terminal D block it fronts: the
        # station pad's frontage band re-seated 0.1 m and pulled two apron
        # rim vertices 0.15-0.18 m)
        block = pref if pref in reg.held else _front_block(L, polys, reg.held,
                                                           near + 2.0 * w)
        if block is None:
            notes.append(f"unit {s.unit}: {pref} fronts no held block")
            continue
        under = s.underside or {}
        soffit = under.get("soffit_y")
        short = soffit is not None and soffit - s.y_feet < clear - 1e-6
        # the walls set the depth and the object is seated by its own
        # geometry even where its soffit stands short of ``clearance_m``
        # (owner 2026-11-04T20:47Z: "set wall depth and object seating based
        # on the objects sizes"; MEASURED LFPG T1 ``T1_16-18``: walls 5.19 m
        # down, a soffit 2.2 m over them): the clearance is reported
        n_k[block] = n_k.get(block, 0) + 1
        ref = plane_ref(block, n_k[block])
        tmpl = by_ref[pref][0]
        # the step at every OPEN edge is vertical (Q341 a): a riser outside
        # the pad, a riser's width, kept off the airside and the pads, and
        # open where the roads leave the level (their run-outs, step 8)
        pads = valid_area(unary_union([r.polygon for r in regs if str(r.ref) != pref]))
        S = valid_area(unary_union([S, valid_area(L.buffer(w, join_style=2).difference(P)
                                                  .difference(pads.buffer(0.5 * w))
                                                  .difference(air.buffer(near)))]))
        gaps[ref + STRIP_SUFFIX] = roads_of(L)
        made = ([_dc.replace(tmpl, polygon=q) for q in nonempty_polygon_parts(H)]
                + [_dc.replace(tmpl, ref=ref, polygon=q) for q in nonempty_polygon_parts(L)]
                + [_dc.replace(tmpl, ref=ref + STRIP_SUFFIX, polygon=q)
                   for q in nonempty_polygon_parts(S)])
        regs = [r for r in regs if str(r.ref) != pref] + made
        by_ref = {}
        for r in regs:
            if r.polygon is not None and not r.polygon.is_empty:
                by_ref.setdefault(str(r.ref), []).append(r)
        reg.landings[ref] = {"block": block, "y": -s.depth, "y_lo": -s.depth, "y_hi": -step,
                             "y_feet": s.y_feet, "top_y": s.z0, "deck": None, "kind": LOW_KIND,
                             "witness": PASSAGE_WITNESS, "pad": pref, "low_parts": s.parts,
                             "area_m2": round(L.area, 1), "ground_z": _ground(L, dem, 2.0),
                             "ground_high_z": None, "seed_unit": s.unit,
                             "soffit_y": soffit, "overhead_y": under.get("any_y"),
                             "clearance_m": None if soffit is None else round(soffit - s.y_feet, 3),
                             "clearance_short": bool(short)}
        levels[ref] = (L, block, -s.depth)
        # STEP (b): the unreachable pieces the level touches -- the roads and
        # walks beside the passage -- are its floor too, off the pads and the
        # airside, a riser along every pad and open edge but where their
        # roads leave (MEASURED KIAH: ``pav62#beyond1`` welded to Terminal
        # D's rim at 28.08 m over a DEM of 25.0, torn 3.9 m to the station
        # level when left out)
        regs, more = _pieces(regs, reg, L, beyond, block, ref, s, air, near, w, n_k,
                             roads_of, dem, step,
                             float(law.tables.structures.building_pad.min_area_m2), gaps)
        levels.update(more)
        notes.append(f"{ref} of unit {s.unit} on {pref}: y {-s.depth:+.2f} {L.area:.0f} m2, "
                     f"soffit {soffit} ({'SHORT of' if short else 'clears'} {clear:g} m), "
                     f"lowest overhead {under.get('any_y')}")
    if levels:
        # STEP 8, THE RUN-OUTS: every road leaving a level runs out at the
        # road ramp law to its ground (``planar/cut_runout`` roads)
        regs = _run_out(regs, reg, levels, gaps, air, airport, law, grid, counts)
    if notes:
        counts["level_seed_list"] = "; ".join(notes)
    counts["level_seed_levels"] = sum(1 for v in reg.landings.values()
                                      if v.get("witness") == PASSAGE_WITNESS)
    return regs


def _pieces(regs: list, reg: Registries, L, beyond, block: str, host: str, s, air,
            near: float, w: float, n_k: dict, roads_of, dem, step: float, pmin: float,
            gaps: dict) -> "tuple[list, dict]":
    """``(regs, levels)``: every unreachable piece within ``pad_frontage_m``
    of the passage level ``L`` minted beside it at its floor (step (b)),
    ``<block>/p<k>`` with a riser along the pads and every open edge but
    the roads leaving it; ``levels`` the minted ``{ref: (piece, block,
    y)}``."""
    from .low_level import LOW_KIND
    gs = [g for g in beyond if g.distance(L) <= near + w]
    if not gs:
        return regs, {}
    pads = valid_area(unary_union([r.polygon for r in regs if r.polygon is not None]))
    keep_off = valid_area(unary_union([pads.buffer(w, join_style=2),
                                       air.buffer(near, join_style=2)]))
    tmpl = next(r for r in regs if str(r.ref) == host)
    out = list(regs)
    levels: dict[str, tuple] = {}
    qs = nonempty_polygon_parts(valid_area(valid_area(unary_union(gs)).difference(keep_off)))
    smalls = [g for g in qs if g.area < pmin]
    for q in qs:
        if q.area < pmin:
            continue
        n_k[block] = n_k.get(block, 0) + 1
        ref = plane_ref(block, n_k[block])
        # the riser fills the keep-off up to a riser off the airside -- the lot
        # band left there stays welded to the apron at the apron's level,
        # never to the level (#1717: a lot between level and apron chains the
        # level up; a riser ON the apron's rim pulled two rim vertices 0.09 m,
        # MEASURED KIAH replay) -- with the slivers of the pieces beside it
        S = valid_area(unary_union([q.buffer(near + 0.5 * w, join_style=2),
                                    *(g for g in smalls if g.distance(q) <= near + w)])
                       .difference(q).difference(pads).difference(air.buffer(w, join_style=2)))
        gaps[ref + STRIP_SUFFIX] = roads_of(q)
        out.append(_dc.replace(tmpl, ref=ref, polygon=q))
        out.extend(_dc.replace(tmpl, ref=ref + STRIP_SUFFIX, polygon=g)
                   for g in nonempty_polygon_parts(S))
        pads = unary_union([pads, q.buffer(w, join_style=2)])
        reg.landings[ref] = {**reg.landings[host], "area_m2": round(q.area, 1),
                             "ground_z": _ground(q, dem, 2.0), "piece_of": host,
                             "kind": LOW_KIND, "y_hi": -step}
        levels[ref] = (q, block, -s.depth)
    return out, levels


def _pad_of(F, by_ref: dict, reg: Registries) -> "str | None":
    """The pad region ref holding most of the footprint ``F`` (a held block
    or a pad of its own), or ``None``."""
    best, area = None, 0.0
    for ref, rs in by_ref.items():
        if "/" in ref or "#" in ref:
            continue
        a = sum(r.polygon.intersection(F).area for r in rs)
        if a > area:
            best, area = ref, a
    return best if best is not None and area >= 0.5 * F.area else None


def _front_block(q, polys: dict, held: dict, reach: float) -> "str | None":
    """The held block the level ``q`` fronts: of the blocks whose datum the
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
    median of their own stated floors: the riser strip between two of them
    then stands flat between one floor, never a step inside it (its refs
    are kept: re-reffing strip pieces into the level moved 4 riser-top
    vertices 6.3-7.6 m at the strips' junctions, MEASURED LFPG replay).
    MEASURED LFPG T2
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
        notes.append(f"{'+'.join(members)} y {y:+.2f} (was {sorted(ys)})")
    if not notes:
        return regs
    counts["level_regions"] = len(notes)
    counts["level_region_list"] = "; ".join(notes)
    return regs


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


def _run_out(regs: list, reg: Registries, levels: dict, gaps: dict, air, airport, law,
             grid: float, counts: dict) -> list:
    """``regs`` with the run-outs of the roads leaving ``levels`` minted into
    ``reg.landing_runouts`` (``cut_runout.cut_runouts`` roads) and each
    level's riser strip opened ONLY where a run-out leaves through it: the
    exits are read with every road crossing (``gaps``: strip ref -> the
    carriageways over it) open, and a crossing no run-out takes stays a
    riser (MEASURED KIAH replay: the strips opened at every crossing left
    the lot torn 3.9 m between the level and Terminal D's rim, within_shape
    112 -> 435)."""
    from .cut_runout import cut_runouts
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))

    def opened(regs_, cuts):
        out = []
        for r in regs_:
            g = cuts.get(str(r.ref))
            if g is None or g.is_empty or r.polygon is None:
                out.append(r)
                continue
            out.extend(_dc.replace(r, polygon=q) for q in
                       nonempty_polygon_parts(valid_area(r.polygon.difference(g)))
                       if q.area >= 1.0)
        return out
    gaps = {k: g for k, g in gaps.items() if g is not None and not g.is_empty}
    # what takes an end is every OTHER pad and the airside: the region's own
    # riser strips are the step its run-outs replace through the gaps --
    # read as pads, the pieces' 3.5 m strips two risers out closed every
    # 8 m carriageway gap between them (spec §17, round 5)
    own = {r + STRIP_SUFFIX for r in levels}
    named = [(str(r.ref), r.polygon) for r in opened(regs, gaps)
             if r.polygon is not None and str(r.ref) not in own] + [("airside", air)]
    taken = valid_area(unary_union([q for _r, q in named]))
    got = cut_runouts(levels, reg.held, airport, law, taken, grid, counts, roads=True,
                      named=named)
    if not got:
        return regs                      # no run-out: every riser stays closed
    reg.landing_runouts.update(got)
    lanes = valid_area(unary_union([q for rec in got.values() for q in rec["polys"]]))
    near = lanes.buffer(3.0 * w, join_style=2)
    return opened(regs, {k: valid_area(g.intersection(near)) for k, g in gaps.items()})
