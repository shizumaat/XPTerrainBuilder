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
from ..model.planar import Face, PlanarMap, vertex_tier
from .geometry import ring_vertex_ids

__all__ = ["face_cap", "View", "view", "row_tier"]


def face_cap(law: Law, face: Face) -> tuple[float, float] | None:
    """``(longitudinal, transverse)`` for a face, or ``None`` when its
    role is ungoverned."""
    rc = role_cap(law, face.role, face.code_number, face.code_letter)
    return None if rc is None else (rc.longitudinal, rc.transverse)


@_dc.dataclass(frozen=True)
class View:
    """The generators' shared read of one planar map."""

    pm: PlanarMap
    law: Law
    xy: dict[int, tuple[float, float]]
    rings: dict[int, list[int]]                 # face -> outer ring ids (open)
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
        caps[fid] = face_cap(law, f)
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
