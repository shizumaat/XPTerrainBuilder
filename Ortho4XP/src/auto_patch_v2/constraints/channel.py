"""THE OPEN CHANNEL'S ROWS (spec §45 (2)/(3)/(5); owner RULINGS
2026-09-15i) — lane ``v2channel``.

Its own module beside ``constraints/structures.py`` for that file's own
1,000-line reason, and for a second: a channel's rows are NOT a tunnel's.
A bore's rim is pinned at the DEM by station (2026-09-03b L1) and its
ramp descends to a mouth; a channel has no mouth at all (§45 (6)) and its
crest is the SOLVED surface of the governed cell at the corridor edge
(§45 (5) — ``crest = "design"``), which is a RELATIONAL row and never a
pin.  Mixing the two in one generator is how a "design" crest would end
up reading ``DEM(x, y)`` at LGAV, 2–4 m under the real rim.

THE RECORD IS THE LAW.  Every number here comes off
``model.structures.Channel`` — ``floor_z(s)`` for the floor,
``walls``/``crest`` for the rim.  ``verify/channel.py`` judges the
emitted surface with the SAME calls on the published record, so the
stated row and the published expectation cannot drift (the defect
``deck_z_on_faces``'s docstring names, and the one §24 (5) had to fix).
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Offset, Pin, Row, Source
from ..model.planar import PlanarMap
from ..model.structures import CHANNEL_FLOOR_ROLE, CHANNEL_WALL_ROLE, CREST_DESIGN
from .precedence import view

__all__ = ["channels", "GEN", "FLOOR_RULING", "CREST_RULING",
           "floor_faces_of", "wall_faces_of"]

GEN = "channels"
FLOOR_RULING = ("channel.floor = the record's profile (spec §45 (3); owner RULINGS "
                "2026-09-15i \"Cut the road down\")")
CREST_RULING = ("channel.crest = \"design\": the solved surface of the governed cell at "
                "the corridor edge, never DEM(x, y) (spec §45 (5))")

#: The refs ``planar/channel.py`` writes.  A ``tunnel_trench`` face whose
#: ref is NOT one of these is a BASIN floor (``basin_floor:``) and keeps
#: §24's rows — ``verify/structures._basin_floors`` already keys on that
#: prefix, so the two populations never mix.
FLOOR_PREFIX = "channel_floor:"
WALL_PREFIX = "channel_wall:"


def _faces(planar: PlanarMap, role: str, prefix: str) -> dict[str, list]:
    """Channel id -> its faces of ``role`` whose ref carries ``prefix``.
    The id is IN the ref (``channel_floor:<k>``), so this is a lookup and
    not the geometric join ``_faces_of`` has to do for a tunnel."""
    out: dict[str, list] = {}
    for f in planar.faces.values():
        if f.role != role or not f.ref.startswith(prefix):
            continue
        key = "channel:" + f.ref[len(prefix):].split("#")[0]
        out.setdefault(key, []).append(f)
    return out


def floor_faces_of(planar: PlanarMap) -> dict[str, list]:
    """Channel id -> its ``tunnel_trench`` floor faces."""
    return _faces(planar, CHANNEL_FLOOR_ROLE, FLOOR_PREFIX)


def wall_faces_of(planar: PlanarMap) -> dict[str, list]:
    """Channel id -> its ``retaining_wall`` void faces (the bank; its
    exterior ring is the CREST)."""
    return _faces(planar, CHANNEL_WALL_ROLE, WALL_PREFIX)


def channels(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every OPEN-CHANNEL row the map carries.

    **THE FLOOR (§45 (3)).**  Each floor vertex is PINNED at the record's
    own profile at its station along the axis — a senior, absolute pin,
    the same shape the sunken road's floor takes (Law B, 2026-09-08b/c),
    because the floor is a measurement (the pack's plate, the credible
    lidar's DTM, or the deck top less ``bridge.clearance_m``) and not the
    outcome of a grade law.

    **THE CREST (§45 (5)).**  ``crest = "design"``: the crest at each wall
    station is the SOLVED surface of the governed cell at the corridor
    edge, so
      * a crest vertex the governed ground SHARES carries that ground's
        value already — one node, one value (09-01g) — and takes NO row;
      * a BARE crest vertex takes a two-sided equality (``Offset`` both
        ways at 0.0) to the nearest vertex of the governed cell it stands
        in — the ``frontage_level`` mechanism §34 (5)'s portal rim uses,
        two-sided here because the crest IS that cell's surface carried
        outward, not a crest merely rising to meet it;
      * a bare crest vertex standing in NO governed cell takes nothing at
        all.  It is adjacent ground and the §19 / zone laws govern it.
        **It is never pinned at the DEM** — that is the whole of (5).
    """
    chans = getattr(planar, "channels", ())
    if not chans:
        return []
    tn = law.tables.structures.tunnel
    bad = [c.id for c in chans if c.crest != CREST_DESIGN]
    if bad:
        raise ValueError(f"channel.crest {bad}: only {CREST_DESIGN!r} is generated "
                         f"(spec §45 (5); a bore's {'dem'!r} crest is "
                         f"constraints/structures.py's)")
    vw = view(planar, law)
    floors = floor_faces_of(planar)
    walls = wall_faces_of(planar)
    structure_roles = (CHANNEL_FLOOR_ROLE, CHANNEL_WALL_ROLE, "tunnel_ramp",
                       "door_ramp", "wall_corridor_ramp", "garage_ramp")
    rows: list[Row] = []
    for c in chans:
        inputs = (c.id, *(f"osm:{w}" for w in c.ways))
        src_floor = Source(GEN, FLOOR_RULING, inputs)
        src_crest = Source(GEN, CREST_RULING, inputs)
        if len(c.axis) < 2 or not c.profile:
            continue
        axis = LineString(c.axis)
        on_floor: set[int] = set()
        for f in floors.get(c.id, ()):
            for v in _ring_and_holes(planar, vw, f):
                on_floor.add(v)
        for v in sorted(on_floor):
            s = axis.project(Point(planar.vertices[v].xy))
            rows.append(Pin(v, float(c.floor_z(s)), src_floor))
        # ── the crest ──────────────────────────────────────────────────
        for f in walls.get(c.id, ()):
            for v in _ring_and_holes(planar, vw, f):
                if v in on_floor:
                    continue          # the void's inner ring IS the floor edge
                if _shared_with_ground(planar, vw, v, structure_roles):
                    continue          # one node, one value: the cell governs it
                gv = _governed_vertex(planar, vw, v, structure_roles)
                if gv is None:
                    continue          # adjacent ground: §19 / the zones govern
                rows.append(Offset(v, gv, 0.0, src_crest))
                rows.append(Offset(gv, v, 0.0, src_crest))
    return rows


def _ring_and_holes(planar: PlanarMap, vw, f) -> list[int]:
    out = list(vw.rings[f.id])
    for h in vw.holes[f.id]:
        out.extend(h)
    return out


def _shared_with_ground(planar: PlanarMap, vw, v: int, structure_roles) -> bool:
    for fid in vw.vertex_faces[v]:
        g = planar.faces[fid]
        if g.role not in structure_roles and vw.caps[fid] is not None:
            return True
    return False


def _governed_vertex(planar: PlanarMap, vw, v: int, structure_roles) -> int | None:
    """The governed cell this crest vertex stands IN, and that cell's
    nearest OTHER vertex — the value the crest takes (§45 (5)).  ONE
    reading with ``constraints/structures._deck_cell_vertex``'s, stated
    here because a channel's crest reads the cell at the corridor EDGE
    and a portal rim reads the DECK cell it stands under; widening that
    function to serve both would make one law answer two questions."""
    pt = Point(planar.vertices[v].xy)
    best = None
    for fid, cap in vw.caps.items():
        f = planar.faces[fid]
        if cap is None or f.role in structure_roles or f.role == "graded_strip":
            continue
        ring = list(vw.rings[fid])
        if v in ring:
            continue
        poly = Polygon([planar.vertices[u].xy for u in ring])
        if not poly.is_valid or not poly.contains(pt):
            continue
        for u in ring:
            d = pt.distance(Point(planar.vertices[u].xy))
            if best is None or d < best[0]:
                best = (d, u)
    return None if best is None else best[1]
