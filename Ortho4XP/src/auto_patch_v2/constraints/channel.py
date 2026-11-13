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

from shapely.geometry import LineString, Point

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Offset, Pin, Row, Source
from ..model.planar import PlanarMap
from ..model.structures import CHANNEL_FLOOR_ROLE, CHANNEL_WALL_ROLE, CREST_DESIGN
from .precedence import view
from .geometry import nearest_vertex_of_containing_cell

__all__ = ["channels", "GEN", "FLOOR_RULING", "CREST_RULING", "LEDGE_RULING",
           "floor_faces_of", "wall_faces_of", "ledge_pin_vertices"]

GEN = "channels"
FLOOR_RULING = ("channel.floor = the record's profile (spec §45 (3); owner RULINGS "
                "2026-09-15i \"Cut the road down\")")
CREST_RULING = ("channel.crest = \"design\": the solved surface of the governed cell at "
                "the corridor edge, never DEM(x, y) (spec §45 (5))")

LEDGE_RULING = ("channel.crest at a LEDGE member's foot = that foot (spec "
                "object-gate-member-floors §4.4; owner RULINGS 2026-11-06d (6) with "
                "2026-11-13i \"we don't want any visible edge to be floating\")")
#: the crest's roles that are a structure's, never the governed ground's
STRUCTURE_ROLES = (CHANNEL_FLOOR_ROLE, CHANNEL_WALL_ROLE, "tunnel_ramp", "door_ramp",
                   "wall_corridor_ramp", "garage_ramp")

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
    structure_roles = STRUCTURE_ROLES
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
        # the axis is stated from the record's FIRST station (the field-side
        # end), the profile in the corridor's own stations: one reading, the
        # verifier's ``_declared_at`` (a flat floor never showed the offset;
        # a profile does, #1918)
        s0 = float(c.profile[0][0])
        for v in sorted(on_floor):
            s = s0 + axis.project(Point(planar.vertices[v].xy))
            rows.append(Pin(v, float(c.floor_z(s)), src_floor))
        # ── the crest ──────────────────────────────────────────────────
        ledges = ledge_pin_vertices(planar, law, c, vw, walls, on_floor)
        src_ledge = Source(GEN, LEDGE_RULING, inputs)
        for v, (_k, zl) in sorted(ledges.items()):
            rows.append(Pin(v, zl, src_ledge))
        for f in walls.get(c.id, ()):
            for v in _ring_and_holes(planar, vw, f):
                if v in on_floor or v in ledges:
                    continue          # the floor edge; a ledge foot's pin
                if _shared_with_ground(planar, vw, v, structure_roles):
                    continue          # one node, one value: the cell governs it
                gv = nearest_vertex_of_containing_cell(planar, vw, v, structure_roles)
                if gv is None:
                    continue          # adjacent ground: §19 / the zones govern
                rows.append(Offset(v, gv, 0.0, src_crest))
                rows.append(Offset(gv, v, 0.0, src_crest))
    return rows


def ledge_pin_vertices(planar: PlanarMap, law: Law, c, vw=None, walls=None,
                       on_floor: "set[int] | None" = None) -> dict[int, tuple[int, float]]:
    """``{crest vertex: (ledge pin index, z)}`` (spec §4.4): the crest
    vertex within ``emit.identity.min_distinct_spacing_m`` of each of
    ``c.ledge_pins`` takes that pin — unless a governed cell SHARES it (one
    node, one value: the cell governs, and the foot is published
    ``unmet``) or it is the floor's own edge."""
    pins = getattr(c, "ledge_pins", ()) or ()
    if not pins:
        return {}
    vw = view(planar, law) if vw is None else vw
    walls = wall_faces_of(planar) if walls is None else walls
    if on_floor is None:
        on_floor = {v for f in floor_faces_of(planar).get(c.id, ())
                    for v in _ring_and_holes(planar, vw, f)}
    tol = float(law.tables.emit.identity.min_distinct_spacing_m)
    crest = sorted({v for f in walls.get(c.id, ()) for v in _ring_and_holes(planar, vw, f)}
                   - set(on_floor))
    out: dict[int, tuple[int, float]] = {}
    if not crest:
        return out
    import numpy as np
    xy = np.array([planar.vertices[v].xy for v in crest], float)
    for k, (px, py, pz) in enumerate(pins):
        d = np.hypot(xy[:, 0] - px, xy[:, 1] - py)
        j = int(np.argmin(d))
        v = crest[j]
        if d[j] > tol or v in out or _shared_with_ground(planar, vw, v, STRUCTURE_ROLES):
            continue
        out[v] = (k, float(pz))
    return out


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


