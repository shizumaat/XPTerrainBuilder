"""THE GENERATORS' SHARED READ of the planar map (:class:`View`): rings
as vertex chains, coordinates, the governed cap at each face and vertex,
the breakline chains, the spine (centreline) vertices.  Built once per
map, read by every generator.

SENIORITY FOLLOWS FROM BEING GOVERNED (RULINGS 2026-09-03i) — the tier
derivation is a function of ``precedence.toml`` and lives in
``law.tables`` (``is_governed`` / ``governed_roles`` / ``tiers`` /
``role_tier``); the vertex-ownership view is ``model.planar.roles_at`` /
``vertex_tier`` (RULINGS 2026-09-04q-3: ``solve/`` reads law and model,
never a generator).  This module exports nothing v2-upward.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..law.tables import role_cap, role_family, role_side
from ..model.constraints import Diff, Flat, Linear, Offset, Pin, Row
from ..model.planar import Face, PlanarMap, face_vertex_ids, vertex_tier
from .geometry import ring_vertex_ids

__all__ = ["cap_of", "face_cap", "View", "view", "row_tier"]


def cap_of(pm: PlanarMap | None, law: Law, ref: str,
           code_number: int | None = None, code_letter: str | None = None
           ) -> float | None:
    """§50.1 (4) THE SOLVE-SIDE ACCESSOR of the runway's EFFECTIVE
    longitudinal cap: ``pm.runway_caps[ref].cap`` where the yield
    derivation (``constraints/runway_yield.py``) published one, else the
    table's own value.  For a ``runway_crossing`` face (``ref = "A+B"``)
    the MAX over its runways — the crossing stands in both runways'
    profiles and the looser of the two is the one that can be built.

    Reads ``pm.runway_caps`` and the law table only, so every generator
    may import it without reaching the derivation (module ordering,
    §50.6).  ``None`` where the table states no runway cap."""
    rc = role_cap(law, "runway", code_number, code_letter)
    table = None if rc is None else rc.longitudinal
    caps = getattr(pm, "runway_caps", None) if pm is not None else None
    if not caps:
        return table
    vals = [float(caps[r].cap) for r in (ref.split("+") if "+" in ref
                                         else [ref]) if r in caps]
    if not vals:
        return table
    got = max(vals)
    return got if table is None else max(table, got)


def face_cap(law: Law, face: Face, pm: PlanarMap | None = None
             ) -> tuple[float, float] | None:
    """``(longitudinal, transverse)`` for a face, or ``None`` when its
    role is ungoverned.

    §50.1 (4): with ``pm`` given, a RUNWAY-FAMILY face answers through
    :func:`cap_of`, so the yielded cap reaches every ``vw.caps`` reader
    with no edit of theirs.  The parameter is optional-last and the
    transverse cap never moves (the yield is a LONGITUDINAL law)."""
    rc = role_cap(law, face.role, face.code_number, face.code_letter)
    if rc is None:
        return None
    lon = rc.longitudinal
    if pm is not None and role_family(law, face.role) == "runway":
        got = cap_of(pm, law, face.ref, face.code_number, face.code_letter)
        if got is not None:
            lon = got
    return (lon, rc.transverse)


@_dc.dataclass(frozen=True)
class View:
    """The generators' shared read of one planar map."""

    pm: PlanarMap
    law: Law
    xy: dict[int, tuple[float, float]]
    rings: dict[int, list[int]]                 # face -> outer ring ids (open) — RING CHORDS only; a per-vertex law reads ``face_vertices``
    holes: dict[int, list[list[int]]]           # face -> hole rings (open)
    caps: dict[int, tuple[float, float] | None]  # face -> (cL, cT) | None
    vertex_faces: dict[int, tuple[int, ...]]
    vertex_cap: dict[int, float | None]         # strictest governed cL at a vertex
    spine: dict[int, str]                       # vertex -> breakline kind (centreline / profile)
    chains: dict[int, list[int]]                # breakline id -> vertex chain
    pavement_vertices: frozenset[int]           # any governed-role face touches it

    def dist(self, a: int, b: int) -> float:
        (ax, ay), (bx, by) = self.xy[a], self.xy[b]
        return math.hypot(ax - bx, ay - by)

    def face_ring_xy(self, fid: int) -> list[tuple[float, float]]:
        return [self.xy[v] for v in self.rings[fid]]

    def face_vertices(self, fid: int) -> list[int]:
        """THE face's vertex set — its outer ring AND its hole rings, each
        vertex once (``model.planar.face_vertex_ids``, the one accessor the
        verifier's ``Shape.vertex_ids`` shares).  A law stated per VERTEX of
        a face reads this; ``rings[fid]`` alone is the outer ring's CHORDS."""
        return face_vertex_ids(self.rings[fid], self.holes[fid])

    def faces_of_role(self, roles: _t.Container[str]) -> list[Face]:
        return [f for f in self.pm.faces.values() if f.role in roles]

    def family(self, role: str) -> str:
        return role_family(self.law, role)

    def side(self, role: str) -> str:
        return role_side(self.law, role)


_CACHE: dict[int, tuple[PlanarMap, View]] = {}


def view(pm: PlanarMap, law: Law) -> View:
    """The (cached) view of ``pm`` under ``law``."""
    hit = _CACHE.get(id(pm))
    if hit is not None and hit[0] is pm and hit[1].law is law:
        return hit[1]
    xy = {vid: v.xy for vid, v in pm.vertices.items()}
    rings: dict[int, list[int]] = {}
    holes: dict[int, list[list[int]]] = {}
    caps: dict[int, tuple[float, float] | None] = {}
    for fid, f in pm.faces.items():
        rings[fid] = ring_vertex_ids(pm, f.ring)
        holes[fid] = [ring_vertex_ids(pm, h) for h in f.holes]
        caps[fid] = face_cap(law, f, pm)      # §50.1 (4): the yielded cap
    vertex_faces = {vid: v.incident_faces for vid, v in pm.vertices.items()}
    vertex_cap: dict[int, float | None] = {}
    pav: set[int] = set()
    for vid, fids in vertex_faces.items():
        best: float | None = None
        for fid in fids:
            c = caps[fid]
            if c is None:
                continue
            pav.add(vid)
            best = c[0] if best is None else min(best, c[0])
        vertex_cap[vid] = best
    chains: dict[int, list[int]] = {}
    spine: dict[int, str] = {}
    for bid, b in pm.breaklines.items():
        ch = list(b.vertices(pm))
        chains[bid] = ch
        for v in ch:
            spine.setdefault(v, b.kind)
    vw = View(pm, law, xy, rings, holes, caps, vertex_faces, vertex_cap,
              spine, chains, frozenset(pav))
    _CACHE.clear()
    _CACHE[id(pm)] = (pm, vw)
    return vw



def row_tier(pm: PlanarMap, row: Row, tier_of: _t.Mapping[str, int], lowest: int) -> int:
    """THE ROW'S TIER (RULINGS 2026-09-04i): a row minted FOR A FACE
    (``Source.inputs`` ``face:<id>``) belongs to that face's role — an apron
    ring edge shared with a taxiway is still the APRON's row; any other row
    belongs to the most JUNIOR of its vertices, a vertex being owned by the
    most SENIOR surface touching it (``model.planar.vertex_tier``).

    The LAW-ORDER ATTRIBUTION, kept when the tier LADDER was deleted with the
    LP (RULINGS 2026-09-08t): the design surface has no ladder, but the
    reports and the twins still name which surface a row belongs to.
    """
    for inp in row.source.inputs:
        if inp.startswith("face:"):
            try:
                return tier_of[pm.faces[int(inp[5:])].role]
            except (KeyError, ValueError):
                break
    if isinstance(row, Pin):
        vs: tuple[int, ...] = (row.v,)
    elif isinstance(row, (Diff, Offset)):
        vs = (row.a, row.b)
    elif isinstance(row, Linear):
        vs = tuple(v for v, _c in row.terms)
    elif isinstance(row, Flat):
        vs = row.group
    else:
        vs = (row.v,)
    return max((vertex_tier(pm, v, tier_of, lowest) for v in vs), default=lowest)
