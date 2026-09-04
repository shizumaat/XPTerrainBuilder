"""STRUCTURE constraints (M4; plan §1 row 5 "structure constraints") —
rows over the tunnel ramp / wall / deck faces the planar map carries
with its ``structures`` records.  A generator, never a writer: every
value is a law-table constant or a DEM sample the planar builder
recorded, and every row names its ruling.

THE ROWS (law ``structures.toml``; RULINGS 2026-08-30, 2026-08-30c/d/f,
2026-09-01c/e, 2026-09-03b):

* RAMP — the ring vertices of each ramp piece are grouped by their
  station along the axis (a left/right pair per station, plus whatever
  the arrangement noded onto the top edge); each group is a ``Flat``
  (the ramp is laterally flat — ``road_cross_section`` at 0 %), and
  consecutive groups are a ``Diff`` at ``tunnel.ramp_max_grade`` over
  their axis distance (the descent law, per corridor axis).  The mouth
  group is PINNED at the mouth datum ``DEM(mouth) − bore_datum_m``
  (09-03b: the mouth wall stands ``bore_datum_m`` above the ramp's
  mouth node; the bore continues below and is not emitted).  With a
  deck across the corridor the cut stays AT the mouth datum from the
  mouth to the deck and the climb begins on the far side (08-30f): every
  group at or before ``climb_from_s`` is pinned at the datum, and so is
  the first group beyond it.  The top group is pinned at the DEM
  (``top_pinned``); a ramp a building pad clipped short ends free
  (08-07 ruling 3: the pad's face is the portal).
* WALL — every ``retaining_wall`` vertex is PINNED at the DEM sampled
  at its projection onto the band's centreline (09-03b L1 "crest = DEM
  by station"; ``tunnel.crest = "dem"``): the inner and outer edge at
  one station project to one point and carry ONE value (09-01c), the
  end cap likewise (its projection is the cap's own centreline at the
  mouth, so the cap crest is ``DEM(mouth)`` — ``bore_datum_m`` above the
  mouth node exactly).  Nothing else touches a wall value: no transition
  law, no ramp-side grading (09-03b L2: the wall IS the discontinuity).
  The gap between ramp and wall has no vertices: the mesh triangulates
  it (09-01c: "the triangulated gap IS the face").
* DECK — every terrain-deck vertex is PINNED at the DEM (08-30d: the
  deck spans the crossing AT ROAD LEVEL; v2's road level is the ground)
  and an ``Offset`` holds it ``bridge.clearance_m`` above the ramp
  groups abutting it on both sides (08-30c §4: the deck conforms
  upward, never the ramp downward — with the ramp pinned at datum the
  offset is a CHECK the solver reports as an IIS when the DEM is too
  low, never a value it invents).
* OBJECT BRIDGE (M4b; ``Deck.datum == "deck_top"``) — the deck is the
  OBJECT, seated at its deck TOP (memory othh-bridge-deck-datum-r12):
  every ramp vertex under its footprint is bounded ABOVE by ``deck top −
  bridge.clearance_m`` (a ``Band``; 08-30f: the cut stays at bore datum
  under the bridge — the datum satisfies it or the IIS names the object).
* BASIN (M4b; RULINGS 2026-08-26; ``structures.toml [basin]``) — every
  floor-face vertex is PINNED at the facility's floor (``Basin.floor_z``,
  the R_est + deepest-solid − margins arithmetic the planar builder
  did once); the wall band round it carries the ground exactly as the
  tunnel wall does (the ground rule: the governed ground's value where
  its edge is shared — the rim LEVEL with the apron, 2026-08-28c item 3
  — the DEM by station where bare), one value per station across the
  band (09-01c).  The gap between floor and wall has no vertices.

The 08-30l consumer rows this generator's geometry settles: the zone
regions stop at the wall (``planar.zones`` keep-outs); the ramp is its
own class — not a road-family ring (``families.road_cross_section.roles``
names none of it), so the lateral-contiguity walk does not bind it;
``no_step`` excludes it (groundside); the transverse walk has no axis
in it; a taxiway or apron OVER the bore keeps its own law (no bore face
exists).  The wall's outer-edge vertices are SHARED with the pavement
it cut, so that pavement carries the DEM there (2026-09-03b: "no service
road shape running around the outside of the tunnel wall" — the ground
outside the wall is the ground).
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Band, Diff, Flat, Linear, Offset, Pin, Row, Source
from ..model.frame import XY
from ..model.planar import Face, PlanarMap
from ..model.structures import Basin, Tunnel
from .precedence import view

__all__ = ["structures", "basins", "ramp_groups", "wall_faces_of", "ramp_faces_of", "GEN"]

GEN = "structures"
#: Two ramp vertices closer than this along the axis are one station.
_STATION_CLUSTER_M = 1.0


def _faces_of(planar: PlanarMap, tunnels: _t.Sequence[Tunnel], role: str,
              path_of: _t.Callable[[Tunnel], _t.Sequence[XY]]) -> dict[str, list[Face]]:
    """Tunnel id -> its faces of ``role``, joined BY GEOMETRY (the ramp
    and wall refs are the oracle's population keys, ``tunnel_ramp`` /
    ``tunnel_wall`` exactly): the tunnel whose ``path_of`` line is
    nearest the face's ring centroid."""
    paths = {tn.id: LineString(path_of(tn)) for tn in tunnels if len(path_of(tn)) >= 2}
    out: dict[str, list[Face]] = {tn.id: [] for tn in tunnels}
    if not paths:
        return out
    for f in planar.faces.values():
        if f.role != role:
            continue
        ids = planar.ring_vertices(f.ring)
        cx = sum(planar.vertices[v].xy[0] for v in ids) / len(ids)
        cy = sum(planar.vertices[v].xy[1] for v in ids) / len(ids)
        p = Point(cx, cy)
        best = min(paths, key=lambda k: paths[k].distance(p))
        out[best].append(f)
    return out


def wall_faces_of(planar: PlanarMap, tunnels: _t.Sequence[Tunnel]) -> dict[str, list[Face]]:
    """Tunnel id -> its ``retaining_wall`` faces."""
    return _faces_of(planar, tunnels, "retaining_wall", lambda tn: tn.wall_path)


def ramp_faces_of(planar: PlanarMap, tunnels: _t.Sequence[Tunnel]) -> dict[str, list[Face]]:
    """Tunnel id -> its ``tunnel_ramp`` faces."""
    return _faces_of(planar, tunnels, "tunnel_ramp", lambda tn: tn.axis)


def ramp_groups(planar: PlanarMap, tn: Tunnel, face: Face
                ) -> list[tuple[float, list[int]]]:
    """``[(s, [vertex ids])…]`` — the face's ring vertices grouped by
    station along the ramp axis, ascending ``s``."""
    axis = LineString(tn.axis)
    ids = list(planar.ring_vertices(face.ring))
    with_s = sorted((axis.project(Point(planar.vertices[v].xy)), v) for v in ids)
    groups: list[tuple[float, list[int]]] = []
    for s, v in with_s:
        if groups and s - groups[-1][0] <= _STATION_CLUSTER_M:
            groups[-1][1].append(v)
        else:
            groups.append((s, [v]))
    return groups


def _dem_at(airport: Airport, x: float, y: float) -> float:
    return float(airport.dem.z(x, y))


def _cluster(items: list[tuple[float, int]], tol: float) -> list[tuple[float, list[int]]]:
    items = sorted(items)
    groups: list[tuple[float, list[int]]] = []
    for u, v in items:
        if groups and u - groups[-1][0] <= tol:
            groups[-1][1].append(v)
        else:
            groups.append((u, [v]))
    return groups


def structures(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every structure row for the map's tunnels.

    THE GROUND RULE (M4 reading of 2026-09-03b under 03i, open question
    to the owner): a structure vertex the GOVERNED ground shares — a wall
    outer-edge vertex on the apron it cut, a ramp top-edge vertex on the
    pavement it climbs to, a deck vertex on the road ground — takes that
    ground's solved value (the ungoverned wall yields to the governed
    apron; measured LEMD: a DEM crest pin at 1.07 % along a 26 m apron
    edge vs the apron's 1 % cap was an IIS); a vertex on bare ground is
    the DEM.  The band stays ONE value per station across its width
    (09-01c) as a ``Flat``; the mouth datum is the end cap's crest minus
    ``bore_datum_m`` (09-03b's 5.1 m relation, exact in both cases)."""
    tunnels = planar.structures
    if not tunnels:
        return []
    tn_law = law.tables.structures.tunnel
    br_law = law.tables.structures.bridge
    if tn_law.crest != "dem":
        raise ValueError(f"tunnel.crest {tn_law.crest!r}: only 'dem' is generated")
    rows: list[Row] = []
    pins: dict[int, Pin] = {}

    def pin(v: int, z: float, src: Source, senior: bool = False) -> None:
        if senior or v not in pins:
            pins[v] = Pin(v, z, src)

    vw = view(planar, law)
    structure_roles = ("tunnel_ramp", "retaining_wall")

    def shared_with_ground(v: int) -> bool:
        """A governed face other than the structure's own touches ``v``
        (a terrain deck is road ground, 08-30m)."""
        for fid in vw.vertex_faces[v]:
            f = planar.faces[fid]
            if f.role not in structure_roles and vw.caps[fid] is not None:
                return True
        return False

    walls = wall_faces_of(planar, tunnels)
    ramps = ramp_faces_of(planar, tunnels)
    faces_by_ref: dict[str, list[Face]] = {}
    for f in planar.faces.values():
        faces_by_ref.setdefault(f.ref.split("#")[0], []).append(f)
    for tn in tunnels:
        inputs = (tn.id, *(f"osm:{w}" for w in tn.ways))
        src_ramp = Source(GEN, "tunnel.ramp_max_grade (2026-08-07 r4; 2026-08-30)", inputs)
        src_mouth = Source(GEN, "tunnel.bore_datum_m (2026-09-03b)", inputs)
        src_flat = Source(GEN, "tunnel_ramp laterally flat (road_cross_section 0 %)", inputs)
        src_top = Source(GEN, "ramp top = ground (2026-08-30 canonical mouth)", inputs)
        src_wall = Source(GEN, "tunnel.crest = dem (2026-09-03b L1; 2026-09-01c)", inputs)
        src_band = Source(GEN, "one corridor-top value per station (2026-09-01c)", inputs)
        # ── the wall band: crest = the ground, one value per station ──
        path = LineString(tn.wall_path) if len(tn.wall_path) >= 2 else None
        cap_reps: list[int] = []
        if path is not None:
            wall_vs = sorted({v for f in walls.get(tn.id, ()) for v in planar.ring_vertices(f.ring)})
            groups = _wall_rows(planar, airport, path, wall_vs, shared_with_ground, rows, pin,
                                src_wall, src_band)
            if tn.cap_centre is not None and groups:
                uc = path.project(Point(tn.cap_centre))
                cap_reps.append(min(groups, key=lambda g: abs(g[0] - uc))[1][0])
        # ── ramp pieces ────────────────────────────────────────────
        pieces: list[tuple[float, Face]] = []
        for f in ramps.get(tn.id, ()):
            g = ramp_groups(planar, tn, f)
            if g:
                pieces.append((g[0][0], f))
        pieces.sort(key=lambda t: t[0])
        seen: set[int] = set()
        abut: list[tuple[float, list[int]]] = []     # groups beside a deck
        datum_vs: list[int] = []
        for k, (_s0, f) in enumerate(pieces):
            if f.id in seen:
                continue
            seen.add(f.id)
            groups = ramp_groups(planar, tn, f)
            for s, vs in groups:
                if len(vs) > 1:
                    rows.append(Flat(tuple(vs), src_flat))
            # THE DESCENT LAW AS THE CENSUS PRICES IT (``within_shape``:
            # every ring vertex pair at the role cap over the DIRECT
            # distance — a curved corridor's chord across the bend is
            # shorter than its axis; measured OTHH -8342: 5.1 m over a
            # 74 m chord of a 144 m axis, 6.9 %)
            ids = [v for _s, vs in groups for v in vs]
            for i in range(len(ids)):
                (xa, ya) = planar.vertices[ids[i]].xy
                for j in range(i + 1, len(ids)):
                    (xb, yb) = planar.vertices[ids[j]].xy
                    d = math.hypot(xa - xb, ya - yb)
                    if d > 1e-6:
                        rows.append(Diff(ids[i], ids[j], tn_law.ramp_max_grade, d, src_ramp))
            # the datum: the mouth, every covered stretch, and the resume
            # group just beyond the last deck (``climb_from_s`` is that
            # deck's far edge + the gap, where the far piece begins)
            for s, vs in groups:
                if s <= tn.climb_from_s + _STATION_CLUSTER_M:
                    datum_vs.extend(vs)
            if tn.decks:
                abut.extend(groups)
            # the top: the ground it climbs to (its value where shared,
            # the DEM where bare)
            if k == len(pieces) - 1 and tn.top_pinned and groups:
                s_top, vs = groups[-1]
                if not any(shared_with_ground(v) for v in vs):
                    x, y = tn.axis[-1]
                    z = _dem_at(airport, x, y)
                    if not math.isnan(z):
                        for v in vs:
                            pin(v, z, src_top)
        # THE MOUTH DATUM: the end cap's crest (the covering surface's own
        # level — the DEM where bare, the ground's solved value where
        # shared) minus bore_datum_m (09-03b: "the mouth wall node stands
        # 5.1 m above the ramp's mouth node"), as an EQUALITY on the
        # datum group: z_mouth − z_cap_centre = −bore_datum_m.  A
        # DEM point sample at the mouth is not the covering surface where
        # the smoothed DEM rides a ridge over a real cutting (measured
        # LEMD -15327+-5980: the ground 8.4 m under the datum 24 m out).
        # The ramp's objective target is its design (``planar.structures.
        # ramp_targets``), so the tie cannot lever the ground.
        if datum_vs:
            group = tuple(sorted(set(datum_vs)))
            if len(group) > 1:
                rows.append(Flat(group, src_mouth))
            if len(cap_reps) == 1:
                rows.append(Linear(((group[0], 1.0), (cap_reps[0], -1.0)),
                                   -tn_law.bore_datum_m, -tn_law.bore_datum_m, src_mouth))
            else:
                pin(group[0], tn.mouth_z, src_mouth)
        # ── decks ───────────────────────────────────────────────────
        for d in tn.decks:
            if d.datum == "deck_top":
                # THE OBJECT BRIDGE: the ramp under the footprint stays
                # bridge.clearance_m under the object's deck top
                src_obj = Source(GEN, "bridge.deck_datum = deck_top; bridge.clearance_m "
                                 "(memory othh-bridge-deck-datum-r12; 08-30f)",
                                 (*inputs, d.ref))
                from shapely.geometry import Polygon as _Poly
                dpoly = _Poly(d.ring)
                hi = float(d.z) - br_law.clearance_m
                for f in ramps.get(tn.id, ()):
                    for v in set(planar.ring_vertices(f.ring)):
                        if dpoly.distance(Point(planar.vertices[v].xy)) <= 1e-6:
                            rows.append(Band(v, None, hi, src_obj))
                continue
            src_clear = Source(GEN, "bridge.clearance_m (2026-08-30c §4, 08-30f)",
                               (*inputs, f"osm:{d.way}"))
            # THE DECK IS ROAD (08-30m): a governed ``service_road`` face
            # solved under the road cap toward the DEM (08-30d "at road
            # level"), never pinned — a DEM pin at 11 % across a 5 m deck
            # edge was an IIS against the road law (measured LEMD deck
            # -11828); the clearance is the only structural row
            deck_vs: list[int] = []
            for f in faces_by_ref.get(d.ref, ()):
                deck_vs.extend(set(planar.ring_vertices(f.ring)))
            if not deck_vs:
                continue
            # the ramp groups ABUTTING the deck: within the gap (+ the grid
            # step the severing added) of the deck's own ring — a deck
            # crossing at an angle spans several stations' s
            from shapely.geometry import Polygon as _Poly
            dpoly = _Poly(d.ring)
            reach = tn_law.wall_gap_m + law.tables.emit.identity.min_distinct_spacing_m + 0.5
            # EVERY deck vertex clears EVERY abutting ramp group (the deck
            # is a road face solved under its own cap, so its low side is
            # not its first vertex — measured LEMD: 4.81 m at one edge)
            for s, vs in abut:
                if any(dpoly.distance(Point(planar.vertices[v].xy)) <= reach for v in vs):
                    for dv in sorted(set(deck_vs)):
                        rows.append(Offset(dv, vs[0], br_law.clearance_m, src_clear))
    rows.extend(pins.values())
    return rows


def _wall_rows(planar: PlanarMap, airport: Airport, path: LineString, wall_vs: list[int],
               shared_with_ground: _t.Callable[[int], bool], rows: list[Row],
               pin: _t.Callable[..., None], src_wall: Source, src_band: Source
               ) -> list[tuple[float, list[int]]]:
    """THE WALL CREST BY STATION (2026-09-03b L1; 2026-09-01c; the ground
    rule): the band's vertices grouped by station along ``path`` — one
    ``Flat`` per station across the band; a station the governed ground
    shares carries the ground's value, a bare one the DEM at its own
    station on the centreline.  Returns the groups."""
    closed = len(path.coords) > 2 and path.coords[0] == path.coords[-1]
    groups = _cluster([(path.project(Point(planar.vertices[v].xy)), v) for v in wall_vs],
                      _STATION_CLUSTER_M)
    if closed and len(groups) > 1 and \
            groups[0][0] + path.length - groups[-1][0] <= _STATION_CLUSTER_M:
        # a closed band: the station at s ≈ 0 and at s ≈ length is one
        first, last = groups[0], groups.pop()
        groups[0] = (first[0], first[1] + last[1])
    for u, vs in groups:
        if len(vs) > 1:
            rows.append(Flat(tuple(vs), src_band))
        if any(shared_with_ground(v) for v in vs):
            continue                      # the ground's value carries the crest
        # ONE value per station: the DEM at the group's own station on
        # the band's centreline (inner and outer edge project millimetres
        # apart — two samples were an IIS)
        u_mean = sum(path.project(Point(planar.vertices[v].xy)) for v in vs) / len(vs)
        p = path.interpolate(u_mean)
        z = _dem_at(airport, p.x, p.y)
        if not math.isnan(z):
            for v in vs:
                pin(v, z, src_wall, senior=True)
    return groups


def basins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every basin row (M4b): the floor pinned at the facility's floor,
    the wall band's crest by the ground rule."""
    if not planar.basins:
        return []
    bl = law.tables.structures.basin
    if bl.floor != "deepest_solid" or bl.rim != "ground":
        raise ValueError(f"basin.floor {bl.floor!r} / rim {bl.rim!r}: only "
                         "'deepest_solid' / 'ground' are generated")
    rows: list[Row] = []
    pins: dict[int, Pin] = {}

    def pin(v: int, z: float, src: Source, senior: bool = False) -> None:
        if senior or v not in pins:
            pins[v] = Pin(v, z, src)

    vw = view(planar, law)
    structure_roles = ("tunnel_trench", "retaining_wall")

    def shared_with_ground(v: int) -> bool:
        for fid in vw.vertex_faces[v]:
            f = planar.faces[fid]
            if f.role not in structure_roles and vw.caps[fid] is not None:
                return True
        return False

    faces_by_ref: dict[str, list[Face]] = {}
    for f in planar.faces.values():
        faces_by_ref.setdefault(f.ref.split("#")[0], []).append(f)
    for b in planar.basins:
        inputs = (b.id, *(f"obj:{o}" for o in b.objects[:8]))
        src_floor = Source(GEN, "basin.floor = deepest_solid: R_est + min solid − "
                           "(floor_below_object_deck_m + seat_margin_m) (2026-08-26)", inputs)
        src_wall = Source(GEN, "basin.rim = ground (2026-08-28c item 3; 2026-09-03b L1)", inputs)
        src_band = Source(GEN, "one crest value per station (2026-09-01c)", inputs)
        for f in faces_by_ref.get(b.floor_ref, ()):
            for v in set(planar.ring_vertices(f.ring)):
                pin(v, b.floor_z, src_floor, senior=True)
        if len(b.wall_path) >= 3:
            path = LineString(list(b.wall_path) + [b.wall_path[0]])
            wall_vs = sorted({v for f in faces_by_ref.get(b.wall_ref, ())
                              for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)})
            _wall_rows(planar, airport, path, wall_vs, shared_with_ground, rows, pin,
                       src_wall, src_band)
    rows.extend(pins.values())
    return rows
