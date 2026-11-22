"""A SURFACE OVER A PARALLELOGRAM FROM ITS FOUR EDGE PROFILES (a bilinearly
blended Coons patch; airside-first bridges spec section 1 row 4).

A generated deck's top is the airside solve's pavement over its ring
(owner RULINGS 2026-11-19s (1)): the solve answers a level at each vertex
on the ring's four edges, and this patch interpolates between them --
EXACT on every edge, so a deck end is flush with the pavement it meets by
construction, whatever the slope along or across the route.

The parallelogram is ``o + s * u + t * w`` for ``s, t`` in ``[0, 1]``:
``u`` runs along the carried route (the SIDES), ``w`` across it (the ENDS,
the cut's crests).  Each profile is a polyline of ``(parameter, z)``
pairs, read flat past its first and last sample.  Pure geometry: no
shapely, no law; the planar stage (``constraints/deck_floor_follow``) and
the object stage (``airport/deck_objects``) read the same patch.
"""
from __future__ import annotations

import bisect
import dataclasses as _dc
import typing as _t

__all__ = ["CoonsPatch", "edge_profiles"]

XY = tuple[float, float]
Profile = tuple[tuple[float, float], ...]


def _profile_at(prof: Profile, q: float) -> float:
    """``prof`` (sorted ``(parameter, z)``) at ``q``, linear between
    samples, flat past the ends."""
    if not prof:
        return 0.0
    ks = [p for p, _z in prof]
    i = bisect.bisect_left(ks, q)
    if i <= 0:
        return float(prof[0][1])
    if i >= len(prof):
        return float(prof[-1][1])
    (p0, z0), (p1, z1) = prof[i - 1], prof[i]
    return float(z0) if p1 - p0 <= 1e-12 else float(z0 + (z1 - z0) * (q - p0) / (p1 - p0))


@_dc.dataclass(frozen=True)
class CoonsPatch:
    """The patch (module doc): corner ``o``, edge vectors ``u`` (route) and
    ``w`` (across); ``a`` the end at ``s = 0`` and ``b`` at ``s = 1``
    (profiles over ``t``), ``s0`` the side at ``t = 0`` and ``s1`` at
    ``t = 1`` (profiles over ``s``)."""

    o: XY
    u: XY
    w: XY
    a: Profile
    b: Profile
    s0: Profile
    s1: Profile

    def st(self, x: float, y: float) -> tuple[float, float]:
        """The patch parameters of a frame point."""
        (ux, uy), (wx, wy) = self.u, self.w
        det = ux * wy - uy * wx
        dx, dy = x - self.o[0], y - self.o[1]
        if abs(det) <= 1e-12:
            return 0.0, 0.0
        return (dx * wy - dy * wx) / det, (ux * dy - uy * dx) / det

    def z_st(self, s: float, t: float) -> float:
        """The patch at ``(s, t)``, clamped into the parallelogram."""
        s, t = min(1.0, max(0.0, s)), min(1.0, max(0.0, t))
        za, zb = _profile_at(self.a, t), _profile_at(self.b, t)
        z0, z1 = _profile_at(self.s0, s), _profile_at(self.s1, s)
        c00, c01 = _profile_at(self.a, 0.0), _profile_at(self.a, 1.0)
        c10, c11 = _profile_at(self.b, 0.0), _profile_at(self.b, 1.0)
        return ((1 - s) * za + s * zb + (1 - t) * z0 + t * z1
                - ((1 - s) * (1 - t) * c00 + s * (1 - t) * c10
                   + (1 - s) * t * c01 + s * t * c11))

    def z(self, x: float, y: float) -> float:
        """The patch at a frame point."""
        return self.z_st(*self.st(x, y))

    def low(self) -> float:
        """The lowest sample of the four profiles (the patch is a blend of
        them: its least is within the profiles' spread of this)."""
        return min(z for p in (self.a, self.b, self.s0, self.s1) for _q, z in p)

    def as_record(self) -> dict:
        """JSON-able: the frame-free half (the profiles); the caller states
        ``o``, ``u``, ``w`` in its own frame."""
        return {"a": [list(p) for p in self.a], "b": [list(p) for p in self.b],
                "s0": [list(p) for p in self.s0], "s1": [list(p) for p in self.s1]}


def edge_profiles(o: XY, u: XY, w: XY, samples: _t.Iterable[tuple[float, float, float]],
                  tol: float = 0.05) -> "CoonsPatch | None":
    """The patch of the parallelogram ``(o, u, w)`` from level samples
    ``(x, y, z)``: each sample within ``tol`` metres of an edge joins that
    edge's profile (a corner joins both).  ``None`` where an end carries no
    sample (no level to be flush with)."""
    ln_u = (u[0] ** 2 + u[1] ** 2) ** 0.5
    ln_w = (w[0] ** 2 + w[1] ** 2) ** 0.5
    if ln_u <= 1e-9 or ln_w <= 1e-9:
        return None
    probe = CoonsPatch(o, u, w, (), (), (), ())
    a, b, s0, s1 = [], [], [], []
    tol_s, tol_t = tol / ln_u, tol / ln_w
    for x, y, z in samples:
        s, t = probe.st(x, y)
        if not (-tol_s <= s <= 1 + tol_s and -tol_t <= t <= 1 + tol_t):
            continue
        if abs(s) <= tol_s:
            a.append((t, z))
        if abs(s - 1.0) <= tol_s:
            b.append((t, z))
        if abs(t) <= tol_t:
            s0.append((s, z))
        if abs(t - 1.0) <= tol_t:
            s1.append((s, z))
    if not a or not b:
        return None
    pa, pb = tuple(sorted(a)), tuple(sorted(b))
    if not s0:
        s0 = [(0.0, _profile_at(pa, 0.0)), (1.0, _profile_at(pb, 0.0))]
    if not s1:
        s1 = [(0.0, _profile_at(pa, 1.0)), (1.0, _profile_at(pb, 1.0))]
    return CoonsPatch(o, u, w, *_cornered(pa, pb, tuple(sorted(s0)), tuple(sorted(s1))))


def _cornered(a: Profile, b: Profile, s0: Profile, s1: Profile) -> tuple[Profile, ...]:
    """The four profiles agreeing at each corner: each corner the mean of
    its two edges' values there, stated as both edges' end sample.  Two
    edges reading their first samples off different vertices left the
    patch discontinuous at the corner (lane lcross21, KRDU taxiway d's deck:
    0.11 m between end A's profile and the side's at one corner, a step at
    the deck end's corner)."""
    def at(p, q):
        return _profile_at(p, q)

    def put(p, q, z):
        return tuple(sorted([(k, v) for k, v in p if abs(k - q) > 1e-9] + [(q, z)]))
    c00 = 0.5 * (at(a, 0.0) + at(s0, 0.0))
    c01 = 0.5 * (at(a, 1.0) + at(s1, 0.0))
    c10 = 0.5 * (at(b, 0.0) + at(s0, 1.0))
    c11 = 0.5 * (at(b, 1.0) + at(s1, 1.0))
    return (put(put(a, 0.0, c00), 1.0, c01), put(put(b, 0.0, c10), 1.0, c11),
            put(put(s0, 0.0, c00), 1.0, c10), put(put(s1, 0.0, c01), 1.0, c11))
