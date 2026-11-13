"""THE STOREY PAD (#2062, owner RULINGS 2026-11-13w: "split level buildings
... are essentially identical to the terrain shell objects ... seated so no
open sides are visible ... and all their wall bottoms are on terrain"; spec
``docs/specs/2062-storey-shell-spec.md`` §1, §3 R1, Amendment A1).

A split-level building (``airport/split_level``) stands on ONE held,
non-conforming ``building`` pad covering its plan, with one rigid level per
storey: the BLOCK (the level the airside meets) is the pad's own face, at
the pad's datum ``D``; every other level ``k`` is ``<pad>/p<k>`` in
``Registries.landings``, held at ``z = D + y_k`` (``constraints/platform.
landing_rows``), with its riser ``<pad>/p<k>#strip`` -- the grammar of the
unit pad's lower and upper levels (``planar/low_level``); no new row, no
new role.  The ground at every run of the building's outline is then the
building's zero plus that run's foot: no open side, no wall in the air.

THE PAD.  Its ref is the building cell under the plan with the most of it;
its polygon the shell's plan with the rest of that cell, less the runway
family, the structures, every other pad and every pit already cut; every
other cell is cut flush at it by the one knife (``planar/cell_knife``).
Each level's region is ``SplitLevel.level_plans[k]`` on the pad; a piece of
the pad off the plan takes a level as an unwitnessed remainder does (spec
A1 (1) (c), ``split_level.take_remainder``).

THE BACK CUT AND ITS KERB (spec A2 (3); owner RULINGS 2026-11-13w "all
their wall bottoms are on terrain", 2026-11-10a (2)).  Outside each
groundside run standing at the shell's LOWEST level, the band
``split_level_back_cut_m`` deep (chained as the pit's back cut,
``split_level_pit.back_band``) is cut down to the block's level: it is part
of the pad.  It yields -- clipped, never refused -- to the runway family,
the structures, other pads and pits, the airside pavement and the mapped
road faces (a road keeps its profile).  Along its outer edge (along the run
where it clipped to nothing) a band one riser wide inside the pad is the
KERB ``<pad>#kerb#strip``: the declared wall between the cut and the higher
lot (``airport/riser_wall`` reads its record from the pad's held record),
never within the airside pavement's riser width, never over an upper level.
The lot never shares a vertex with a block-level face on such a run.

SCOPE (spec A2 (4)): a shell with two counted levels or more whose block is
its LOWEST level -- (i) the airside meets the lowest level
(``air_level == 0``), or (ii) no run faces the airside and half the lowest
level's run length faces a structure floor (a tunnel ramp, an entrance
bank, a channel or basin floor: the block follows that floor).  Scope (ii)
is read and NAMED but HELD (:data:`FLOOR_HELD`): the follower is a new row
family.  Upper-block
shells stay on the pit (``planar/split_level_pit``) until R3, and so does a
scope-(ii) shell the pit already built.  Refused, by name, as the pit
refuses: a plan overlapping the runway family or a structure, a mapped
road running under it, a plan another pit took; and a shell with no
building cell under it.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from ..airport.split_level import (
    SplitLevel,
    corner_cut,
    read_split_levels,
    run_faces,
    take_remainder,
)
from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area
from ..law.tables import frontage_roles
from ..model.planar import plane_ref
from ..model.storey_shell import StoreyRun, StoreyShell
from .basin_geometry import _rim
from .cell_knife import knife_cells
from .fill_riser import _lines, riser_width
from .split_level_pit import _largest, _road_under, _roads, back_band

__all__ = ["read_storey_shells", "pit_skip", "storey_pads", "shell_levels"]


def read_storey_shells(airport, cells, polys, law, objects, cache
                       ) -> tuple[list[SplitLevel], list[str]]:
    """The split-level buildings of ``objects`` that may stand on storey
    pads (module docstring, SCOPE: (i) now; (ii) once the structures are
    cut, :func:`storey_pads`), and one note each."""
    fr = frontage_roles(law)
    air = unary_union([p for p, c in zip(polys, cells, strict=True) if c.role in fr]).buffer(0)
    dem_z = getattr(getattr(airport, "dem", None), "z", None)
    sls, _notes = read_split_levels(objects, cache, law, dem_z,
                                    None if air.is_empty else prep(air))
    out = [sl for sl in sls if sl.air_level in (0, None) and len(sl.levels) >= 2]
    return out, [f"{sl.id} {sl.paths[0].rsplit('/', 1)[-1]}: levels "
                 + "/".join(f"{y:+.2f}" for y in sl.levels)
                 + (f", block {sl.air_level}" if sl.air_level is not None else ", no airside")
                 + f", {len(sl.minor)} minor run(s)" for sl in out]


def pit_skip(shells: _t.Sequence[SplitLevel]) -> frozenset:
    """The record ids no pit is cut under: scope (i) (module docstring)."""
    return frozenset(sl.id for sl in shells if sl.air_level == 0)


def storey_pads(airport, cells, polys, law, shells: _t.Sequence[SplitLevel],
                taken: _t.Sequence[Polygon], runway_roles: _t.Collection[str],
                pitted: _t.AbstractSet[str] = frozenset()
                ) -> tuple[list, list[StoreyShell], list[str], list[str]]:
    """``(cells, records, notes, refusals)``: the classification's cells
    with every shell's pad cut in (module docstring).  ``pitted``: the
    placement ids a split-level pit was built under."""
    if not shells:
        return list(cells), [], [], []
    bp = law.tables.structures.building_pad
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    probe = float(bp.split_level_probe_m)
    reach = float(getattr(bp, "split_level_back_cut_m", 0.0) or 0.0)
    w = riser_width(law, grid)
    hard = [p for p, c in zip(polys, cells, strict=True)
            if c.role in runway_roles or c.kind == "structure"]
    blocked = unary_union(hard) if hard else None
    floors = unary_union([p for p, c in zip(polys, cells, strict=True)
                          if c.kind == "structure" and "wall" not in str(c.role)])
    floors = None if floors.is_empty else prep(floors)
    pits = unary_union(list(taken)) if taken else None
    roads = _roads(airport)
    road_faces = unary_union([p for p, c in zip(polys, cells, strict=True)
                              if "road" in str(c.role)])
    fr = frontage_roles(law)
    air_g = unary_union([p for p, c in zip(polys, cells, strict=True)
                         if c.role in fr]).buffer(0)
    air = None if air_g.is_empty else prep(air_g)
    # the GROUNDSIDE VALUE FACES a kerb may border (no void, no airside, no
    # runway family, no structure, no building)
    ground = unary_union([p for p, c in zip(polys, cells, strict=True)
                          if c.role not in runway_roles and c.kind != "structure"
                          and c.role not in fr and c.role != "building"])
    pads: dict[int, Polygon] = {}
    recs: list[StoreyShell] = []
    notes: list[str] = []
    refused: list[str] = []
    for sl in shells:
        name = sl.paths[0].rsplit("/", 1)[-1]
        scope = "airside" if sl.air_level == 0 else "floor"
        plan = sl.pit_plan
        why = "" if scope == "airside" else (_floor_scope(sl, floors, pitted) or FLOOR_HELD)
        why = why or _refusal(plan, blocked, roads, grid)
        under = [(i, p.intersection(plan).area)
                 for i, (p, c) in enumerate(zip(polys, cells, strict=True))
                 if c.role == "building" and i not in pads and p.intersects(plan)]
        under = [(i, a) for i, a in under if a > 0.0]
        if not why and not under:
            why = "no building cell under the shell (no pad is minted)"
        if why:
            refused.append(f"{sl.id} {name}: {why}")
            continue
        i0 = max(under, key=lambda q: (q[1], -q[0]))[0]
        others = [p for j, (p, c) in enumerate(zip(polys, cells, strict=True))
                  if c.role == "building" and j != i0 and p.intersects(plan.buffer(reach + grid))]
        keep_off = [g for g in (blocked, pits, *pads.values()) if g is not None] + others
        yields = {"structure": blocked, "pit": pits,
                  "pad": unary_union([*pads.values(), *others]) if pads or others else None,
                  "airside": None if air_g.is_empty else air_g,
                  "road": None if road_faces.is_empty else road_faces}
        T, cuts = _back_cut(sl, plan, reach, yields, air, grid)
        P = valid_area(unary_union([plan, polys[i0], T]))
        if keep_off:
            P = valid_area(P.difference(unary_union(keep_off)))
        P = _largest(P)
        P = None if P is None else _rim(P, 0.0, grid)
        if P is None or P.intersection(plan).area < 0.5 * plan.area:
            refused.append(f"{sl.id} {name}: the shell's plan is taken by another pit or pad")
            continue
        pads[i0] = P
        rec = _record(sl, str(cells[i0].ref), P, probe, air, valid_area(T.intersection(P)),
                      cuts, scope)
        rec = _with_kerb(rec, P, plan, w, grid, ground, air_g, keep_off, law)
        recs.append(rec)
        notes.append(f"{sl.id} {name}: pad {rec.pad_ref} {P.area:.0f} m2 (plan "
                     f"{plan.area:.0f} m2, scope {scope}), levels "
                     + ", ".join(f"{r} y {rec.y_of(k):+.2f} {_area(rec.level_regions[k]):.0f} m2"
                                 for k, r in enumerate(rec.level_refs))
                     + f"; back cut {_area(rec.back_cut):.0f} m2, kerb {_area(rec.kerb):.0f} m2 "
                     f"({len(rec.kerbs)} wall(s))")
    if not pads:
        return list(cells), [], notes, refused
    knife = unary_union(list(pads.values()))
    rest = [(c, p) for i, (c, p) in enumerate(zip(cells, polys, strict=True))
            if i not in pads]
    new = [_dc.replace(cells[i], ring=tuple(P.exterior.coords)[:-1],
                       holes=tuple(tuple(h.coords)[:-1] for h in P.interiors),
                       evidence=dict(cells[i].evidence, storey_shell=1.0))
           for i, P in sorted(pads.items())]
    out, n_cut = knife_cells([c for c, _p in rest], [p for _c, p in rest], knife, law,
                             runway_roles, cut_pads=False, mark="storey_cut", new_cells=new)
    notes.append(f"{len(recs)} storey pad(s), {n_cut} cell(s) cut at them")
    return out, recs, notes, refused


#: SCOPE (ii) IS HELD (#2062 A2 (6), K0 measured on the KLAX capture): a
#: block with no airside contact has no stage-1 datum column
#: (``model.platform.datum_vertices``), so its upper level's landing rows
#: hold nothing, and no row makes the block follow the structure floor one
#: way -- a new row family, an owner decision; such a shell keeps today's
#: path until one exists
FLOOR_HELD = ("scope (ii): its lowest level stands on a structure floor, but no row "
              "makes the block follow that floor (no floor-led datum; #2062 A2 (6)) -- "
              "held, today's path")


def _floor_scope(sl: SplitLevel, floors, pitted: _t.AbstractSet[str]) -> str:
    """Why a shell with no airside contact is NOT laid on a storey pad
    (scope (ii), module docstring), or ``""``."""
    if not pitted.isdisjoint(sl.member_ids) and sl.part == 0:
        return "no airside contact; its split-level pit was built (stays on the pit)"
    low = [r for (r, _f), k, i in zip(sl.runs, sl.run_levels, range(len(sl.runs)), strict=True)
           if k == 0 and i not in sl.minor]
    total = sum(r.length for r in low)
    on = sum(r.length for r in low if floors is not None and run_faces(floors, r))
    if total <= 0.0 or on < 0.5 * total:
        return (f"no airside contact and {on:.1f} of {total:.1f} m of its lowest level on a "
                "structure floor (an upper-block shell: the pit until R3)")
    return ""


def _back_cut(sl: SplitLevel, plan: Polygon, reach: float, yields: dict, air, grid: float
              ) -> tuple[Polygon, dict[int, tuple[float, tuple[str, ...]]]]:
    """``(T, {run: (back cut m, clipped by)})``: the back cut outside the
    shell's groundside runs at its lowest level (module docstring), the
    part touching the plan."""
    runs = {i: r for i, ((r, f), k) in enumerate(zip(sl.runs, sl.run_levels, strict=True))
            if k == 0 and f is not None and not (air is not None and run_faces(air, r))}
    if reach <= 0.0 or not runs:
        return Polygon(), {}
    band = valid_area(back_band(list(runs.values()), reach).difference(plan))
    # ... never in front of a run at another level: where the fronts of two
    # outline-adjacent runs overlap (a reflex corner), the bisector splits
    # them (``split_level.corner_cut``, the level strips' rule outside)
    xy = [tuple(r.coords) for r, _f in sl.runs]
    fronts = corner_cut([r.buffer(reach, single_sided=True, cap_style="flat") for r, _f in sl.runs],
                        xy, [_right(c) for c in xy], sl.run_levels)
    upper = [g for g, k in zip(fronts, sl.run_levels, strict=True) if k not in (None, 0)]
    if upper:
        band = valid_area(band.difference(unary_union(upper)))
    stop = [g for g in yields.values() if g is not None and not g.is_empty]
    T = valid_area(band.difference(unary_union(stop))) if stop else band
    near = plan.buffer(grid)
    T = valid_area(unary_union([q for q in nonempty_polygon_parts(T) if q.intersects(near)]))
    cuts = {}
    for i, r in runs.items():
        side = r.buffer(reach, single_sided=True, cap_style="flat").difference(plan)
        L = max(r.length, 1e-9)
        by = tuple(k for k, g in yields.items() if g is not None and not g.is_empty
                   and side.intersection(g).area > grid * grid)
        cuts[i] = (round(T.intersection(side).area / L, 2), by)
    return T, cuts


def _right(c) -> tuple[float, float]:
    """The unit normal on the RIGHT of the run ``c`` (into its building)."""
    (x0, y0), (x1, y1) = c[0], c[-1]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    return ((y1 - y0) / L, -(x1 - x0) / L)


def _with_kerb(rec: StoreyShell, P: Polygon, plan: Polygon, w: float, grid: float,
               ground, air, keep_off, law) -> StoreyShell:
    """``rec`` with its KERB (module docstring): the band ``w`` inside the
    pad along the back cut's outer edge (along the run where the cut
    clipped to nothing) where it borders a groundside value face
    (``ground``), off the airside's riser width, the other pads and pits
    and every upper level; and its wall records."""
    eps = 0.5 * grid
    T = rec.back_cut
    lines = [P.exterior.intersection(T.buffer(eps)).difference(plan.buffer(eps))] \
        if T is not None and not T.is_empty else []
    # ... and along every back-cut run where the cut clipped to nothing
    # there (the run itself is then the pad's edge)
    lines += [P.exterior.intersection(LineString(r.xy).buffer(eps)) for r in rec.runs
              if r.back_cut_m is not None]
    edge = unary_union(_lines(unary_union(lines))) if lines else None
    if edge is None or edge.is_empty or ground.is_empty:
        return rec
    edge = unary_union(_lines(edge.intersection(ground.buffer(eps, join_style=2))))
    off = [g for g in (air, *keep_off) if g is not None and not g.is_empty]
    if off:
        edge = edge.difference(unary_union(off).buffer(w + eps, join_style=2))
    if edge.is_empty:
        return rec
    upper = unary_union([g for k, g in enumerate(rec.level_regions) if k != rec.block])
    R = valid_area(P.intersection(edge.buffer(w, cap_style="flat", join_style="mitre")))
    if not upper.is_empty:
        R = valid_area(R.difference(upper))
    pieces = [q for q in nonempty_polygon_parts(R) if q.area >= max(grid * grid, 1.0)]
    if not pieces:
        return rec
    h = (max(rec.levels) - rec.levels[rec.block]
         + float(law.tables.emit.cockpit.visual_m))
    kerbs = tuple({"ring": [tuple(c) for c in q.exterior.coords],
                   "upper": [[tuple(c) for c in ln.coords]
                             for ln in _lines(edge.intersection(q.buffer(eps)))],
                   "height_m": round(h, 3)} for q in pieces)
    return _dc.replace(rec, kerb=valid_area(unary_union(pieces)), kerbs=kerbs)


def _refusal(plan: Polygon, blocked, roads, grid: float) -> str:
    """The pit's refusals (``planar/split_level_pit``), on the plan (which
    may TOUCH a structure: a scope-(ii) shell stands on its floor)."""
    if blocked is not None and plan.buffer(-grid).intersects(blocked):
        return "the shell's plan meets the runway family or a structure"
    if _road_under(plan, roads, grid):
        return ("a mapped road runs under the shell's plan (a tunnel way inside it) — "
                "a road's underpass, not a building cut into a slope")
    return ""


def _area(g) -> float:
    return sum(q.area for q in nonempty_polygon_parts(g))


def _record(sl: SplitLevel, pad_ref: str, P: Polygon, probe: float, air, T: Polygon,
            cuts: _t.Mapping[int, tuple], scope: str) -> StoreyShell:
    """The shell's record on its pad ``P``: each level's region of the pad
    (its plan there, the back cut ``T`` the block's; the rest of the pad
    by :func:`take_remainder`)."""
    regions = [valid_area(g.intersection(P)) for g in sl.level_plans]
    block = int(sl.air_level or 0)
    if not T.is_empty:
        regions = [valid_area(g.difference(T)) for g in regions]
        regions[block] = valid_area(unary_union([regions[block], T]))
    regions = take_remainder(regions, valid_area(P.difference(unary_union(regions))), probe)
    refs, j = [], 0
    for k in range(len(sl.levels)):
        if k == block:
            refs.append(pad_ref)
        else:
            j += 1
            refs.append(plane_ref(pad_ref, j))
    minor = set(sl.minor)
    lv = sl.run_levels or (None,) * len(sl.runs)
    runs = tuple(StoreyRun(tuple(tuple(map(float, q)) for q in r.coords), f, k, i in minor,
                           air is not None and run_faces(air, r),
                           *(cuts[i] if i in cuts else (None, ())))
                 for i, ((r, f), k) in enumerate(zip(sl.runs, lv, strict=True)))
    plan = sl.pit_plan
    return StoreyShell(sl.id, tuple(sl.member_ids), tuple(sl.paths), pad_ref,
                       tuple(sl.levels), block, tuple(refs), tuple(regions), runs,
                       tuple(tuple(map(float, q)) for q in plan.exterior.coords)[:-1],
                       tuple(tuple(map(float, q)) for q in P.exterior.coords)[:-1],
                       tuple(map(float, sl.anchor_xy)), back_cut=T, scope=scope)


def shell_levels(P, shell: StoreyShell, air, law, grid: float, others=None
                 ) -> tuple[_t.Any, list[tuple[str, _t.Any, _t.Any, dict]]]:
    """``(block, [(level ref, level, riser strip, landing record)])``: the
    held pad region ``P`` (its kerb carved out already) split at the
    shell's levels (module docstring), the levels highest first, each kept
    a riser's width off the airside ``air`` (the airside meets the block)
    and off the other pads ``others`` (as ``low_level.plan_up``), carving
    its riser out of the levels under it.  A level piece the riser could
    not stand beside (under ``pad_frontage_m x 2 x riser``) stays in the
    block."""
    from ..law.tables import design as design_law
    from .low_level import LOW_KIND, UP_KIND
    near = float(design_law(law).pad_frontage_m)
    w = riser_width(law, grid)
    off = [g.buffer(w, join_style=2) for g in (air, others) if g is not None and not g.is_empty]
    off = unary_union(off) if off else None
    taken = Polygon()
    levels = []
    order = sorted((k for k in range(len(shell.levels)) if k != shell.block),
                   key=lambda k: -shell.levels[k])
    for k in order:
        U = valid_area(valid_area(shell.level_regions[k]).intersection(P).difference(taken))
        if off is not None:
            U = valid_area(U.difference(off))
        keep = [q for q in nonempty_polygon_parts(U) if q.area >= near * 2.0 * w]
        if not keep:
            continue
        U = valid_area(unary_union(keep))
        S = valid_area(P.intersection(U.buffer(w, join_style=2)).difference(U).difference(taken))
        taken = valid_area(unary_union([taken, U, S]))
        y = round(shell.y_of(k), 3)
        rec = {"y": y, "area_m2": round(U.area, 1), "shell": shell.id}
        if y < 0.0:
            rec.update(y_lo=y, y_hi=y, ground_z=None)
        rec["kind"] = UP_KIND if y > 0.0 else LOW_KIND
        levels.append((shell.level_refs[k], U, S, rec))
    return valid_area(P.difference(taken)), levels

