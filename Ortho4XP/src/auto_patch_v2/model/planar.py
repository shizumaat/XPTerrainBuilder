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

__all__ = ["EdgeKind", "Vertex", "Edge", "Face", "Breakline",
           "PlanarMap", "PlanarError", "validate"]


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
