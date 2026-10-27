"""A STEEP RUNWAY FLATTENS WHERE TAXIWAYS JOIN IT (owner RULINGS 2026-10-26n,
Q160–Q162; spec ``docs/findings/vnlk-junctions-lvnlk.md``).

The owner, verbatim (Q160): "The taxiway can't have that much lateral slope,
the runway is less steep at the points where a taxiway joins it"; Q161 (a):
flat to the taxiway's own cross-slope limit, so the taxiway meets it without
twisting.  The ruling's reading: across each taxiway junction (the joining
taxiway's width plus fillets) the runway's longitudinal grade is capped at
that taxiway's TRANSVERSE maximum; between junctions the runway takes the
remaining grade the end pins require, eased by vertical curves.

ONE DERIVATION (:func:`design`), called by ``runway_yield.derive`` for a
STEEP runway — one whose §50 cap YIELDED to pins demanding more than the
29ac universal pavement ceiling (``tables.pavement_fallback_cap``), the
grade the pavement beside it can no longer follow (Q160 was asked against
that ceiling) — over its GOVERNING span (the two consecutive hard pins §50
names).  A runway yielded under the ceiling keeps the uniform §50 yield and
the 30ah (1) / 10-10j following taxiways and aprons.  Its product rides on the ``RunwayCap`` record, so the
solve rows (``runway_profile``), v2 verify (``verify/runway``) and the
sidecar all read one thing.

* A JUNCTION is a non-runway airside pavement face — the taxi family or an
  apron — sharing at least two ring vertices with the runway's own faces.
  Its span is the along-ridge extent of those vertices' feet, widened to
  the ridge chords that cover it (the runway's ring edge between the
  contacts is interpolated off those chords); its cap ``t`` is the face's
  own transverse maximum.  Overlapping spans merge, at the tighter ``t``.
  A junction applies only where the pin grade exceeds its ``t``.
* THE DESIGNED PROFILE, ``u`` the ridge distance from the lower pin:
  ``g(u) = min(G, min_j (t_j + r · δ_j(u)))`` with ``δ_j`` the distance to
  junction ``j``'s span (0 inside it): the grade is ``t_j`` inside a
  junction and eases out at a constant rate ``r`` (a vertical curve,
  ``K = unit / r``) to the remaining grade ``G``, solved so the profile
  meets both pins exactly.
* THE CURVE: the law's ``vertical_curve_k_m`` where it fits; otherwise it
  yields, uniformly per runway, only as far as keeps ``G`` within
  ``[design] steep_junction_curve_share`` of the abrupt fit ``G0`` (no curve
  at all).  The design is made a little gentler than the published K
  (``_CURVE_SLACK``) so the vertical-curve rows hold it with room.
"""
from __future__ import annotations

import bisect as _bisect
import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..law.tables import apron_roles, role_cap, role_family, runway_zone_edge_offset_m
from ..model.planar import PlanarMap
from .geometry import project_to_chain

__all__ = ["Junction", "JunctionProfile", "design", "junctions", "RULING"]

#: the ``Source.ruling`` text a junction row cites beside its hard head
RULING = "RULINGS 2026-10-26n a steep runway flattens where taxiways join it"

#: the designed curve is this much GENTLER than the K the rows allow, so a
#: vertical-curve row never holds the design at its own bound
_CURVE_SLACK = 1.05
#: integration step of the designed grade (m)
_STEP_M = 0.25
_RUNWAY_FAMILY = ("runway", "runway_crossing")


@_dc.dataclass(frozen=True)
class Junction:
    """One junction span on a runway's ridge: ``u0``..``u1`` metres of ridge
    from the governing span's lower pin, its cap ``t`` and the faces that
    join there."""

    u0: float
    u1: float
    t: float
    faces: tuple[int, ...]

    def as_dict(self) -> dict[str, _t.Any]:
        """The PUBLISHED shape (sidecar ``runway_caps[].junctions``)."""
        return {"from_m": round(self.u0, 3), "to_m": round(self.u1, 3),
                "cap": round(self.t, 6), "faces": list(self.faces)}


@_dc.dataclass(frozen=True)
class JunctionProfile:
    """The designed profile of one runway's governing span."""

    junctions: tuple[Junction, ...]
    #: the steepest designed grade (a magnitude) and the abrupt fit's
    grade: float
    abrupt: float
    #: the K (m per ``vertical_curve_k_grade_unit``) the rows allow, or
    #: ``None`` where the law's own K stands
    curve_k_m: float | None
    #: ridge station vertex -> designed height
    z: _t.Mapping[int, float]


def _runway_vertices(pm: PlanarMap, ref: str) -> set[int]:
    out: set[int] = set()
    for f in pm.faces.values():
        if f.role in _RUNWAY_FAMILY and ref in f.ref.split("+"):
            for cyc in (f.ring, *f.holes):
                out.update(pm.ring_vertices(cyc))
    return out


def junctions(pm: PlanarMap, law: Law, xy, st: _t.Sequence[int],
              cum: _t.Sequence[float], rw, i: int, j: int,
              grade: float) -> tuple[Junction, ...]:
    """Every junction on runway ``rw`` between stations ``i`` and ``j``
    whose cap is under ``grade`` (module docstring), in ``u`` from ``st[i]``."""
    rwv = _runway_vertices(pm, rw.id)
    if not rwv or j - i < 1:
        return ()
    aprons = apron_roles(law)
    pts = [xy[v] for v in st]
    reach = _reach_m(law, rw)

    def own(f) -> bool:
        return f.role not in _RUNWAY_FAMILY and (
            role_family(law, f.role) == "taxi" or f.role in aprons)

    raw: list[tuple[float, float, float, int]] = []
    for fid, f in sorted(pm.faces.items()):
        if not own(f):
            continue
        shared = {v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)
                  if v in rwv}
        if len(shared) < 2:
            continue
        rc = role_cap(law, f.role, f.code_number, f.code_letter)
        if rc is None or rc.transverse >= grade:
            continue
        # THE JOINING PAVEMENT'S FRONTAGE: every vertex of the joined
        # pavement (the face's ref) the runway-edge tie reaches — there the
        # runway's grade IS that pavement's grade along the runway
        near = set(shared)
        for g in pm.faces.values():
            if g.ref == f.ref and own(g):
                near.update(v for cyc in (g.ring, *g.holes)
                            for v in pm.ring_vertices(cyc))
        us = []
        for v in near:
            d, k, t, _s = project_to_chain(xy[v], pts)
            if v in shared or d <= reach:
                us.append(cum[k] + t * (cum[k + 1] - cum[k]))
        # the chords covering the contact: the last station at or before
        # its first foot, the first at or after its last
        lo = max(i, _bisect.bisect_right(cum, min(us) + 1e-9) - 1)
        hi = min(j, _bisect.bisect_left(cum, max(us) - 1e-9))
        if hi <= lo:
            continue
        raw.append((cum[lo] - cum[i], cum[hi] - cum[i], float(rc.transverse), fid))
    raw.sort()
    out: list[list] = []
    for u0, u1, t, fid in raw:
        if out and u0 <= out[-1][1] + 1e-9:
            last = out[-1]
            last[1], last[2] = max(last[1], u1), min(last[2], t)
            last[3].append(fid)
        else:
            out.append([u0, u1, t, [fid]])
    return tuple(Junction(a, b, t, tuple(sorted(fs))) for a, b, t, fs in out)


def _reach_m(law: Law, rw) -> float:
    """How far from the centreline the runway-edge tie binds pavement to
    the runway's level: the zone-2 half width (``tables.
    runway_zone_edge_offset_m`` from the edge, plus the half width)."""
    half = float(getattr(rw, "width_m", 0.0) or 0.0) / 2.0
    off = runway_zone_edge_offset_m(law, rw.code_number, rw.code_letter, half)
    return half + (float(off) if off is not None else 0.0)


def _grades(span: float, js: _t.Sequence[Junction], margin: float):
    """``(u, δ-curves)``: the grid and, per junction, its design cap and
    distance; the caller takes ``min(G, t + r δ)``."""
    import numpy as np
    n = max(2, int(math.ceil(span / _STEP_M)) + 1)
    u = np.linspace(0.0, span, n)
    caps = [(max(0.0, jn.t - margin),
             np.where(u < jn.u0, jn.u0 - u, np.where(u > jn.u1, u - jn.u1, 0.0)))
            for jn in js]
    return u, caps


def _profile(u, caps, G: float, r: float):
    import numpy as np
    g = np.full_like(u, G)
    for t, d in caps:
        g = np.minimum(g, t + r * d) if math.isfinite(r) else \
            np.minimum(g, np.where(d > 0.0, G, t))
    return g


def _height(u, g) -> float:
    import numpy as np
    return float(np.trapezoid(g, u))


def _solve_g(u, caps, r: float, dz: float) -> float | None:
    """The remaining grade ``G`` meeting ``dz`` at curve rate ``r``, or
    ``None`` where even an unbounded ``G`` does not reach it."""
    hi = 1.0
    while _height(u, _profile(u, caps, hi, r)) < dz:
        hi *= 2.0
        if hi > 64.0:
            return None
    lo = 0.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _height(u, _profile(u, caps, mid, r)) < dz:
            lo = mid
        else:
            hi = mid
    return hi


def design(pm: PlanarMap, law: Law, xy, st: _t.Sequence[int],
           cum: _t.Sequence[float], rw, i: int, j: int,
           za: float, zb: float, k_law: float | None) -> JunctionProfile | None:
    """THE DESIGNED PROFILE of the span ``st[i]``..``st[j]`` (module
    docstring), or ``None`` where no junction applies (the uniform §50
    yield stands)."""
    import numpy as np
    span = cum[j] - cum[i]
    dz = abs(zb - za)
    if span <= 0.0 or dz <= 0.0:
        return None
    js = junctions(pm, law, xy, st, cum, rw, i, j, dz / span)
    if not js:
        return None
    d = law.tables.emit.design
    margin = float(d.runway_yield_margin)
    share = float(d.steep_junction_curve_share)
    unit = float(law.tables.common.vertical_curve_k_grade_unit)
    u, caps = _grades(span, js, margin)
    g0 = _solve_g(u, caps, math.inf, dz)
    if g0 is None or g0 <= max(t for t, _d in caps):
        return None                       # the flats alone carry the rise
    target = (1.0 + share) * g0

    def g_of(k: float) -> float | None:
        return _solve_g(u, caps, unit / k, dz)

    k_top = (k_law or 0.0) * _CURVE_SLACK
    k_d = k_top if k_top > 0.0 else None
    got = g_of(k_d) if k_d else None
    if got is None or got > target:
        lo, hi = 1e-3, (k_top if k_top > 0.0 else 1e4)
        for _ in range(60):               # the gentlest K within the share
            mid = math.sqrt(lo * hi)
            gm = g_of(mid)
            if gm is not None and gm <= target:
                lo = mid
            else:
                hi = mid
        k_d = lo
        got = g_of(k_d)
    if got is None:
        return None
    g = _profile(u, caps, got, unit / k_d)
    h = np.concatenate(([0.0], np.cumsum(0.5 * (g[1:] + g[:-1]) * np.diff(u))))
    sign = 1.0 if zb >= za else -1.0
    z = {st[k]: za + sign * float(np.interp(cum[k] - cum[i], u, h))
         for k in range(i, j + 1)}
    z[st[j]] = zb
    k_pub = k_d / _CURVE_SLACK
    return JunctionProfile(js, float(g.max()), g0,
                           None if k_law and k_pub >= k_law else k_pub, z)
