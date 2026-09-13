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
* RIM — every vertex of the at-grade RIM (the ``retaining_wall`` VOID
  face's exterior ring; RULINGS 2026-09-06b (1), no wall band) is PINNED
  at the DEM sampled at its own station on the rim (09-03b L1 "crest =
  DEM by station"; ``tunnel.crest = "dem"``) where bare, and carries the
  governed ground's value where shared with the pavement the structure
  cut; the end cap likewise (the cap's centre is the MOUTH WALL NODE:
  its crest is ``DEM(mouth)`` — ``bore_datum_m`` above the mouth node
  exactly).  Nothing else touches a rim value: no transition law, no
  ramp-side grading (09-03b L2: the wall IS the discontinuity).  The
  void between ramp and rim has no vertices of its own: the mesh
  triangulates the wall (09-01c: "the triangulated gap IS the face").
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
* BASIN (M4b; RULINGS 2026-08-26, 2026-09-06b (3); ``structures.toml
  [basin]``) — every floor-face vertex stands ``body_depth_m`` UNDER ITS
  NEAREST RIM VERTEX (owner RULINGS 2026-09-10ba, replacing the absolute
  pin at ``Basin.floor_z``: the rim follows the pavement and the floor
  follows the rim); the rim round it carries the ground exactly as the tunnel rim
  does (the ground rule: the governed ground's value where its edge is
  shared — the rim LEVEL with the apron, 2026-08-28c item 3 — the DEM by
  station where bare).  The void between floor and rim has no vertices
  of its own.

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
from ..law.tables import is_rigid_role, pavement_roles
from ..model.airport import Airport
from ..model.constraints import Band, Diff, Flat, Linear, Offset, Pin, Row, Source
from ..model.frame import XY
from ..model.planar import Face, PlanarMap
from ..model.structures import Basin, Tunnel
from .precedence import view

__all__ = ["structures", "basins", "ramp_groups", "wall_faces_of", "ramp_faces_of",
           "reconcile_datums", "structure_of", "rim_level", "rim_contacts",
           "GEN", "GEN_RIM_LEVEL", "RIM_LEVEL_RULING", "BASIN_FLOOR_RULING",
           "RAMP_REF", "WALL_REF"]

GEN = "structures"
#: The planar builder's refs of a tunnel's own faces (``planar/structures.py``;
#: the verify reader keys the same strings) — the join keys of ``_faces_of``.
RAMP_REF = "tunnel_ramp"
WALL_REF = "tunnel_wall"
#: The ROLE of every structure's void/rim face — a tunnel's and a basin's
#: alike (``planar/structures.py`` / ``planar/basins.py``).
WALL_ROLE = "retaining_wall"
#: The RIM's flush-contact rows carry their own generator so the design
#: report reads their residual as its own line (2026-09-10an).
GEN_RIM_LEVEL = "rim_level"
#: Its ruling HEAD — named by ``[design] one_way_rulings`` (the rim
#: follows the pavement, never pulls it).
RIM_LEVEL_RULING = "structures.structure_rim frontage_level"
#: THE BASIN FLOOR IS THE OBJECT'S DEPTH BELOW THE RIM (owner RULINGS
#: 2026-09-10ba; spec §22.1c).  Its ruling HEAD: the row is an EQUALITY
#: (``lo == hi``) the design solve prices at ``[design] law``, and the
#: vertex it GOVERNS anchors its sheet (``solve/design`` §9).
BASIN_FLOOR_RULING = "basin.floor = rim - body_depth"
#: A door ramp's role AND ref (RULINGS 2026-09-08b/c Law A).
DOOR_RAMP_REF = "door_ramp"
#: RULINGS 2026-09-08m/08n Law C: a wall corridor's floor + climb, and an
#: authored garage ramp (``planar/wall_corridor_ramps.py``).
WALL_CORRIDOR_ROLES = ("wall_corridor_ramp", "garage_ramp")
WALL_CORRIDOR_SOURCE = "wall_corridor"
#: Two ramp vertices closer than this along the axis are one station.
_STATION_CLUSTER_M = 1.0

#: Per-generator statistics (``constraints.generate`` publishes them as
#: ``<generator>.<key>``): the basin floors stated RELATIVE to their rim
#: and the ones that fell back to the absolute pin (RULINGS 2026-09-10ba).
STATS: dict[str, dict[str, int]] = {}


def _faces_of(planar: PlanarMap, tunnels: _t.Sequence[Tunnel], role: str, ref: str,
              path_of: _t.Callable[[Tunnel], _t.Sequence[XY]]) -> dict[str, list[Face]]:
    """Tunnel id -> its faces of ``role`` AND ``ref`` (the oracle's
    population keys, ``tunnel_ramp`` / ``tunnel_wall`` exactly — the
    ``#n`` piece suffix aside), joined BY GEOMETRY among the tunnels: the
    one whose ``path_of`` line is nearest the face's ring centroid.  The
    ref is the structure's identity, never the role alone: a basin's wall
    band is ``retaining_wall`` too (ref ``basin_wall:<k>``), and joined by
    role it was pinned at the DEM of its projection onto a tunnel's wall
    path — 616.99 at LEMD basin 22 / tunnel -5938 — against the basin's
    own crest 611.00 on the same vertex: two hard pins, the IIS of
    2026-09-05 (5.99 m tier-8 yield)."""
    paths = {tn.id: LineString(path_of(tn)) for tn in tunnels if len(path_of(tn)) >= 2}
    out: dict[str, list[Face]] = {tn.id: [] for tn in tunnels}
    if not paths:
        return out
    for f in planar.faces.values():
        if f.role != role or f.ref.split("#")[0] != ref:
            continue
        ids = planar.ring_vertices(f.ring)
        cx = sum(planar.vertices[v].xy[0] for v in ids) / len(ids)
        cy = sum(planar.vertices[v].xy[1] for v in ids) / len(ids)
        p = Point(cx, cy)
        best = min(paths, key=lambda k: paths[k].distance(p))
        out[best].append(f)
    return out


def wall_faces_of(planar: PlanarMap, tunnels: _t.Sequence[Tunnel]) -> dict[str, list[Face]]:
    """Tunnel id -> its ``retaining_wall`` (void) faces; the rim is each
    face's exterior ring."""
    return _faces_of(planar, tunnels, "retaining_wall", WALL_REF, lambda tn: tn.wall_path)


def ramp_faces_of(planar: PlanarMap, tunnels: _t.Sequence[Tunnel]) -> dict[str, list[Face]]:
    """Tunnel id -> its ``tunnel_ramp`` faces, and a door's ``door_ramp``
    faces (RULINGS 2026-09-08b/c: the door ramp is its own role)."""
    out = _faces_of(planar, tunnels, "tunnel_ramp", RAMP_REF, lambda tn: tn.axis)
    for role in (DOOR_RAMP_REF, *WALL_CORRIDOR_ROLES):
        for k, fs in _faces_of(planar, tunnels, role, role, lambda tn: tn.axis).items():
            out.setdefault(k, []).extend(fs)
    return out


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
    ob = tn_law.object
    if ob.plate_datum != "ground" or ob.mouth_depth != "floor_slab" or ob.ramp_end != "wall_end":
        raise ValueError(f"tunnel.object plate_datum {ob.plate_datum!r} / mouth_depth "
                         f"{ob.mouth_depth!r} / ramp_end {ob.ramp_end!r}: only 'ground' / "
                         f"'floor_slab' / 'wall_end' are generated")
    rows: list[Row] = []
    pins: dict[int, Pin] = {}
    co = law.tables.structures.cutout
    from ..model.structures import profile_z

    def pin(v: int, z: float, src: Source, senior: bool = False) -> None:
        if senior or v not in pins:
            pins[v] = Pin(v, z, src)

    vw = view(planar, law)
    structure_roles = ("tunnel_ramp", DOOR_RAMP_REF, *WALL_CORRIDOR_ROLES, "retaining_wall")

    def shared_with_ground(v: int) -> bool:
        """A governed face other than the structure's own touches ``v``
        (a terrain deck is road ground, 08-30m)."""
        for fid in vw.vertex_faces[v]:
            f = planar.faces[fid]
            if f.role not in structure_roles and vw.caps[fid] is not None:
                return True
        return False

    def on_floor(v: int) -> bool:
        """A ramp / floor face touches ``v``: a U void's exterior runs along
        the ramp's own edges — those vertices are the ramp's, never rim."""
        return any(planar.faces[fid].role in ("tunnel_ramp", DOOR_RAMP_REF, *WALL_CORRIDOR_ROLES,
                                              "tunnel_trench")
                   for fid in vw.vertex_faces[v])

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
        src_wall = Source(GEN, "tunnel.crest = dem: the rim at the DEM by station "
                          "(2026-09-03b L1; 2026-09-06b no band)", inputs)
        # the descent law's cap: a door ramp's own (09-08b/c Law A), else the tunnel's
        ramp_cap = co.door.ramp_grade if tn.source == "door" else tn_law.ramp_max_grade
        if tn.source == WALL_CORRIDOR_SOURCE:
            ramp_cap = co.wall_corridor.max_ramp_grade
        src_profile = None
        src_bottom = None
        if tn.source == "object":
            # THE OBJECT CORRIDOR (RULINGS 2026-09-05n): the band's crest is
            # the GROUND by station (``plate_datum = "ground"`` — the object
            # is re-seated to it), the mouth datum ground − plate height
            # (``mouth_depth = "floor_slab"``: the slab or the bore law,
            # 2026-09-08l), absolute — never the cap − 5.1
            inputs = (tn.id, *(f"obj:{o}" for o in tn.objects), tn.resource)
            src_wall = Source(GEN, "tunnel.object.plate_datum = ground: the ground by station "
                              "(2026-09-03b L1; 2026-09-05n-4) under an object corridor", inputs)
            src_mouth = Source(GEN, "tunnel.object.mouth_depth = floor_slab: ground(mouth) − "
                              "the floor slab or bore_datum_m (2026-09-05n-1; 2026-09-08l)", inputs)
        elif tn.source == "door":
            # THE DOOR RAMP (RULINGS 2026-09-08b/c Law A): the well floor
            # pinned at the SILL, the climb at cutout.door.ramp_grade, the
            # rim the ground by station inside the well's walls (09-08a)
            inputs = (tn.id, *(f"obj:{o}" for o in tn.objects), tn.resource)
            src_ramp = Source(GEN, "cutout.door.ramp_grade: the door ramp's descent law "
                              "(2026-09-08b/c Law A)", inputs)
            src_mouth = Source(GEN, "cutout.door: the well floor = the sill plate "
                              "(2026-09-08b/c Law A)", inputs)
            src_wall = Source(GEN, "cutout.door: the rim at the ground by station inside the "
                              "well's walls (2026-09-08a; 2026-09-08b/c Law A)", inputs)
        elif tn.source == WALL_CORRIDOR_SOURCE:
            # THE WALL CORRIDOR (RULINGS 2026-09-08m/08n Law C): inside the
            # walls every station is pinned at the wall BOTTOM (level, or a
            # garage ramp cut as authored); beyond them the climb descends
            # at cutout.wall_corridor.max_ramp_grade to the ground at the top
            inputs = (tn.id, *(f"obj:{o}" for o in tn.objects), tn.resource)
            src_bottom = Source(GEN, "cutout.wall_corridor.mouth_depth = wall_bottom: the floor = "
                                "the walls' bottom per station (2026-09-08m/08n Law C)", inputs)
            src_ramp = Source(GEN, "cutout.wall_corridor.max_ramp_grade: the climb beyond the "
                              "walls (2026-09-08m Law C)", inputs)
            src_wall = Source(GEN, "cutout.wall_corridor: the rim at the ground by station inside "
                              "the walls (2026-09-08a; 2026-09-08m Law C)", inputs)
        elif tn.source == "sunken_road":
            # THE SUNKEN ROAD (Law B): every station at the plate's own y
            inputs = (tn.id, *(f"obj:{o}" for o in tn.objects), tn.resource)
            src_mouth = Source(GEN, "cutout.sunken_road: the cut at max_depth_m — the plate's "
                              "floor there (2026-09-08b/c Law B)", inputs)
            src_wall = Source(GEN, "cutout.sunken_road: the rim at the ground by station inside "
                              "the walls (2026-09-08a; 2026-09-08b/c Law B)", inputs)
            src_profile = Source(GEN, "cutout.sunken_road: the floor = the plate's own y per "
                                 "station (2026-09-08b/c Law B)", inputs)
        # ── the rim: the ground by station (the void's exterior ring) ──
        path = LineString(tn.wall_path) if len(tn.wall_path) >= 2 else None
        cap_reps: list[int] = []
        if path is not None:
            wall_vs = sorted({v for f in walls.get(tn.id, ())
                              for v in planar.ring_vertices(f.ring) if not on_floor(v)})
            groups = _rim_rows(planar, airport, path, wall_vs, shared_with_ground, pin, src_wall)
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
            if src_profile is not None and tn.profile:
                # a sunken road: the floor IS the plate — every station
                # group pinned at its y (the plate's own grade, under the
                # ramp cap by ``door_ramps.sunken_groups``); no descent
                # rows, no DEM top: the pins are the law
                for s, vs in groups:
                    z = profile_z(tn.profile, min(s, tn.top_s))
                    for v in vs:
                        pin(v, z, src_profile, senior=True)
                continue
            if src_bottom is not None and tn.profile:
                # Law C: the stations INSIDE the walls are the wall bottom
                # (senior pins); the descent rows below bind only the climb
                # beyond them, anchored on the last inside station
                for s, vs in groups:
                    if s <= tn.wall_length_m + _STATION_CLUSTER_M:
                        z = profile_z(tn.profile, s)
                        for v in vs:
                            pin(v, z, src_bottom, senior=True)
                last_in = max((s for s, _vs in groups if s <= tn.wall_length_m + _STATION_CLUSTER_M),
                              default=None)
                groups_climb = [(s, vs) for s, vs in groups
                                if s > tn.wall_length_m + _STATION_CLUSTER_M or s == last_in]
            else:
                groups_climb = groups
            # THE DESCENT LAW AS THE CENSUS PRICES IT (``within_shape``:
            # every ring vertex pair at the role cap over the DIRECT
            # distance — a curved corridor's chord across the bend is
            # shorter than its axis; measured OTHH -8342: 5.1 m over a
            # 74 m chord of a 144 m axis, 6.9 %)
            ids = [v for _s, vs in groups_climb for v in vs]
            for i in range(len(ids)):
                (xa, ya) = planar.vertices[ids[i]].xy
                for j in range(i + 1, len(ids)):
                    (xb, yb) = planar.vertices[ids[j]].xy
                    d = math.hypot(xa - xb, ya - yb)
                    if d > 1e-6:
                        rows.append(Diff(ids[i], ids[j], ramp_cap, d, src_ramp))
            # the datum: the mouth, every covered stretch, and the resume
            # group just beyond the last deck (``climb_from_s`` is that
            # deck's far edge + the gap, where the far piece begins)
            for s, vs in groups:
                if s <= tn.climb_from_s + _STATION_CLUSTER_M and src_bottom is None:
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
            if tn.source in ("object", "door", "sunken_road"):
                pin(group[0], tn.mouth_z, src_mouth, senior=True)
            elif len(cap_reps) == 1:
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
            # A TERRAIN DECK IS TIED TO ITS ENDS (spec §33 (4); owner
            # RULINGS 2026-09-13d item 9 "the bridge is too low as it needs
            # to smoothly connect the road on either end").  ITS DATUM is
            # the higher of (trench floor + bridge.clearance_m) and the
            # GRADED surface at its two mapped ends — the apron on one
            # side, the road on the other — as a LOWER bound per vertex, so
            # the deck rises to meet them and the ramp beneath yields
            # downward (the clearance rows above are satisfied by the lift,
            # never by pushing the ramp).  A bound, never a pin: the road
            # cap still shapes the face (08-30m; a DEM PIN across a 5 m deck
            # edge was an IIS, measured LEMD deck -11828).  Measured LEMD
            # ways -6288/-6291: emitted 603.81-603.85 = the DEM at the rim,
            # against an apron at 606.5 and way ends at 609.99 / 606.10.
            floor_lo = float(tn.mouth_z) + br_law.clearance_m
            src_ends = Source(GEN, "spec §33 (4): a terrain deck is tied to its ends "
                              "(RULINGS 2026-09-13d item 9, 2026-09-13i)",
                              (*inputs, f"osm:{d.way}", *(r for r in d.end_ref if r)))
            deck_sorted = sorted(set(deck_vs))
            # THE ROAD SHAPE: the deck runs from one end's ground to the
            # other's (owner item 9 "a road shape connecting directly to the
            # apron on the east end and the road on the west side"), never
            # below the trench floor + clearance.  Interpolated per vertex
            # over the mapped way's own chord — a single flat datum at the
            # HIGHER end would stand 3.5 m over the apron at the other
            # (measured LEMD -6288: ends 609.99 west / 606.10 east).
            if len(d.end_z) == 2 and len(d.end_xy) == 2 \
                    and not any(math.isnan(z) for z in d.end_z):
                (ax, ay), (bx, by) = d.end_xy
                span2 = (bx - ax) ** 2 + (by - ay) ** 2
                for dv in deck_sorted:
                    vx, vy = planar.vertices[dv].xy
                    t = 0.0 if span2 <= 1e-9 else \
                        min(1.0, max(0.0, ((vx - ax) * (bx - ax) + (vy - ay) * (by - ay)) / span2))
                    lo = max(floor_lo, d.end_z[0] + t * (d.end_z[1] - d.end_z[0]))
                    if lo > floor_lo + 1e-9:
                        rows.append(Band(dv, lo, None, src_ends))
            # ...and where an end stands IN a governed cell, the deck meets
            # THAT SURFACE'S OWN SOLVED VALUE, not the DEM under it (the
            # apron pav92 solves to 606.6 where the DEM at the way's end
            # reads 606.1): a relational bound on the cell's nearest vertex.
            for ref in d.end_ref:
                gv = _nearest_vertex(planar, faces_by_ref.get(ref, ()), dpoly)
                if gv is None:
                    continue
                for dv in deck_sorted:
                    rows.append(Offset(dv, gv, 0.0, src_ends))
    rows.extend(pins.values())
    return rows


def _nearest_vertex(planar: PlanarMap, faces, near) -> int | None:
    """The vertex of ``faces`` standing nearest ``near`` (spec §33 (4): the
    governed surface a terrain deck's end meets — its own solved value, so
    the deck is tied to the APRON, not to the DEM under it)."""
    best = None
    for f in faces:
        for v in set(planar.ring_vertices(f.ring)):
            d = near.distance(Point(planar.vertices[v].xy))
            if best is None or d < best[0]:
                best = (d, v)
    return None if best is None else best[1]


def _rim_rows(planar: PlanarMap, airport: Airport, path: LineString, rim_vs: list[int],
              shared_with_ground: _t.Callable[[int], bool], pin: _t.Callable[..., None],
              src_rim: Source) -> list[tuple[float, list[int]]]:
    """THE RIM BY STATION (2026-09-03b L1; 2026-09-06b (1); the ground
    rule): the rim's vertices grouped by station along ``path`` (the rim
    ring itself); a vertex the governed ground shares carries the
    ground's value — the rim LEVEL with the apron, 2026-08-28c item 3,
    by the shared vertex itself (one node per coordinate) — a bare one
    is pinned at the DEM at its own station on the rim (an object
    corridor's rim likewise: the ground, 2026-09-05n-4).  No ``Flat``
    across a band: there is no band.  Returns the groups."""
    closed = len(path.coords) > 2 and path.coords[0] == path.coords[-1]
    groups = _cluster([(path.project(Point(planar.vertices[v].xy)), v) for v in rim_vs],
                      _STATION_CLUSTER_M)
    if closed and len(groups) > 1 and \
            groups[0][0] + path.length - groups[-1][0] <= _STATION_CLUSTER_M:
        # a closed rim: the station at s ≈ 0 and at s ≈ length is one
        first, last = groups[0], groups.pop()
        groups[0] = (first[0], first[1] + last[1])
    for u, vs in groups:
        for v in vs:
            if shared_with_ground(v):
                continue                  # the ground's value carries the rim
            p = path.interpolate(path.project(Point(planar.vertices[v].xy)))
            z = _dem_at(airport, p.x, p.y)
            if not math.isnan(z):
                pin(v, z, src_rim, senior=True)
    return groups


def basins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every basin row (M4b): the floor the object's DEPTH BELOW ITS RIM,
    the rim by the ground rule.

    THE FLOOR IS RELATIVE (owner RULINGS 2026-09-10ba; spec §22.1c).  The
    floor was PINNED at ``Basin.floor_z`` — ``DEM(anchor) + agl +
    plate_y``, an absolute datum the pavement's own level never reached:
    measured at LEMD's T4S pit the rim took the apron (597.3–597.9, 10an/
    10ar) while the floor stayed at 588.95, a cut of 8.3–9.0 m for a
    7.05 m object, and the plate seat put ``LEMD37``'s authored wall crest
    (−1.88) 3.1–3.8 m under the rim where 10aq reads 1.9 m.

    The rim follows the pavement and the FLOOR FOLLOWS THE RIM: every
    floor-ring vertex carries ``z_floor − z_rim = −body_depth`` against
    its NEAREST rim vertex, ``body_depth = −Basin.solid_min_y_m`` (the
    sidecar's ``body_depth_m``, the facility's own deepest genuine solid
    under R_est).  ``Diff`` is a symmetric grade cap with no offset, so
    the law is one ``Linear`` EQUALITY (``lo == hi``) at the design
    solve's LAW weight, and ``follows`` names the FLOOR vertex:
    the floor follows, the rim is never pulled down into the pit.

    A basin with no rim vertex of its own, or no measured depth, keeps the
    absolute pin — the fallback is recorded in ``STATS``."""
    if not planar.basins:
        return []
    bl = law.tables.structures.basin
    if bl.floor != "deepest_solid" or bl.rim != "ground" or bl.seat != "floor_plate":
        raise ValueError(f"basin.floor {bl.floor!r} / rim {bl.rim!r} / seat {bl.seat!r}: only "
                         "'deepest_solid' / 'ground' / 'floor_plate' are generated")
    clearance = float(bl.floor_clearance_m)
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
    relative = fallback = 0
    for b in planar.basins:
        inputs = (b.id, *(f"obj:{o}" for o in b.objects[:8]))
        src_floor = Source(GEN, "basin.floor = deepest_solid: the rendered floor plate "
                           f"(2026-08-26; 2026-09-06b (3)) - floor_clearance_m {clearance:.2f} "
                           "(2026-09-11t §24 (2))", inputs)
        src_wall = Source(GEN, "basin.rim = ground: the rim at the DEM where bare (2026-09-03b "
                          "L1; 2026-09-04d), the apron's value where shared (2026-08-28c "
                          "item 3)", inputs)
        floor_vs = {v for f in faces_by_ref.get(b.floor_ref, ())
                    for v in planar.ring_vertices(f.ring)}
        rim_vs = sorted({v for f in faces_by_ref.get(b.wall_ref, ())
                         for v in planar.ring_vertices(f.ring)} - floor_vs)
        # THE DEPTH IS THE FACILITY'S OWN BODY (10ba) PLUS THE CLEARANCE
        # (11t, §24 (2)): ``Basin.floor_below_rim_m`` is the ONE derivation
        # — ``pipeline/publication`` publishes the same call, and the
        # census joins the two.  0.0 = a basin evidencing no depth at all:
        # it keeps the absolute pin.
        depth = b.floor_below_rim_m(clearance)
        if rim_vs and depth > 1e-6:
            src_rel = Source(GEN, BASIN_FLOOR_RULING +
                             " (owner RULINGS 2026-09-10ba: the rim follows the "
                             "pavement, 10an/10ar, and the FLOOR follows the rim "
                             f"— {depth - clearance:.2f} m of object under it, 10aq"
                             f"; + {clearance:.2f} m floor_clearance_m under its "
                             "floor plate, 2026-09-11t §24 (2))", inputs)
            for v in sorted(floor_vs):
                vx, vy = planar.vertices[v].xy
                r = min(rim_vs, key=lambda u: (planar.vertices[u].xy[0] - vx) ** 2
                        + (planar.vertices[u].xy[1] - vy) ** 2)
                # ONE EQUALITY ROW (``lo == hi``): ``Diff`` caps a difference
                # symmetrically around zero and cannot carry the offset, so
                # the law is stated as a ``Linear`` equality, which
                # ``solve/design`` carries as a two-sided target at the LAW
                # weight — the strongest tier below the active set.
                #
                # NOT two opposing one-sided rows in ``[design]
                # hard_rulings``, which is what this lane measured first:
                # both halves of one equality are AT their bound at the
                # solution, so the augmented-Lagrangian polish escalates
                # them against each other and never settles.  At LEMD that
                # arm reported 1305/128088 hard rows active, max violation
                # 0.3019 m, "HARD SET NOT SETTLED", a runway projection
                # moving 0.442 m and adjudicated 580 -> 1259 airport-wide.
                rows.append(Linear(((v, 1.0), (r, -1.0)), -depth, -depth,
                                   src_rel, follows=(v,)))
            relative += 1
        else:
            for v in sorted(floor_vs):
                # the absolute pin takes the clearance too (§24 (2)): a
                # basin with no rim vertex of its own still gets a terrain
                # floor under its plate, never coplanar with it
                pin(v, b.floor_z - clearance, src_floor, senior=True)
            fallback += 1
        if len(b.wall_path) >= 3:
            path = LineString(list(b.wall_path) + [b.wall_path[0]])
            _rim_rows(planar, airport, path, rim_vs, shared_with_ground, pin, src_wall)
    rows.extend(pins.values())
    STATS["basins"] = {"floor_relative": relative, "floor_absolute_fallback": fallback}
    return rows


def rim_contacts(planar: PlanarMap, law: Law
                 ) -> list[tuple[int, str, str, list[int], set[int]]]:
    """THE RIM'S CONTACT WITH THE PAVEMENT IT SITS IN, as data —
    ``(wall face id, wall ref, pavement role, contact vertices, the
    pavement's own vertices off the rim)`` per (wall face, pavement face)
    with a shared vertex.

    A structure's rim is the ``retaining_wall`` VOID face's exterior ring
    (2026-09-06b (1); ``basin_wall:<k>`` for a basin, ``tunnel_wall`` for a
    tunnel — the SAME class, one reader).  Where that ring runs THROUGH a
    pavement face, the shared vertices are the pavement's own hole-ring
    vertices: one node, one value (09-01g)."""
    vw = view(planar, law)
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    pav = [f for f in vw.faces_of_role(tuple(r for r in pavement_roles(law)
                                             if r not in rigid))]
    pav_vs = {f.id: {v for ring in [vw.rings[f.id], *vw.holes[f.id]] for v in ring}
              for f in pav}
    out: list[tuple[int, str, str, list[int], set[int]]] = []
    for wf in planar.faces.values():
        if wf.role != WALL_ROLE:
            continue
        rim = set(planar.ring_vertices(wf.ring))
        if not rim:
            continue
        for f in pav:
            vs = pav_vs[f.id]
            contacts = sorted(rim & vs)
            if not contacts:
                continue
            own = vs - rim
            if own:
                out.append((wf.id, wf.ref, f.role, contacts, own))
    return out


def rim_level(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE RIM IS FLUSH WITH THE PAVEMENT IT SITS IN (owner RULINGS
    2026-09-10an, under 08t answer 5 "flush and tangent").

    A structure's rim vertex the governed ground SHARES gets no pin from
    :func:`_rim_rows` — "the ground's value carries the rim".  MEASURED at
    LEMD's T4S pit corner (lane ``v2pit`` round 2), that premise is false
    where the shared vertices are the pavement's own EDGE: the ring of
    ``tunnel_wall`` face 912 shares five vertices with apron ``pav16``,
    and NOT ONE ROW of any generator states a level on them — every row
    naming ``v21779`` is a one-sided CAP (``apron`` preferred tier / ring
    edge / body chord, ``pavement_ceiling``, ``no_step`` rate).  The
    apron's hole edge is therefore a FREE EDGE of the bending sheet
    (``why``: "FREE — no binding row blocks it: above its DEM, held by
    bending alone"), the per-body datum's three AFFINE rows say only where
    the body sits and how it leans, and the apron fell 0.755 m over its
    last 23.8 m into the pit — at the caps, with ``apron_preference``
    binding (dual 9.59).

    THE ROW: one ONE-WAY level row per (wall face, pavement role) — the
    MEAN of the rim's contacts against THE PAVEMENT'S OWN VALUE beside
    each of them (``pads.frontage_leaders``, the same band and the same
    inverse-distance read the pad frontage uses, so there is ONE
    derivation of "where does the pavement stand beside this vertex").
    ONE-WAY with the RIM as the follower: the crest rises to the pavement
    and never pulls the pavement down.  A LEVEL row, not a per-vertex
    pull: the rim keeps its within-shape rows and stays a member of its
    apron body's affine datum (10an), and it carries NO LOWER TARGET of
    its own — the wall's drop is the FLOOR ring's business
    (:func:`basins`' ``basin.floor`` pins, unchanged).

    A rim vertex that shares no pavement face mints nothing here and keeps
    the DEM pin of 09-03b L1."""
    from .pads import frontage_leaders
    rows: list[Row] = []
    for fid, ref, role, contacts, own in rim_contacts(planar, law):
        per = frontage_leaders(planar, contacts, own)
        if not per:
            continue
        terms: dict[int, float] = {v: 1.0 / len(contacts) for v in contacts}
        for _c, lw in per:
            for j, wj in lw:
                terms[j] = terms.get(j, 0.0) - wj / len(per)
        src = Source(GEN_RIM_LEVEL,
                     RIM_LEVEL_RULING + f" ({role}; owner 2026-09-10an: the rim "
                     "is flush with the pavement it sits in, the wall's drop is "
                     "the floor ring's)",
                     (f"wall:{fid}", ref, f"pavement:{role}"))
        # ONE-SIDED, the DOWNWARD side only: the row penalises the rim
        # standing UNDER the pavement beside it and says nothing about a
        # crest that stands at or above it.  An EQUALITY was measured first
        # and REFUTED against a consumer (``test_v2lemd4``'s pavement deck):
        # the contacts are the PAVEMENT'S OWN vertices, so the upward half
        # of the row pulls the pavement DOWN where the crest happens to sit
        # high — 0.031 m off a bridge deck's 5.1 m clearance target.  10an
        # forbids a LOWER target on the rim; it mints no upper one.
        rows.append(Linear(tuple((v, -c) for v, c in terms.items()), None, 0.0,
                           src, follows=tuple(contacts)))
    return rows


def structure_of(row: Row) -> str | None:
    """The structure kind a structure row belongs to — the prefix of its
    first input (``tunnel:-5938@0`` -> ``tunnel``, ``basin:22`` -> ``basin``);
    ``None`` for any other generator's row."""
    if row.source.generator != GEN or not row.source.inputs:
        return None
    return row.source.inputs[0].split(":", 1)[0]


def reconcile_datums(rows: list[Row], law: Law) -> tuple[list[Row], int]:
    """THE SENIOR STRUCTURE'S DATUM (``precedence.toml [structures]
    datum_order``; spawner ruling 2026-09-05): a vertex two structures pin
    keeps the pin of the structure listed first and loses the other's —
    never both hard.  Returns the rows and the number withdrawn.  A
    ``generate`` post-pass, like ``seam_exempt``: the generators are pure
    per structure and cannot see each other's pins."""
    order = {k: i for i, k in enumerate(law.tables.precedence.structures.datum_order)}
    best: dict[int, int] = {}          # vertex -> the most senior rank pinning it
    for r in rows:
        if isinstance(r, Pin):
            k = structure_of(r)
            if k is not None and k in order:
                rank = order[k]
                if r.v not in best or rank < best[r.v]:
                    best[r.v] = rank
    out: list[Row] = []
    n = 0
    for r in rows:
        if isinstance(r, Pin):
            k = structure_of(r)
            if k is not None and k in order and order[k] > best.get(r.v, order[k]):
                n += 1
                continue
        elif isinstance(r, Linear) and r.follows is not None:
            # THE RELATIVE FLOOR IS A DATUM TOO (RULINGS 2026-09-10ba): a
            # basin floor vertex a SENIOR structure pins keeps the pin and
            # loses the basin's row, exactly as it lost the basin's pin.
            k = structure_of(r)
            fvs = ((r.follows,) if isinstance(r.follows, int) else tuple(r.follows))
            if k is not None and k in order \
                    and any(order[k] > best.get(v, order[k]) for v in fvs):
                n += 1
                continue
        out.append(r)
    return out, n
