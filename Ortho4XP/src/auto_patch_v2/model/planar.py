"""The PLANAR MAP (plan §1 row 4) — faces, edges, vertices, breaklines.

Built ONCE by ``planar/`` (M1) from the airport inputs and the roles;
every later stage reads it, none mutates it.  Shared edges exist once,
so there are no welds, no annuli and no T-vertices BY CONSTRUCTION — the
class the mesh pays for (Appendix B §4) cannot be emitted.

Invariants (checked by :func:`validate`):
  I1  every vertex id is unique and its ``key`` (canonical 11-dp lat/lon
      identity) is unique — two vertices never share a coordinate;
  I2  every edge appears ONCE; ``(a, b)`` with ``a < b``; no self-loop;
      no two edges join the same vertex pair;
  I3  each edge names its left and right face (``None`` = outside the
      map); an edge with two ``None`` faces is an error; an edge with
      equal faces is an error;
  I4  each face's ring is a closed cycle of its own edges; the face is
      on the stated side of every ring edge; each hole likewise;
  I5  every vertex lists ALL faces incident to it (`incident_faces`)
      and that list equals the faces of its edges — a T-vertex (a vertex
      lying on an edge that does not end there) is impossible because a
      vertex on a face boundary must be an endpoint of that face's ring
      edges;
  I6  every breakline is a chain of existing edges (kind ``breakline``
      or ``centerline``), consecutive edges sharing a vertex;
  I7  every vertex has a DEM sample (``dem_z`` not None) — a vertex with
      no DEM is an error at build, never a value the solver invents
      (plan §2).

No shapely / numpy: tuples and dicts.  The producers keep an STRtree and
cached unions beside the map; the map itself is the record.
"""
from __future__ import annotations

import dataclasses as _dc
import enum
import typing as _t

from .frame import XY, Key
from .structures import Basin, Tunnel

__all__ = ["NO_SHAPE", "EdgeKind", "Vertex", "Edge", "Face", "Breakline",
           "ShapeJoint", "PlanarMap", "PlanarError", "validate", "vertex_tier"]

#: Label of a vertex no shape owns (``shape_of_vertex``).  It lives with
#: the RECORD, not with the pass that fills it (``planar/shapes.py`` — which
#: re-exports it): the solve reads shape membership for the per-body datum
#: (RULINGS 2026-09-09v) and may not import ``planar`` (M0 §1's direction).
NO_SHAPE = -1


class EdgeKind(str, enum.Enum):
    """Why an edge exists."""

    BOUNDARY = "boundary"        # a face outline (pavement / pad / zone edge)
    BREAKLINE = "breakline"      # an interior grade break (runway profile station, spine)
    CENTERLINE = "centerline"    # a taxi / runway / road centreline chord
    ZONE = "zone"                # an adjacent-ground zone boundary (zone 1|2, 2|3)


@_dc.dataclass(frozen=True)
class Vertex:
    """One map vertex.  ``key`` is the canonical lat/lon identity (the
    ONLY join key, memory ``canonical-identity-join``); ``xy`` the frame
    position; ``dem_z`` the DEM sample; ``incident_faces`` every face
    touching it (I5)."""

    id: int
    xy: XY
    key: Key
    dem_z: float | None
    incident_faces: tuple[int, ...]


@_dc.dataclass(frozen=True)
class Edge:
    """One map edge, existing once (I2).  ``left_face`` / ``right_face``
    are face ids or ``None`` (outside); left is to the left walking from
    ``a`` to ``b``."""

    id: int
    a: int
    b: int
    left_face: int | None
    right_face: int | None
    kind: EdgeKind

    @property
    def length_key(self) -> tuple[int, int]:
        """The unordered vertex pair."""
        return (self.a, self.b) if self.a < self.b else (self.b, self.a)


@_dc.dataclass(frozen=True)
class Face:
    """One map face.  ``role`` is a registered law role; ``ref`` the input
    id it came from (apt.dat pavement id, OSM way id, building id, or a
    derived name such as ``adjacent_ground:<pavement>:zone2``);
    ``ring`` the outer cycle of edge ids in walking order; ``holes`` the
    inner cycles; ``code_number`` / ``code_letter`` the class the law
    keys by (runway family / taxi family), else ``None``."""

    id: int
    role: str
    ref: str
    ring: tuple[int, ...]
    holes: tuple[tuple[int, ...], ...]
    code_number: int | None = None
    code_letter: str | None = None
    side: str = "airside"


@_dc.dataclass(frozen=True)
class Breakline:
    """A chain of edges the solver grades ALONG (longitudinal) and the
    emitter keeps as a constrained line.  ``kind`` names the producer:
    ``runway_profile``, ``taxi_centerline``, ``road_centerline``,
    ``crown_spine``, ``drainage_spine``, ``structure_outline``."""

    id: int
    kind: str
    ref: str
    edges: tuple[int, ...]
    #: The chain's code letter (taxi centrelines; RULINGS 2026-09-04t-3:
    #: a taxiway's letter applies per STRETCH — the breakline carries its
    #: own chain's letter, never a bounding face's).
    code_letter: str | None = None

    def vertices(self, pm: "PlanarMap") -> tuple[int, ...]:
        """The vertex chain in order (I6 guarantees adjacency)."""
        out: list[int] = []
        for i, eid in enumerate(self.edges):
            e = pm.edges[eid]
            if i == 0:
                nxt = pm.edges[self.edges[1]] if len(self.edges) > 1 else None
                first = e.a if nxt is None or e.b in (nxt.a, nxt.b) else e.b
                out.append(first)
            out.append(e.b if out[-1] == e.a else e.a)
        return tuple(out)


@_dc.dataclass(frozen=True)
class ShapeJoint:
    """ONE SHAPE JOINT (owner RULINGS 2026-09-08k; ``planar/shapes.py``):
    the declared boundary between two SHAPES — the label-boundary contour
    through the faces whose vertices carry both labels (no vertex is
    split: the mesh builds the step between the two nodes), or the
    midline of a GAP the step readers price (``gap``).  ``points`` in the
    frame, ``points_ll`` as lat/lon (the line the sidecar declares),
    ``pairs`` the vertex pairs across it whose largest |Δz| is the declared
    step, ``shapes`` the two shape ids."""

    id: int
    points: tuple[XY, ...]
    points_ll: tuple[tuple[float, float], ...]
    pairs: tuple[tuple[int, int], ...]
    length_m: float
    roles: tuple[str, ...]
    shapes: tuple[int, int] = (-1, -1)
    gap: bool = False


@_dc.dataclass(frozen=True)
class RoadRamp:
    """A ROAD CROSSING from one shape to another (owner RULINGS
    2026-09-08r-2; ``planar/shapes.py::_label_roads``): it belongs to
    NEITHER shape — every vertex unlabelled, every row kept — and RAMPS
    along its length at its own row law.  ``contacts_a`` / ``contacts_b``
    are its vertices shared with the two shapes, ``length_m`` the axis
    distance between the two contact centroids; the built |Δz| over it is
    the report's ramp (``pipeline/shapes.py::joint_steps``)."""

    face: int
    ref: str
    shapes: tuple[int, int]
    contacts_a: tuple[int, ...]
    contacts_b: tuple[int, ...]
    length_m: float


@_dc.dataclass(frozen=True)
class PlanarMap:
    """The map.  Mappings are id -> record; ids are dense from 0."""

    icao: str
    vertices: _t.Mapping[int, Vertex]
    edges: _t.Mapping[int, Edge]
    faces: _t.Mapping[int, Face]
    breaklines: _t.Mapping[int, Breakline]
    #: Vertices on the edge of a tile-seam band (``law.emit.seam``; M3a,
    #: additive): the graticule line the airport crosses is cut out of
    #: the map as a band the DEM owns, and these vertices bound it.
    seam_vertices: frozenset[int] = frozenset()
    #: The tunnel structures the map's ramp / wall / deck faces belong to
    #: (M4, additive): the generator and the verifier read the record,
    #: never re-derive the corridor from rings.
    structures: tuple[Tunnel, ...] = ()
    #: The basin facilities (M4b, additive): floor + wall faces per record.
    basins: tuple[Basin, ...] = ()
    #: THE FIT TARGET WHERE IT IS NOT THE DEM (RULINGS 2026-09-04t-4, M3c,
    #: additive): vertex id -> the elevation the objective pulls it to.
    #: A road-family vertex prefers the CORE's clamped, laterally-levelled
    #: road profile (``airport/road_profile.py``); every other vertex is
    #: absent here and keeps ``Vertex.dem_z``.  ``dem_z`` itself stays the
    #: DEM sample: seams, reports and readers compare against terrain.
    preferred_z: _t.Mapping[int, float] = _dc.field(default_factory=dict)
    #: THE TAXI CHAIN'S TARGET PROFILE (owner RULINGS 2026-09-10v (1);
    #: spec §8.6, ``constraints/taxi_trend.py``): vertex id -> the ground's
    #: LONG-WAVE TREND along that vertex's taxi centreline chain, shifted
    #: linearly through the chain's runway contacts.  A channel of its OWN,
    #: never ``preferred_z``: this target is priced WEAK
    #: (``[design] taxi_trend``, below ``body_datum``) while ``preferred_z``
    #: carries the runway's ``chord`` and the core's ``road`` profile.  A
    #: runway-contact vertex is absent (the runway owns its value).
    taxi_trend_z: _t.Mapping[int, float] = _dc.field(default_factory=dict)
    #: THE APRON BODY'S TARGET SURFACE (owner RULINGS 2026-09-10ar; spec
    #: §8.7, ``constraints/apron_trend.py``): vertex id -> the ground's 2-D
    #: LONG-WAVE TREND under it — a moving quadratic SURFACE fit of the
    #: production DEM over the same window.  Published only for an apron
    #: body whose plan DIAMETER exceeds that window; such a body carries NO
    #: affine ``body_datum`` rows, and a body at or under the window keeps
    #: them and is absent here.  Its own channel, priced weak
    #: (``[design] apron_trend``), like ``taxi_trend_z``.
    apron_trend_z: _t.Mapping[int, float] = _dc.field(default_factory=dict)
    #: THE GROUNDSIDE ROAD'S RAMP TARGET (owner RULINGS 2026-09-13j item 5,
    #: ruled 13aj; spec §37 (6), ``constraints/road_ramp.py``): vertex id ->
    #: ``max(DEM(s), z_contact - road_cap * s)`` along the road's own route
    #: from its airside contacts.  Its own channel, priced at the DESIGN-
    #: TARGET weight (``[design] law``) with a HARD ceiling a visual
    #: threshold above it, and it SUPERSEDES ``preferred_z`` for the
    #: vertices it governs (which are therefore absent from that mapping).
    road_ramp_z: _t.Mapping[int, float] = _dc.field(default_factory=dict)
    #: §37 (7) THE ROAD'S ROUTE FRAME (owner RULINGS 2026-09-13av;
    #: ``airport/road_ramp.road_route_frame``): road-family ring vertex ->
    #: ``(route id, station s along that route, signed lateral t)``.  A
    #: road PAIR is priced over ``s`` — the route, never the plan chord —
    #: and a pair whose two vertices sit on DIFFERENT routes is not a pair
    #: (a switchback's two branches).  Published to the sidecar so the
    #: verify reader and the v1 census pair the same way the generator
    #: does; empty on a map the publisher never ran over (the chord law).
    road_route_frame: _t.Mapping[int, tuple[int, float, float]] = _dc.field(
        default_factory=dict)
    #: THE SHAPES (owner RULINGS 2026-09-08k, ``planar/shapes.py``): vertex
    #: id -> shape id (``NO_SHAPE`` = -1 for a vertex of no shape), face id
    #: -> shape id (a pad's majority shape), and the declared joints — the
    #: only places a step is lawful.  A generator's row whose vertices carry
    #: two shape ids is dropped at assembly (``pipeline/shapes.py``).
    shape_of_vertex: _t.Mapping[int, int] = _dc.field(default_factory=dict)
    shape_of_face: _t.Mapping[int, int] = _dc.field(default_factory=dict)
    shape_joints: tuple[ShapeJoint, ...] = ()
    #: The roads crossing from one shape to another (owner RULINGS
    #: 2026-09-08r-2): unlabelled, ramping, never a joint.
    road_ramps: tuple[RoadRamp, ...] = ()
    #: THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19,
    #: additive): the edge SEGMENTS the adjacent-ground clip made, as
    #: frame polylines — the boundary beyond which there is no patch and
    #: NO BANK (the DEM's own slope is the bank) — and the rule that ended
    #: each region, by region ref (``crest`` / ``road``).
    terrain_edges: tuple[tuple[tuple[float, float], ...], ...] = ()
    edge_kind_of_ref: _t.Mapping[str, str] = _dc.field(default_factory=dict)
    #: THE TILE-SEAM BANDS (§38 (3); owner RULINGS 2026-09-13ah/13am), as
    #: frame polygon rings — the SINGLE derivation is
    #: ``planar/overlay.seam_bands``, recorded here so every downstream
    #: reader takes THAT band and never re-derives the graticule.  The band
    #: is DRAPED DEM: no face lives in it (``dropped_seam_faces``), its
    #: edge vertices are ``seam_vertices``, and ``emit/bank.py`` derives no
    #: bank inside it and unions it into the coverage before the collar.
    seam_band_rings: tuple[tuple[tuple[float, float], ...], ...] = ()

    def roles_at(self, v: int) -> tuple[str, ...]:
        """THE VERTEX-OWNERSHIP VIEW (RULINGS 2026-09-04q-3): the roles of
        every face touching vertex ``v`` (I5 — the record, never a
        re-derivation); which of them OWNS the value is the law's question
        (``law.tables.senior_role`` / ``tier_of_roles``)."""
        return tuple(self.faces[f].role for f in self.vertices[v].incident_faces)

    def edges_of_vertex(self) -> dict[int, tuple[int, ...]]:
        """Vertex id -> incident edge ids (derived, not stored)."""
        acc: dict[int, list[int]] = {v: [] for v in self.vertices}
        for e in self.edges.values():
            acc[e.a].append(e.id)
            acc[e.b].append(e.id)
        return {k: tuple(v) for k, v in acc.items()}

    def faces_of_edge(self, eid: int) -> tuple[int, ...]:
        """The one or two faces an edge separates."""
        e = self.edges[eid]
        return tuple(f for f in (e.left_face, e.right_face) if f is not None)

    def ring_vertices(self, cycle: _t.Sequence[int]) -> tuple[int, ...]:
        """The vertex ids of an edge cycle in walking order (first not
        repeated) — I4 guarantees consecutive edges share a vertex."""
        if not cycle:
            return ()
        if len(cycle) == 1:
            e = self.edges[cycle[0]]
            return (e.a, e.b)
        e0, e1 = self.edges[cycle[0]], self.edges[cycle[1]]
        cur = e0.a if e0.b in (e1.a, e1.b) else e0.b
        out = [cur]
        for eid in cycle:
            e = self.edges[eid]
            cur = e.b if cur == e.a else e.a
            out.append(cur)
        if out[-1] == out[0]:
            out.pop()
        return tuple(out)


def vertex_tier(pm: PlanarMap, v: int, tier_of: _t.Mapping[str, int],
                lowest: int) -> int:
    """The tier a VERTEX belongs to: the most SENIOR (smallest) tier of any
    face touching it, ``lowest`` where no face does — a shared vertex is
    owned by its senior surface (``law.tables.tier_of_roles`` over
    :meth:`PlanarMap.roles_at`)."""
    best = lowest
    for r in pm.roles_at(v):
        k = tier_of[r]
        if k < best:
            best = k
    return best


class PlanarError(ValueError):
    """An invariant I1..I7 is broken; the message names the offender."""


def validate(pm: PlanarMap) -> None:
    """Check I1..I7; raise :class:`PlanarError` on the first breach.
    The producer calls this once at build; the solver and the emitters
    trust the map afterwards."""
    keys: dict[Key, int] = {}
    for vid, v in pm.vertices.items():
        if v.id != vid:
            raise PlanarError(f"I1 vertex {vid}: id mismatch {v.id}")
        if v.key in keys:
            raise PlanarError(f"I1 vertices {keys[v.key]} and {vid} share "
                              f"key {v.key}")
        keys[v.key] = vid
        if v.dem_z is None:
            raise PlanarError(f"I7 vertex {vid}: no DEM sample")
    pairs: dict[tuple[int, int], int] = {}
    for eid, e in pm.edges.items():
        if e.id != eid:
            raise PlanarError(f"I2 edge {eid}: id mismatch {e.id}")
        if e.a == e.b:
            raise PlanarError(f"I2 edge {eid}: self-loop at {e.a}")
        if e.a not in pm.vertices or e.b not in pm.vertices:
            raise PlanarError(f"I2 edge {eid}: unknown vertex")
        if e.length_key in pairs:
            raise PlanarError(f"I2 edges {pairs[e.length_key]} and {eid} "
                              f"join the same pair {e.length_key}")
        pairs[e.length_key] = eid
        if e.left_face is None and e.right_face is None:
            raise PlanarError(f"I3 edge {eid}: no face on either side")
        if e.left_face == e.right_face:
            raise PlanarError(f"I3 edge {eid}: same face both sides")
        for f in (e.left_face, e.right_face):
            if f is not None and f not in pm.faces:
                raise PlanarError(f"I3 edge {eid}: unknown face {f}")
    face_vertices: dict[int, set[int]] = {}
    for fid, f in pm.faces.items():
        if f.id != fid:
            raise PlanarError(f"I4 face {fid}: id mismatch {f.id}")
        for cycle in (f.ring, *f.holes):
            _check_cycle(pm, fid, cycle)
            for eid in cycle:
                e = pm.edges[eid]
                face_vertices.setdefault(fid, set()).update((e.a, e.b))
    incident: dict[int, set[int]] = {v: set() for v in pm.vertices}
    for fid, vs in face_vertices.items():
        for v in vs:
            incident[v].add(fid)
    for vid, v in pm.vertices.items():
        if set(v.incident_faces) != incident[vid]:
            raise PlanarError(f"I5 vertex {vid}: incident_faces "
                              f"{sorted(v.incident_faces)} != faces of its "
                              f"edges {sorted(incident[vid])}")
    for bid, b in pm.breaklines.items():
        if b.id != bid:
            raise PlanarError(f"I6 breakline {bid}: id mismatch")
        if not b.edges:
            raise PlanarError(f"I6 breakline {bid}: empty")
        for e1, e2 in zip(b.edges, b.edges[1:]):
            if e1 not in pm.edges or e2 not in pm.edges:
                raise PlanarError(f"I6 breakline {bid}: unknown edge")
            a, c = pm.edges[e1], pm.edges[e2]
            if not {a.a, a.b} & {c.a, c.b}:
                raise PlanarError(f"I6 breakline {bid}: edges {e1},{e2} "
                                  "do not share a vertex")
        if b.edges[0] not in pm.edges:
            raise PlanarError(f"I6 breakline {bid}: unknown edge")


def _check_cycle(pm: PlanarMap, fid: int, cycle: tuple[int, ...]) -> None:
    """I4: ``cycle`` is a closed walk of edges each bounding face ``fid``."""
    if len(cycle) < 3:
        raise PlanarError(f"I4 face {fid}: cycle shorter than 3 edges")
    prev_end: int | None = None
    first_start: int | None = None
    for i, eid in enumerate(cycle):
        if eid not in pm.edges:
            raise PlanarError(f"I4 face {fid}: unknown edge {eid}")
        e = pm.edges[eid]
        if fid not in (e.left_face, e.right_face):
            raise PlanarError(f"I4 face {fid}: edge {eid} does not bound it")
        if prev_end is None:
            nxt = pm.edges[cycle[(i + 1) % len(cycle)]]
            start = e.a if e.b in (nxt.a, nxt.b) else e.b
            first_start = start
            prev_end = e.b if start == e.a else e.a
            continue
        if prev_end == e.a:
            prev_end = e.b
        elif prev_end == e.b:
            prev_end = e.a
        else:
            raise PlanarError(f"I4 face {fid}: edge {eid} does not continue "
                              f"from vertex {prev_end}")
    if prev_end != first_start:
        raise PlanarError(f"I4 face {fid}: cycle does not close")
