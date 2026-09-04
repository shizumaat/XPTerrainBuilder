"""SENIORITY FOLLOWS FROM BEING GOVERNED (RULINGS 2026-09-03i, generalising
03h) — the two tiers, DERIVED from the tables, never a role list in code.

A role is GOVERNED when the law states a grade cap for it
(``tables.role_cap`` is not ``None``); everything else — pads, strips,
walls, clearances, cuts — is UNGOVERNED and takes its level from what it
touches.  A new surface class without a cap is junior by omission.

Also here: the ONE shared read of the planar map every generator needs
(:class:`View`): rings as vertex chains, coordinates, the roles and the
governed cap at each vertex, the breakline chains, the spine (centreline)
vertices.  Built once per map, read by every generator.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..law.tables import role_cap, role_family, role_side
from ..model.planar import Face, PlanarMap
from .geometry import ring_vertex_ids

__all__ = ["is_governed", "governed_roles", "ungoverned_roles", "face_cap",
           "View", "view"]


def is_governed(law: Law, role: str, code_number: int | None = None,
                code_letter: str | None = None) -> bool:
    """Whether the law states a grade cap for ``role`` (03i)."""
    return role_cap(law, role, code_number, code_letter) is not None


def governed_roles(law: Law) -> tuple[str, ...]:
    """The governed tier in the tables' stated order (03i)."""
    reg = law.tables.precedence.roles
    order = law.tables.precedence.order
    gov = [r for r in order if is_governed(law, r)]
    gov += sorted(r for r in reg if r not in order and is_governed(law, r))
    return tuple(gov)


def ungoverned_roles(law: Law) -> tuple[str, ...]:
    """Every registered role with no cap — junior by omission (03i)."""
    return tuple(sorted(r for r in law.tables.precedence.roles
                        if not is_governed(law, r)))


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
