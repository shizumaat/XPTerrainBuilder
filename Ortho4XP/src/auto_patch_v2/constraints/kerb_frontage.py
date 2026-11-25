"""THE LANDSIDE MEETS THE BUILDING AT KERB LEVEL (#2279 step 2; spec
``docs/specs/2279-kerb-frontage-spec.md``; owner, #2279: "the terminal's
landside is one level higher; the front access road and parking must be
graded to meet the bottom of the building and its kerbs").

A unit's LANDSIDE lot (``classify/storey_edge``) is cut back from the
storey's PLAN, and its kerb record sits on the unit block's ``held`` entry
(``planar/kerb_frontage``, :data:`model.registries.LANDSIDE_KERB`): the
lot, the plan rings, the storey's rise ``y`` over the unit's floor.

THE RULE (:func:`kerb_frontage_rows`).  Every GROUNDSIDE PAVEMENT vertex
(``constraints/groundside.groundside_face_roles``: the lot and the front
access road beside it alike — the owner's "front access road and parking")
outside the plan and within ``[design]
pad_frontage_m`` of it — the landside's FRONTAGE on the building, the
radius §20 and §28 read the pad relation by — that is no stage-1
(airside) vertex and no pad's, and whose own ground confirms the storey as
§27 read it (half the rise over the airside's ground), takes ONE one-way
row ``z_v - z_D = y``, ``D`` the
block's DATUM COLUMN (``model.platform.datum_vertices``, the landing rows'
column): the kerb deck's bottom.  Stage 2's row, ``D`` a constant there:
the kerb follows the unit, the unit and the airside never follow the kerb.
Priced as §28's senior frontage (``pad_flat``): the lot grades away from
the kerb under its own lot cap (5 %, RULINGS 2026-11-25e) toward its own
ground — the lot law's rows, none minted here.

THE WALL (:func:`kerb_wall_exempt`, a post-pass after the 5 % ceiling and
the fallback road cap).
Across the cut-back the plan's edge IS the building's wall (RULINGS
2026-11-25b (5): pavements touching, the step is a wall): every row
spanning a kerb vertex and a vertex at the plan (inside it or within the
groundside cut-back of its edge) or any airside or pad vertex — the
apron-edge ramp, §28 to a pad under the storey, a
road stub's within-shape pair — is withdrawn, so neither it nor its
ceiling twin ties the kerb to the floor a storey below; and a road's §37
ramp rows on a kerb vertex (its own-ground target and ceiling) give way
to the kerb row, as on a landing's run-out."""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from shapely import points
from shapely.ops import unary_union

from ..law import Law
from ..law.tables import design as design_law
from ..model.constraints import Linear, Row, Source
from ..model.map_memo import per_map
from ..model.planar import PlanarMap
from ..model.registries import LANDSIDE_KERB

__all__ = ["GEN", "RULING", "STATS", "kerb_frontage_rows", "kerb_vertices",
           "kerb_wall_exempt", "wall_line"]

GEN = "kerb_frontage"
#: the row's ruling HEAD: in ``[design] pad_flat_rulings`` (§28's senior
#: price) and ``one_way_rulings`` (the kerb follows the block)
RULING = "structures.building_pad landside_kerb"
#: the generator's report (``kerb_frontage.<key>``)
STATS: dict[str, _t.Any] = {}
_MEMO: dict[int, tuple[_t.Any, dict]] = {}


def _records(planar: PlanarMap) -> list[tuple[str, dict]]:
    held = getattr(getattr(planar, "registries", None), "held", None) or {}
    return [(b, rec) for b, h in sorted(held.items()) for rec in h.get(LANDSIDE_KERB, ())]


def kerb_vertices(planar: PlanarMap, law: Law
                  ) -> tuple[dict[int, tuple[str, float]], set[int]]:
    """``({kerb vertex: (block, y)}, the wall vertices)`` (module
    docstring), read once per map."""
    memo = per_map(_MEMO, planar)
    if "kerb" in memo:
        return memo["kerb"]
    recs = _records(planar)
    out: tuple[dict, set] = ({}, set())
    if recs:
        out = _derive(planar, law, recs)
    memo["kerb"] = out
    return out


def wall_line(planar: PlanarMap, law: Law):
    """THE WALL LINE the kerb meets (``pipeline/kerb_publication``): the
    boundary of the plan grown by the groundside cut-back, joined with the
    pad and airside faces carrying a wall vertex, kept within the frontage
    radius of a kerb vertex — or ``None``."""
    memo = per_map(_MEMO, planar)
    if "line" in memo:
        return memo["line"]
    kerb, wall = kerb_vertices(planar, law)
    line = None
    if kerb:
        reach = float(design_law(law).pad_frontage_m)
        back = float(law.tables.zones.adjacent_ground.groundside_cutback_m)
        near = unary_union(points([planar.vertices[v].xy for v in kerb]).tolist())
        near = near.buffer(reach + back)
        polys = [rec["plan"].buffer(back) for _b, rec in _records(planar)
                 if rec.get("plan") is not None]
        from .groundside import groundside_face_roles
        floor = _pavement(law) - set(groundside_face_roles(law))
        for f in planar.faces.values():
            if f.role in floor and _verts(planar, f) & wall:
                ring = [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]
                if len(ring) >= 3:
                    p = shapely.Polygon(ring)
                    if p.is_valid and p.intersects(near):
                        polys.append(p)
        W = unary_union(polys)
        line = W.boundary.intersection(near) if not W.is_empty else None
    memo["line"] = line
    return line


def _verts(planar: PlanarMap, f) -> set[int]:
    return {v for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}


def _derive(planar: PlanarMap, law: Law, recs) -> tuple[dict, set]:
    from ..model.platform import stage_air_vertices
    from .groundside import groundside_face_roles
    reach = float(design_law(law).pad_frontage_m)
    back = float(law.tables.zones.adjacent_ground.groundside_cutback_m)
    air = stage_air_vertices(planar, law)
    ground = set(groundside_face_roles(law))
    def verts(f) -> set[int]:
        return {v for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}
    # a vertex a pad (or any other non-groundside pavement) carries is that
    # face's, never the kerb's
    other = {v for f in planar.faces.values() if f.role not in ground
             and f.role in _pavement(law) for v in verts(f)}
    gfaces = [verts(f) for f in planar.faces.values() if f.role in ground]
    kerb: dict[int, tuple[str, float]] = {}
    plans = []
    landside: set[int] = set()
    for block, rec in recs:
        plan = rec["plan"]
        if plan is None or plan.is_empty:
            continue
        plans.append(plan)
        inner = plan.buffer(-back)
        # a groundside face reaching INTO the plan is the floor's side of the
        # wall (a floor piece no aircraft reaches, a road into the building):
        # its vertices are no kerb's (MEASURED PHLI: ``pav63#4#beyond1``
        # read half kerb, half floor, a 4 m step inside one face)
        allg = sorted(set().union(*gfaces)) if gfaces else []
        hit = (set(np.asarray(allg)[shapely.covers(inner, points(
            [planar.vertices[v].xy for v in allg]))].tolist())
            if allg and not inner.is_empty else set())
        out_faces, in_faces = [], []
        for vs in gfaces:
            (in_faces if vs & hit else out_faces).append(vs)
        inside = set().union(*in_faces) if in_faces else set()
        gv = sorted(set().union(*out_faces) - air - other - inside) if out_faces else []
        landside.update(gv)
        if not gv:
            continue
        y, air_z = float(rec["y"]), rec.get("air_z")
        # a unit's two-floor record reads its band along its landside FACE
        # (``planar/kerb_frontage._unit_records``; spec §1.4)
        face = rec.get("face")
        line = face if face is not None and not face.is_empty else plan
        d = shapely.distance(line, points([planar.vertices[v].xy for v in gv]))
        if line is not plan:
            d = np.where(shapely.covers(plan, points([planar.vertices[v].xy for v in gv])),
                         0.0, d)
        half = 0.0 if rec.get("lot") is None else 0.5
        for v, dv in zip(gv, d, strict=True):
            if 0.0 < dv <= reach and _confirms(planar.vertices[v].dem_z, air_z, y, half):
                kerb.setdefault(v, (block, y))
    wall: set[int] = set()
    if kerb and plans:
        # the plan side of the wall: inside the plan or within the
        # cut-back of its edge (the set-back the landside stands off by)
        P = unary_union(plans).buffer(back)
        x0, y0, x1, y1 = P.bounds
        # a landside vertex the kerb did not take (its ground has come down)
        # is the lot's own, never the wall's
        cand = [v for v, vx in planar.vertices.items() if v not in kerb and v not in landside
                and x0 <= vx.xy[0] <= x1 and y0 <= vx.xy[1] <= y1]
        if cand:
            inside = shapely.covers(P, points([planar.vertices[v].xy for v in cand]))
            wall = {v for v, k in zip(cand, inside, strict=True) if k}
        # and every airside or pad vertex: what the kerb meets there is the
        # building or its floor (MEASURED PHLI: a pad of the unit standing
        # past the storey's body held the kerb 4.1 m down by its rim strip)
        wall |= (air | other) - set(kerb)
    return kerb, wall


def _confirms(dem_z, air_z, y: float, half: float = 0.5) -> bool:
    """Whether a frontage vertex's own ground confirms the storey as §27
    read it for the whole lot (``classify/storey_edge.ground_confirms``):
    at least half the rise over the airside's ground, on the rise's side
    (a storey DOWN: at least half of it under -- RULINGS 2026-11-25g, both
    signs).  Where it does not the landside has come down (or up) to the
    floor's ground (a lot's end past the building) and the kerb is no
    level of it.

    ``half`` 0 (a unit's two-floor record, ``planar/kerb_frontage.
    _unit_records``): the record's verdict already read half the rise on
    the face's own ground (``unit_storey._verdict``); a band vertex need
    only stand on the rise's side of the airside ground.  The airport DEM
    is smoothed (``Ortho4XP/CLAUDE.md`` "DEM frame") and cannot show a
    wall's step at the wall: MEASURED LDSP, the frontage road's kerb
    vertices read 14.4-15.9 against the apron's 17.16 while the face's
    ground reads 11.41 (owner 25h addendum: the road in front stands at
    least a storey under the airside)."""
    if air_z is None:
        return True
    if dem_z is None:
        return False
    dz = float(dem_z) - float(air_z)
    return dz >= half * y if y >= 0.0 else dz <= half * y


def _pavement(law: Law) -> frozenset[str]:
    from ..law.tables import pavement_roles
    return frozenset(pavement_roles(law)) | {"building"}


def kerb_frontage_rows(planar: PlanarMap, law: Law, airport=None) -> list[Row]:
    """THE KERB ROWS (module docstring).  A generator."""
    STATS.clear()
    kerb, _wall = kerb_vertices(planar, law)
    if not kerb:
        return []
    from ..model.platform import datum_vertices
    held = datum_vertices(planar, law, fills=True)
    rows: list[Row] = []
    lots: dict[str, int] = {}
    no_datum: set[str] = set()
    for v, (block, y) in sorted(kerb.items()):
        dv = held.get(block)
        if dv is None or dv == v:
            no_datum.add(block)
            continue
        src = Source(GEN, RULING + " (#2279: the unit's landside meets it at the "
                     "kerb, its datum + the storey's rise)", (f"block:{block}",))
        rows.append(Linear(((v, 1.0), (dv, -1.0)), None, y, src, follows=(v,)))
        rows.append(Linear(((v, -1.0), (dv, 1.0)), None, -y, src, follows=(v,)))
        lots[block] = lots.get(block, 0) + 1
    STATS.update({"vertices": sum(lots.values()), "blocks": len(lots),
                  "blocks_no_datum": len(no_datum)})
    return rows


def _row_vertices(r: Row) -> tuple[int, ...]:
    terms = getattr(r, "terms", None)
    if terms is not None:
        return tuple(v for v, _c in terms)
    group = getattr(r, "group", None)
    if group is not None:
        return tuple(group)
    return tuple(getattr(r, k) for k in ("a", "b", "v") if isinstance(getattr(r, k, None), int))


def kerb_wall_exempt(rows: list[Row], planar: PlanarMap, law: Law
                     ) -> tuple[list[Row], int]:
    """THE WALL (module docstring): ``rows`` less every row (but this
    module's own) spanning a kerb vertex and a wall vertex, and every §37
    ramp row (``constraints/road_ramp``: the road's target and ceiling off
    its DEM) all of whose vertices are kerb vertices — the kerb row is
    that vertex's level, the run-out's precedent
    (``ramp_runout.runout_exempt``); and the count withdrawn."""
    from .road_ramp import GEN as _ROAD_RAMP
    kerb, wall = kerb_vertices(planar, law)
    if not kerb:
        return rows, 0
    keep: list[Row] = []
    n = 0
    for r in rows:
        if r.source.generator != GEN:
            vs = _row_vertices(r)
            on = [v in kerb for v in vs]
            if (any(on) and any(v in wall for v in vs)) or (
                    r.source.generator == _ROAD_RAMP and vs and all(on)):
                n += 1
                continue
        keep.append(r)
    return keep, n
