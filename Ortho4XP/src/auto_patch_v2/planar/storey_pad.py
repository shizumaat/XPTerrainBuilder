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

R1 SCOPE (spec A1 (3)): only shells whose block is their LOWEST level
(``air_level == 0``) with two levels or more; the rest stay on the pit
(``planar/split_level_pit``) until R3.  Refused, by name, as the pit
refuses: a plan over the runway family or a structure, a mapped road
running under it, a plan another pit took; and (R1) a shell with no
building cell under it.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from ..airport.split_level import (SplitLevel, read_split_levels, run_faces_airside,
                                   take_remainder)
from ..geom.parts import nonempty_polygon_parts, polygon_parts_with_area
from ..geom.valid_area import valid_area
from ..law.tables import frontage_roles
from ..model.planar import plane_ref
from ..model.storey_shell import StoreyRun, StoreyShell
from .basin_geometry import _rim
from .cell_knife import knife_cells
from .split_level_pit import _road_under, _roads

__all__ = ["read_storey_shells", "storey_pads", "shell_levels"]


def read_storey_shells(airport, cells, polys, law, objects, cache
                       ) -> tuple[list[SplitLevel], list[str]]:
    """The split-level buildings of ``objects`` this round lays on storey
    pads (module docstring, R1 SCOPE), and one note each."""
    fr = frontage_roles(law)
    air = unary_union([p for p, c in zip(polys, cells, strict=True) if c.role in fr]).buffer(0)
    dem_z = getattr(getattr(airport, "dem", None), "z", None)
    sls, _notes = read_split_levels(objects, cache, law, dem_z,
                                    None if air.is_empty else prep(air))
    out = [sl for sl in sls if sl.air_level == 0 and len(sl.levels) >= 2]
    return out, [f"{sl.id} {sl.paths[0].rsplit('/', 1)[-1]}: levels "
                 + "/".join(f"{y:+.2f}" for y in sl.levels)
                 + f", block {sl.air_level}, {len(sl.minor)} minor run(s): storey pad"
                 for sl in out]


def storey_pads(airport, cells, polys, law, shells: _t.Sequence[SplitLevel],
                taken: _t.Sequence[Polygon], runway_roles: _t.Collection[str]
                ) -> tuple[list, list[StoreyShell], list[str], list[str]]:
    """``(cells, records, notes, refusals)``: the classification's cells
    with every shell's pad cut in (module docstring)."""
    if not shells:
        return list(cells), [], [], []
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    probe = float(law.tables.structures.building_pad.split_level_probe_m)
    hard = [p for p, c in zip(polys, cells, strict=True)
            if c.role in runway_roles or c.kind == "structure"]
    blocked = unary_union(hard) if hard else None
    pits = unary_union(list(taken)) if taken else None
    roads = _roads(airport)
    fr = frontage_roles(law)
    air = unary_union([p for p, c in zip(polys, cells, strict=True) if c.role in fr]).buffer(0)
    air = None if air.is_empty else prep(air)
    pads: dict[int, Polygon] = {}
    recs: list[StoreyShell] = []
    notes: list[str] = []
    refused: list[str] = []
    for sl in shells:
        name = sl.paths[0].rsplit("/", 1)[-1]
        plan = sl.pit_plan
        why = _refusal(plan, blocked, roads, grid)
        under = [(i, p.intersection(plan).area) for i, (p, c) in enumerate(zip(polys, cells))
                 if c.role == "building" and i not in pads and p.intersects(plan)]
        under = [(i, a) for i, a in under if a > 0.0]
        if not why and not under:
            why = "no building cell under the shell (R1 mints no pad)"
        if why:
            refused.append(f"{sl.id} {name}: {why}")
            continue
        i0 = max(under, key=lambda q: (q[1], -q[0]))[0]
        keep_off = [g for g in (blocked, pits, *pads.values()) if g is not None]
        keep_off += [p for j, (p, c) in enumerate(zip(polys, cells))
                     if c.role == "building" and j != i0 and p.intersects(plan.buffer(grid))]
        P = valid_area(unary_union([plan, polys[i0]]))
        if keep_off:
            P = valid_area(P.difference(unary_union(keep_off)))
        P = _largest(P)
        P = None if P is None else _rim(P, 0.0, grid)
        if P is None or P.intersection(plan).area < 0.5 * plan.area:
            refused.append(f"{sl.id} {name}: the shell's plan is taken by another pit or pad")
            continue
        pads[i0] = P
        rec = _record(sl, str(cells[i0].ref), P, probe, air)
        recs.append(rec)
        notes.append(f"{sl.id} {name}: pad {rec.pad_ref} {P.area:.0f} m2 (plan "
                     f"{plan.area:.0f} m2), levels "
                     + ", ".join(f"{r} y {rec.y_of(k):+.2f} "
                                 f"{sum(g.area for g in nonempty_polygon_parts(rec.level_regions[k])):.0f} m2"
                                 for k, r in enumerate(rec.level_refs)))
    if not pads:
        return list(cells), [], notes, refused
    knife = unary_union(list(pads.values()))
    rest = [(c, p) for i, (c, p) in enumerate(zip(cells, polys)) if i not in pads]
    new = [_dc.replace(cells[i], ring=tuple(P.exterior.coords)[:-1],
                       holes=tuple(tuple(h.coords)[:-1] for h in P.interiors),
                       evidence=dict(cells[i].evidence, storey_shell=1.0))
           for i, P in sorted(pads.items())]
    out, n_cut = knife_cells([c for c, _p in rest], [p for _c, p in rest], knife, law,
                             runway_roles, cut_pads=False, mark="storey_cut", new_cells=new)
    notes.append(f"{len(recs)} storey pad(s), {n_cut} cell(s) cut at them")
    return out, recs, notes, refused


def _refusal(plan: Polygon, blocked, roads, grid: float) -> str:
    """The pit's refusals (``planar/split_level_pit``), on the plan."""
    if blocked is not None and plan.intersects(blocked):
        return "the shell's plan meets the runway family or a structure"
    if _road_under(plan, roads, grid):
        return ("a mapped road runs under the shell's plan (a tunnel way inside it) — "
                "a road's underpass, not a building cut into a slope")
    return ""


def _largest(geom) -> "Polygon | None":
    parts = polygon_parts_with_area(geom)
    return max(parts, key=lambda g: g.area) if parts else None


def _record(sl: SplitLevel, pad_ref: str, P: Polygon, probe: float, air) -> StoreyShell:
    """The shell's record on its pad ``P``: each level's region of the pad
    (its plan there; the pad off the plan by :func:`take_remainder`)."""
    regions = [valid_area(g.intersection(P)) for g in sl.level_plans]
    regions = take_remainder(regions, valid_area(P.difference(unary_union(regions))), probe)
    block = int(sl.air_level or 0)
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
                           air is not None and run_faces_airside(air, r))
                 for i, ((r, f), k) in enumerate(zip(sl.runs, lv, strict=True)))
    plan = sl.pit_plan
    return StoreyShell(sl.id, tuple(sl.member_ids), tuple(sl.paths), pad_ref, tuple(sl.levels), block,
                       tuple(refs), tuple(regions), runs,
                       tuple(tuple(map(float, q)) for q in plan.exterior.coords)[:-1],
                       tuple(tuple(map(float, q)) for q in P.exterior.coords)[:-1],
                       tuple(map(float, sl.anchor_xy)))


def shell_levels(P, shell: StoreyShell, air, law, grid: float
                 ) -> tuple[_t.Any, list[tuple[str, _t.Any, _t.Any, dict]]]:
    """``(block, [(level ref, level, riser strip, landing record)])``: the
    held pad region ``P`` split at the shell's levels (module docstring),
    the levels highest first, each kept a riser's width off the airside
    ``air`` (the airside meets the block) and carving its riser out of the
    levels under it.  A level piece the riser could not stand beside
    (under ``pad_frontage_m x 2 x riser``) stays in the block."""
    from ..law.tables import design as design_law
    from .low_level import LOW_KIND, UP_KIND
    near = float(design_law(law).pad_frontage_m)
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    off = air.buffer(w, join_style=2) if air is not None and not air.is_empty else None
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

