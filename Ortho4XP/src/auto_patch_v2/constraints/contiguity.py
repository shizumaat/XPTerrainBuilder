"""LATERAL CONTIGUITY, per station (family ``lateral_contiguity``; owner
FINAL 2026-08-02 clause 2; RULINGS 2026-08-25b, 2026-08-28 Amendment 2
"the cap lives at the STATION"; ``law/emit.toml [lateral_contiguity]``).

A road-family ring (``families.road_cross_section.roles``) is priced at
STATIONS along its own long axis (``geometry.long_axis``, the minimum-
area rectangle — the same convention the census walks).  At each
station a perpendicular probe ``± probe_m`` cuts every governed
pavement ring; the cut pieces that TOUCH (gap ≤ ``gap_tol_m``) merge
into runs; the run holding the station is the laterally-contiguous
cross-section, and its cap is the STRICTEST longitudinal cap of any
class in it (a foreign piece shorter than ``min_member_m`` is a graze,
not a member).  A station inside a runway strip footprint has no verdict
(clause 5: the strip law supersedes there); a station off the ring has
none either.

THE ROAD IS BOUND AT ITS STATIONS' CAPS: every pair on the ring at the
strictest cap of the stations nearest its two endpoints (v1 ``cap_at``,
nearest-station), never looser than the face's own cap; the vector is
PUBLISHED (sidecar ``station_caps`` as ``[lat, lon, cap]``) so the
census's fourth reader prices each station against the cap it was built
to instead of re-deriving one under its own frame (measured 5j: +100
rows at CYXY and SPJC without it).  The way-level ``o4_grade_law_cap``
carries the strictest station cap of the face (the within-shape
reader's own frame).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import family, role_cap
from ..model.planar import PlanarMap
from .geometry import long_axis
from .precedence import View, view

__all__ = ["Station", "station_caps", "road_station_caps", "cap_at",
           "face_station_cap"]

GEN = "contiguity"


@_dc.dataclass(frozen=True)
class Station:
    """One station of a road-family face: position and its lawful cap
    (``None`` = no verdict)."""

    face: int
    xy: tuple[float, float]
    cap: float | None
    roles: tuple[str, ...]


def _face_polygon(vw: View, fid: int) -> Polygon | None:
    ring = vw.rings[fid]
    if len(ring) < 3:
        return None
    try:
        poly = Polygon([vw.xy[v] for v in ring],
                       [[vw.xy[v] for v in h] for h in vw.holes[fid] if len(h) >= 3])
    except (ValueError, TypeError):
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.geom_type != "Polygon":
        return None
    return poly


def _keepout(vw: View, airport) -> Polygon | None:
    """The runway strip footprint (clause 5) — the census's own rings."""
    from .strips import runway_groups
    from shapely.ops import unary_union
    polys = []
    for g in runway_groups(vw, airport):
        for ring in g.rings:
            if len(ring) >= 3:
                polys.append(Polygon(ring))
    return unary_union(polys) if polys else None


def station_caps(planar: PlanarMap, law: Law, airport=None,
                 vw: View | None = None) -> list[Station]:
    """Every station of every road-family face with its cap."""
    vw = vw or view(planar, law)
    lc = law.tables.emit.lateral_contiguity
    roads = tuple(family(law, "road_cross_section").roles)
    # the governed rings the probe reads (every face with a cap in the
    # tables — v1 ``ROLE_GRADE_LIMITS`` non-None; pads included)
    polys: list[Polygon] = []
    caps: list[float] = []
    roles: list[str] = []
    fids: list[int] = []
    for fid, f in planar.faces.items():
        c = vw.caps.get(fid)
        if c is None:
            continue
        poly = _face_polygon(vw, fid)
        if poly is None:
            continue
        polys.append(poly)
        caps.append(c[0])
        roles.append(f.role)
        fids.append(fid)
    if not polys:
        return []
    tree = STRtree(polys)
    own_index = {fid: k for k, fid in enumerate(fids)}
    keepout = _keepout(vw, airport) if airport is not None else None
    out: list[Station] = []
    for f in vw.faces_of_role(roads):
        k_own = own_index.get(f.id)
        if k_own is None:
            continue
        poly = polys[k_own]
        axis = long_axis([vw.xy[v] for v in vw.rings[f.id]])
        if axis is None:
            continue
        (ux, uy), length, mid = axis
        nx, ny = -uy, ux
        n_st = max(1, int(length / lc.station_step_m))
        for k in range(n_st):
            t = -0.5 * length + length * (k + 0.5) / n_st
            px, py = mid[0] + ux * t, mid[1] + uy * t
            pt = Point(px, py)
            if not poly.contains(pt):
                continue                       # off the shape: no station
            if keepout is not None and keepout.covers(pt):
                out.append(Station(f.id, (px, py), None, ()))
                continue
            present = _cross_section(px, py, nx, ny, lc.probe_m, lc.gap_tol_m,
                                     lc.min_member_m, tree, polys, roles, k_own)
            cap = min(caps[own_index[fids[j]]] for j in present) if present else None
            out.append(Station(f.id, (px, py), cap,
                               tuple(sorted({roles[j] for j in present}))))
    return out


def _cross_section(px: float, py: float, nx: float, ny: float, probe: float,
                   gap: float, min_member: float, tree: STRtree,
                   polys: list[Polygon], roles: list[str], own: int
                   ) -> list[int]:
    """Indices (into ``polys``) of the run holding the station."""
    cut = LineString([(px - nx * probe, py - ny * probe),
                      (px + nx * probe, py + ny * probe)])
    segs: list[tuple[float, float, int]] = []
    for j in tree.query(cut):
        j = int(j)
        inter = cut.intersection(polys[j])
        if inter.is_empty:
            continue
        parts = [inter] if inter.geom_type == "LineString" else \
            [g for g in getattr(inter, "geoms", ()) if g.geom_type == "LineString"]
        for g in parts:
            ts = [((x - px) * nx + (y - py) * ny) for x, y in g.coords]
            if ts:
                segs.append((min(ts), max(ts), j))
    if not segs:
        return []
    segs.sort()
    runs: list[list] = []
    cur = [segs[0][0], segs[0][1], [segs[0]]]
    for s in segs[1:]:
        if s[0] <= cur[1] + gap:
            cur[1] = max(cur[1], s[1])
            cur[2].append(s)
        else:
            runs.append(cur)
            cur = [s[0], s[1], [s]]
    runs.append(cur)
    for lo, hi, members in runs:
        if not (lo - gap <= 0.0 <= hi + gap):
            continue
        return [j for t0, t1, j in members if j == own or (t1 - t0) >= min_member]
    return []


_CACHE: dict[tuple[int, int, bool], dict[int, list[Station]]] = {}


def road_station_caps(planar: PlanarMap, law: Law, airport=None,
                      vw: View | None = None) -> dict[int, list[Station]]:
    """Stations grouped by face (memoised per planar map — the map never
    mutates, and four generators and the publication read one walk)."""
    key = (id(planar), id(law), airport is not None)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    out: dict[int, list[Station]] = {}
    for st in station_caps(planar, law, airport, vw):
        out.setdefault(st.face, []).append(st)
    if len(_CACHE) > 8:
        _CACHE.clear()
    _CACHE[key] = out
    return out


def cap_at(stations: _t.Sequence[Station], x: float, y: float) -> float | None:
    """The cap governing ``(x, y)``: its NEAREST station's (v1 ``cap_at``
    — the one join convention)."""
    best: tuple[float, float | None] | None = None
    for st in stations:
        d = (st.xy[0] - x) ** 2 + (st.xy[1] - y) ** 2
        if best is None or d < best[0]:
            best = (d, st.cap)
    return None if best is None else best[1]


def face_station_cap(stations: _t.Sequence[Station]) -> float | None:
    """The strictest station cap of a face (the way-level tag)."""
    caps = [st.cap for st in stations if st.cap is not None]
    return min(caps) if caps else None
