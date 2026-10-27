"""A STEEP RUNWAY FLATTENS WHERE TAXIWAYS JOIN IT (owner RULINGS 2026-10-26n,
Q160–Q162, refined by 2026-10-27b Q182; spec
``docs/findings/vnlk-junctions-lvnlk.md``).

The owner, verbatim (Q160): "The taxiway can't have that much lateral slope,
the runway is less steep at the points where a taxiway joins it"; Q161 (a):
flat to the taxiway's own cross-slope limit; Q182 (a): the flat spans the
taxiway MOUTH, "But the runway must still minimize curvature changes, it
can't create a dramatic bump or dip".

ONE DERIVATION (:func:`design`), called by ``runway_yield.derive`` for a
STEEP runway — one whose §50 cap YIELDED to pins demanding more than the
29ac universal pavement ceiling (``tables.pavement_fallback_cap``), the
grade the pavement beside it can no longer follow (Q160 was asked against
that ceiling) — over its GOVERNING span (the two consecutive hard pins §50
names).  A runway yielded under the ceiling keeps the uniform §50 yield and
the 30ah (1) / 10-10j following taxiways and aprons.  Its product rides on
the ``RunwayCap`` record, so the solve rows (``runway_profile``), v2 verify
and the sidecar all read one thing.

* A JUNCTION is a non-runway airside pavement face — the taxi family or an
  apron — sharing at least two ring vertices with the runway's own faces.
  Its span is the MOUTH (Q182 (a)): the along-ridge extent of those shared
  vertices' feet, widened to the ridge chords that cover it (the runway's
  ring edge between the contacts is interpolated off those chords); its cap
  ``t`` is the face's own transverse maximum.  Overlapping spans merge at
  the tighter ``t``.  A junction applies only where the pin grade exceeds
  its ``t``.
* THE DESIGNED PROFILE FOLLOWS THE GROUND, SMOOTHLY (Q182 smoothness;
  Q205 / 27n "VNLK follows the video profile", under 26q): over the station
  chords' grades ``g_k``, the SMOOTHING SPLINE of the DEM along the ridge —
  minimise ``sum w_k (z_k - DEM_k)^2 + lam * sum_k (g_{k+1} - g_k)^2 / s_k``
  with ``lam = (L / 2 pi)^4``, ``L = [design]
  steep_runway_ground_wavelength_m`` on credible lidar, ``..._coarse_m`` on
  a coarser DEM (owner RULINGS 2026-10-28a) (relief longer than ``L`` is followed,
  shorter relief — a surface model's buildings, its noise — is smoothed out)
  — subject to ``sum_k g_k d_k = dz`` (both pins exact) and
  ``|g_k| <= t - margin`` on every junction chord: a bounded least squares.
  With no DEM it is the pure least-change-of-grade profile (27b).  Measured
  (round 4): the pure smoothest profile puts the steepest grade at the low
  end (17.8 %), against both the owner's video and the DEM.
* ONLY WHERE PAVEMENT REALLY JOINS (owner RULINGS 2026-10-27n, Q205,
  superseding 27e's ski-jump ends): a pavement the build's imagery shows
  unpaved where it meets the runway (``airport/junction_witness``,
  ``Airport.paved_joins``) mints no junction; with no imagery the witness
  abstains and every junction stands.
* THE CURVE the vertical-curve rows hold is the one the design needs: the
  law's ``vertical_curve_k_m`` where the design's largest change of grade
  fits it, else the K that design reads, published (``curve_k_m``) a little
  sharper than drawn (``_CURVE_SLACK``) so the rows hold it with room.
"""
from __future__ import annotations

import bisect as _bisect
import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..law.tables import apron_roles, role_cap, role_family
from ..model.planar import PlanarMap
from .geometry import project_to_chain

__all__ = ["Junction", "JunctionProfile", "design", "junctions", "smoothest_grades",
           "RULING"]

#: the ``Source.ruling`` text a junction row cites beside its hard head
RULING = "RULINGS 2026-10-26n a steep runway flattens where taxiways join it"

#: the designed curve is this much GENTLER than the K the rows allow, so a
#: vertical-curve row never holds the design at its own bound
_CURVE_SLACK = 1.05
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
    #: the steepest designed grade (a magnitude) and the largest change of
    #: grade per metre between two chords
    grade: float
    change_per_m: float
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
              grade: float, paved: _t.Mapping[str, bool] | None = None
              ) -> tuple[Junction, ...]:
    """Every junction MOUTH on runway ``rw`` between stations ``i`` and
    ``j`` whose cap is under ``grade`` (module docstring), in ``u`` from
    ``st[i]``.  ``paved``: ``Airport.paved_joins`` — a face of a pavement
    the imagery shows UNPAVED where it meets the runway mints none (owner
    RULINGS 2026-10-27n); ``None`` or an absent id abstains."""
    rwv = _runway_vertices(pm, rw.id)
    if not rwv or j - i < 1:
        return ()
    aprons = apron_roles(law)
    pts = [xy[v] for v in st]
    raw: list[tuple[float, float, float, int]] = []
    for fid, f in sorted(pm.faces.items()):
        if f.role in _RUNWAY_FAMILY:
            continue
        if role_family(law, f.role) != "taxi" and f.role not in aprons:
            continue
        if paved is not None and paved.get(f.ref) is False:
            continue                     # 27n: the photo shows no pavement here
        shared = {v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)
                  if v in rwv}
        if len(shared) < 2:
            continue
        rc = role_cap(law, f.role, f.code_number, f.code_letter)
        if rc is None or rc.transverse >= grade:
            continue
        us = []
        for v in shared:
            _d, k, t, _s = project_to_chain(xy[v], pts)
            us.append(cum[k] + t * (cum[k + 1] - cum[k]))
        # the chords covering the mouth: the last station at or before its
        # first foot, the first at or after its last
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


def smoothest_grades(d: _t.Sequence[float], dz: float,
                     caps: _t.Sequence[float | None],
                     ground: _t.Sequence[float] | None = None,
                     wavelength_m: float | None = None) -> list[float] | None:
    """THE SMOOTHEST CHORD GRADES (module docstring): ``g_k`` over chords of
    lengths ``d`` rising ``dz`` in all, ``|g_k| <= caps[k]`` where a cap is
    given, minimising ``sum (g_{k+1} - g_k)^2 / s_k``.

    With ``ground`` (the ground's height at every station, relative to the
    first; ``len(d) + 1`` values) the profile is the SMOOTHING SPLINE of the
    ground instead: ``sum w_k (z_k - ground_k)^2 + lam * sum (dg)^2 / s_k``,
    ``lam = (wavelength_m / 2 pi)^4`` — relief longer than ``wavelength_m``
    is followed, shorter relief is smoothed out.  ``None`` where the capped
    chords alone cannot be met (no free chord to carry the rest)."""
    import numpy as np
    from scipy.optimize import lsq_linear
    n = len(d)
    free = [k for k in range(n) if caps[k] is None]
    if n == 0 or not free:
        return None
    dd = np.asarray(d, float)
    lam = 1.0
    blocks, rhs = [], []
    if ground is not None and wavelength_m:
        lam = (float(wavelength_m) / (2.0 * math.pi)) ** 4
        C = np.zeros((n + 1, n))
        for k in range(1, n + 1):
            C[k, :k] = dd[:k]
        w = np.sqrt(np.concatenate(([dd[0] / 2], 0.5 * (dd[1:] + dd[:-1]), [dd[-1] / 2])))
        blocks.append(w[:, None] * C)
        rhs.append(w * np.asarray(ground, float))
    R = np.zeros((max(0, n - 1), n))
    for k in range(n - 1):
        wk = math.sqrt(lam) / math.sqrt(0.5 * (d[k] + d[k + 1]))
        R[k, k], R[k, k + 1] = -wk, wk
    blocks.append(R)
    rhs.append(np.zeros(n - 1))
    span = float(dd.sum())
    big = 1e6 / math.sqrt(span)            # the pins, far above every other term
    blocks.append((big * dd / span)[None, :])
    rhs.append(np.array([big * dz / span]))
    A, b = np.vstack(blocks), np.concatenate(rhs)
    lo = np.array([-c if c is not None else -np.inf for c in caps])
    hi = np.array([c if c is not None else np.inf for c in caps])
    res = lsq_linear(A, b, bounds=(lo, hi), method="bvls", tol=1e-12)
    g = [float(x) for x in res.x]
    # the pins EXACT: what the weighted row left, carried by the free chords
    err = dz - sum(gk * dk for gk, dk in zip(g, d, strict=True))
    share = sum(d[k] for k in free)
    for k in free:
        g[k] += err / share
    return g


def design(pm: PlanarMap, law: Law, xy, st: _t.Sequence[int],
           cum: _t.Sequence[float], rw, i: int, j: int,
           za: float, zb: float, k_law: float | None,
           paved: _t.Mapping[str, bool] | None = None,
           lidar: bool = False) -> JunctionProfile | None:
    """THE DESIGNED PROFILE of the span ``st[i]``..``st[j]`` (module
    docstring), or ``None`` where no junction applies (the uniform §50
    yield stands).  ``paved``: the junction witness (:func:`junctions`);
    ``lidar``: the DEM is a credible lidar inset (RULINGS 2026-10-28a)."""
    span = cum[j] - cum[i]
    dz = zb - za
    if span <= 0.0 or dz == 0.0:
        return None
    js = junctions(pm, law, xy, st, cum, rw, i, j, abs(dz) / span, paved)
    if not js:
        return None
    margin = float(law.tables.emit.design.runway_yield_margin)
    unit = float(law.tables.common.vertical_curve_k_grade_unit)
    d = [cum[k + 1] - cum[k] for k in range(i, j)]
    caps: list[float | None] = []
    for k in range(i, j):
        a0, a1 = cum[k] - cum[i], cum[k + 1] - cum[i]
        t = [jn.t for jn in js if a0 >= jn.u0 - 1e-6 and a1 <= jn.u1 + 1e-6]
        caps.append(max(0.0, min(t) - margin) if t else None)
    # RULINGS 2026-10-27n (under 26q): the profile FOLLOWS THE GROUND — the
    # smoothing spline of the DEM along the ridge — where every station has a
    # DEM value; else the pure smoothest profile
    dem = [pm.vertices[st[k]].dem_z for k in range(i, j + 1)]
    ground = None if any(x is None for x in dem) else [float(x) - za for x in dem]
    # RULINGS 2026-10-28a: 200 m on credible lidar, 250 m on a coarse DEM
    dl = law.tables.emit.design
    wl = float(dl.steep_runway_ground_wavelength_m if lidar
               else dl.steep_runway_ground_wavelength_coarse_m)
    g = smoothest_grades(d, dz, caps, ground, wl)
    if g is None:
        return None
    z = {st[i]: za}
    h = za
    for k, (gk, dk) in enumerate(zip(g, d, strict=True)):
        h += gk * dk
        z[st[i + k + 1]] = h
    z[st[j]] = zb
    rate = max((abs(g[k + 1] - g[k]) / (0.5 * (d[k] + d[k + 1]))
                for k in range(len(g) - 1)), default=0.0)
    k_need = unit / (rate * _CURVE_SLACK) if rate > 0.0 else None
    k_pub = None if k_need is None or (k_law and k_need >= k_law) else k_need
    return JunctionProfile(js, max(abs(x) for x in g), rate, k_pub, z)
