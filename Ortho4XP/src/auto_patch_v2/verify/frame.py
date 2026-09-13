"""The verifier's read of a :class:`GradedSurface` — the emitted rings in
the CENSUS'S OWN metre frame (mean-centred equirectangular, the v1
``check_grade._ll_to_m_factory``; ``R_EARTH`` is WGS84's semi-major axis)
so a v2 row and a v1 row of the same site carry the same ``site_m``, and
the row record with the v1 ``census.row_record`` keys so the two row
sets diff by (family, roles, site).

Everything here is DATA: rings with ``(x, y, z)`` per vertex, the
publication (sidecar) in metres, the instrument envelope per role from
``emit.instrument`` (the reader's forgiveness, never a solve budget).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..emit.surface import GradedSurface
from ..law import Law
from ..law.tables import is_rigid_role, role_cap, role_side

__all__ = ["R_EARTH", "Shape", "Patch", "Row", "row", "noise_m"]

R_EARTH = 6_378_137.0


@_dc.dataclass(frozen=True)
class Shape:
    """One emitted ring (a face's outer ring, or a hole / breakline
    FEATURE way) with its vertices in the census frame."""

    key: int                     # face id (or -1 - k for features)
    role: str
    ref: str
    ids: tuple[int, ...]         # vertex ids, open
    xy: tuple[tuple[float, float], ...]
    z: tuple[float, ...]
    feature: str | None = None   # gap_interior_ring | crown_spine | structure_rim
    code_letter: str | None = None
    code_number: int | None = None
    single_poly: bool = False
    #: §37 (1): the TRANSVERSE binding of lateral contiguity
    #: (``o4_grade_law_cap_t``) — never the longitudinal cap
    law_cap: float | None = None
    #: a hole feature's host face id (``key`` of the shape it is cut from)
    host: int | None = None
    #: a ``structure_rim`` feature: a closed ring (True) or an open chain
    #: whose ends stand on the ramp's top corners (a U void)
    feature_closed: bool = True

    @property
    def closed_ring(self) -> tuple[tuple[float, float, float], ...]:
        return tuple((x, y, zz) for (x, y), zz in zip(self.xy, self.z))


@_dc.dataclass(frozen=True)
class Patch:
    """The whole emitted product in the census frame."""

    law: Law
    lat0: float
    lon0: float
    xy: dict[int, tuple[float, float]]
    z: dict[int, float]
    ll: dict[int, tuple[float, float]]
    shapes: tuple[Shape, ...]          # role-carrying rings
    features: tuple[Shape, ...]        # holes, crown spines
    publication: _t.Mapping[str, _t.Any]

    def to_m(self, lat: float, lon: float) -> tuple[float, float]:
        cos0 = math.cos(math.radians(self.lat0))
        return (math.radians(lon - self.lon0) * R_EARTH * cos0,
                math.radians(lat - self.lat0) * R_EARTH)

    def cap(self, sh: Shape) -> float | None:
        """The within-shape LONGITUDINAL cap the census judges at — the
        role's own.  §37 (1) (RULINGS 2026-09-13q item 5): the
        lateral-contiguity cap no longer enters here; it binds the
        TRANSVERSE cap only (:meth:`cap_t`)."""
        rc = role_cap(self.law, sh.role, sh.code_number, sh.code_letter)
        return None if rc is None else rc.longitudinal

    def cap_t(self, sh: Shape) -> float | None:
        """The TRANSVERSE cap: the role's, tightened by the shape's
        lateral-contiguity binding (§37 (1))."""
        rc = role_cap(self.law, sh.role, sh.code_number, sh.code_letter)
        if rc is None:
            return None
        c = min(rc.transverse, rc.longitudinal)
        if sh.law_cap is not None:
            c = min(c, sh.law_cap)
        return c

    def side(self, role: str) -> str:
        return role_side(self.law, role)

    def is_rigid(self, role: str) -> bool:
        return is_rigid_role(self.law, role)

    @classmethod
    def of(cls, surface: GradedSurface, law: Law,
           publication: _t.Mapping[str, _t.Any] | None = None,
           law_caps: _t.Mapping[int, float] | None = None) -> "Patch":
        verts = surface.vertices
        lat0 = sum(v.ll[0] for v in verts) / max(1, len(verts))
        lon0 = sum(v.ll[1] for v in verts) / max(1, len(verts))
        cos0 = math.cos(math.radians(lat0))

        def to_m(lat: float, lon: float) -> tuple[float, float]:
            return (math.radians(lon - lon0) * R_EARTH * cos0,
                    math.radians(lat - lat0) * R_EARTH)

        xy = {v.id: to_m(*v.ll) for v in verts}
        z = {v.id: v.z for v in verts}
        ll = {v.id: v.ll for v in verts}
        shapes: list[Shape] = []
        feats: list[Shape] = []
        k = 0
        for f in surface.faces:
            shapes.append(Shape(f.id, f.role, f.ref, tuple(f.ring),
                                tuple(xy[i] for i in f.ring),
                                tuple(z[i] for i in f.ring), None,
                                f.code_letter, f.code_number,
                                f.role == "runway",
                                (law_caps or {}).get(f.id)))
            for h in f.holes:
                k += 1
                feats.append(Shape(-k, "", f.ref, tuple(h),
                                   tuple(xy[i] for i in h), tuple(z[i] for i in h),
                                   "gap_interior_ring", host=f.id))
        for b in surface.breaklines:
            if b.kind == "runway_profile" and len(b.vertices) >= 2:
                k += 1
                feats.append(Shape(-k, "", b.ref, tuple(b.vertices),
                                   tuple(xy[i] for i in b.vertices),
                                   tuple(z[i] for i in b.vertices), "crown_spine"))
            elif b.kind == "structure_rim" and len(b.vertices) >= 3:
                # the at-grade rim of a structure's void (2026-09-06b):
                # the ring open (its closing vertex dropped), the ref the
                # structure's (``tunnel_wall`` / ``basin_wall:<k>``)
                k += 1
                closed = b.vertices[0] == b.vertices[-1]
                ids = b.vertices[:-1] if closed else b.vertices
                feats.append(Shape(-k, "", b.ref.split("@")[0], tuple(ids),
                                   tuple(xy[i] for i in ids), tuple(z[i] for i in ids),
                                   "structure_rim", feature_closed=closed))
        return cls(law, lat0, lon0, xy, z, ll, tuple(shapes), tuple(feats),
                   dict(publication or {}))


Row = dict[str, _t.Any]


def row(family: str, roles: _t.Sequence[str], side: str, magnitude_m: float,
        grade_pct: float | None, cap_pct: float | None, distance_m: float | None,
        a: tuple[float, float] | None, b: tuple[float, float] | None,
        way_a: object, way_b: object, out_of_scope: str | None = None,
        lat: float | None = None, lon: float | None = None) -> Row:
    """One row in the v1 ``census.row_record`` shape."""
    return {
        "family": family, "roles": "|".join(sorted(roles)), "side": side,
        "magnitude_m": round(float(magnitude_m), 4),
        "grade_pct": None if grade_pct is None else round(float(grade_pct), 4),
        "cap_pct": None if cap_pct is None else round(float(cap_pct), 4),
        "distance_m": None if distance_m is None else round(float(distance_m), 3),
        "site_m": None if a is None or b is None else
        [[round(a[0], 2), round(a[1], 2)], [round(b[0], 2), round(b[1], 2)]],
        "lat": lat, "lon": lon, "way_a": way_a, "way_b": way_b,
        "out_of_scope": out_of_scope,
    }


def noise_m(law: Law, role: str) -> float:
    """The census's per-pair quantisation envelope for ``role``
    (``emit.instrument``): coarse on the weld-hub roles."""
    ins = law.tables.emit.instrument
    if role in ins.coarse_noise_roles:
        return ins.coarse_noise_m
    return ins.rounding_noise_m


def pair_side(p: Patch, ra: str, rb: str) -> str:
    sa, sb = p.side(ra), p.side(rb)
    if sa == sb:
        return sa
    return "mixed"
