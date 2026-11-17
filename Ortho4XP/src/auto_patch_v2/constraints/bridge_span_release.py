"""THE PAGE A MAPPED BRIDGE CARRIES IS NOT GRADED OVER THE SPAN (issue
#2073; owner 2026-11-13T22:48Z: "keep the lower road cut, and don't try to
grade the bridge at all, it should be handled by a bridge object or x-plane
road") -- an assembly post-pass.

``PlanarMap.bridge_span`` (``airport/bridge_span``) names, per groundside
road / lot face a deckless mapped bridge carries, the face's SPAN vertices:
the page's pieces over the bridge, standing on the ground under it.  The
bridge is X-Plane's to draw, so the page grades nothing over the span:
every GRADE row (a ``Diff``, whichever generator minted it -- within-shape,
the 5 % ceiling's twin, the pavement cap's fallback) between two vertices
of a carried face, one of them a span vertex, is WITHDRAWN.  The approach on
the bank keeps its own rows and follows its ground; a span vertex keeps the
rows of every other pavement face it stands on, and one no such face holds
takes ITS GROUND as its target (``Vertex.dem_z``: the ground under the
bridge, ``airport/bridge_ground``'s where the DEM carries the deck) -- one
``Linear`` at the law weight, the road ramp's own target form.  A pavement
vertex takes no DEM pull (08t (1)), so without it the objective alone held
a freed span vertex: MEASURED ESSA, ``dsf:pol192`` v10585 under another
deckless bridge stood +4.46 m over its ground.  A row is kept when

* either end is a §20b stage-1 (airside) vertex (airside is king);
* another pavement face, not carried, holds both its ends (the road the
  bridge passes over keeps its own grade on an edge it shares).

MEASURED ESSA (#2073, lessa2 capture replayed at 9e809287b): lot face 580
of ``dsf:pol192`` held the west bank top at 24.2-24.3 m on lidar 30.3 m
(5 % rows to its span pieces in the motorway cutting at 22.9 m), and road
way -2811's foot beside it stood 2.25 m under its lidar.  Widening the rows
to the ground's own difference instead (``public_road_release``'s rule)
moved the foot 0.45 m only: a span vertex the cutting holds low still held
its approach within the ground step of it."""
from __future__ import annotations

import typing as _t

from ..geom import exact
from ..law import Law
from ..law.tables import pavement_roles
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap, face_vertex_set
from .roads import stage_one_vertices

__all__ = ["span_release", "span_lifts", "GEN"]

GEN = "bridge_span_release"
#: the ruling of a free span vertex's ground target
_GROUND_RULING = ("bridge span ground (owner 2026-11-13T22:48Z on #1939 site 3: "
                 "\"don't try to grade the bridge at all\"; #2073)")


class _Released:
    """The pair test over the carried faces of one map."""

    def __init__(self, planar: PlanarMap, law: Law):
        spans = getattr(planar, "bridge_span", None) or {}
        self.planar = planar
        self.faces: dict[int, tuple[frozenset, frozenset]] = {}
        self.by_v: dict[int, list[int]] = {}
        self.held: set[int] = set()
        if not spans:   # a map with no span reads no law
            return
        air = stage_one_vertices(planar, law)
        pav = set(pavement_roles(law))
        for fid, span in spans.items():
            if fid not in planar.faces:
                continue
            vs = frozenset(face_vertex_set(planar, planar.faces[fid]) - air)
            sp = frozenset(span) & vs
            if not sp:
                continue
            self.faces[int(fid)] = (sp, vs)
            for v in vs:
                self.by_v.setdefault(v, []).append(int(fid))
        self.held = {fid for fid, f in planar.faces.items()
                     if f.role in pav and fid not in self.faces}

    def free_span(self) -> list[int]:
        """The span vertices no other (not carried) pavement face holds."""
        out: set[int] = set()
        for sp, _vs in self.faces.values():
            out.update(v for v in sp
                       if not set(self.planar.vertices[v].incident_faces) & self.held)
        return sorted(out)

    def __bool__(self) -> bool:
        return bool(self.faces)

    def __call__(self, a: int, b: int) -> bool:
        """Whether ``a``-``b`` is withdrawn (module docstring)."""
        if not any(b in self.faces[f][1] and (a in self.faces[f][0] or b in self.faces[f][0])
                   for f in self.by_v.get(a, ())):
            return False
        va, vb = self.planar.vertices[a], self.planar.vertices[b]
        common = set(va.incident_faces) & set(vb.incident_faces)
        return not (common & self.held)


def span_release(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                 ) -> tuple[list[Row], int]:
    """``(rows, withdrawn)`` (module docstring)."""
    rel = _Released(planar, law)
    if not rel:
        return list(rows), 0
    out = [r for r in rows if not (isinstance(r, Diff) and rel(r.a, r.b))]
    n = len(rows) - len(out)
    for v in rel.free_span():
        z = _ground(planar, v)
        ref = planar.faces[next(iter(planar.vertices[v].incident_faces))].ref
        out.append(Linear(((v, 1.0),), z, z, Source(GEN, _GROUND_RULING, (f"vertex:{v}", ref))))
    return out, n


def _ground(planar: PlanarMap, v: int) -> float:
    return float(planar.vertices[v].dem_z)


def span_lifts(planar: PlanarMap, law: Law) -> dict[int, float]:
    """face id -> the steepest ground grade over a withdrawn pair of the
    face, for the census's lift (``pipeline/publication.lifted_caps``: the
    lift is the tag's presence, the value names the ground it follows) --
    the carried faces only."""
    rel = _Released(planar, law)
    out: dict[int, float] = {}
    for fid, (_sp, vs) in rel.faces.items():
        vl = sorted(vs)
        g = 0.0
        for i, a in enumerate(vl):
            ax, ay = planar.vertices[a].xy
            for b in vl[i + 1:]:
                if not rel(a, b):
                    continue
                bx, by = planar.vertices[b].xy
                d = exact.hypot(ax - bx, ay - by)
                if d > 0.0:
                    g = max(g, abs(_ground(planar, a) - _ground(planar, b)) / d)
        out[fid] = round(g, 6)
    return out
