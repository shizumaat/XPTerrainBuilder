"""THE RUNWAY FITS THE THRESHOLD CHORD (owner RULINGS 2026-09-08d (1); spec
``heca-v1-parity-spec.md`` §1 — v1's ``runway_redistribute`` anchored a
CIFP-chord envelope and FILLED; v2 fitted the DEM and sagged to it).

For every runway carrying TWO CIFP threshold pins (``constraints.
runway_profile.threshold_pins``), every runway-family vertex on that
runway's faces takes a FIT TARGET (``PlanarMap.preferred_z``, the same
channel the core's road profile uses, RULINGS 04t-4): the straight line
between the two pins at the vertex's station along the runway axis,
less the DESIGNED crown drop at its lateral offset (``common.
runway_crown_transverse`` × d — the edge's target is the ridge's chord
minus the crown, so the crown floor and the chord agree).  The station is
the vertex's FOOT on the crown ridge (the crown reader's own projection),
so a crossing-ring vertex reads the chord of the ridge it is nearest to.
The fit weight is ``rulesets.toml [common] runway_chord_fit`` (``law.
tables.runway_chord_fit_weight``), applied to the runway family's roles by
``pipeline.build.weights_under_law``.  A runway with fewer than two pins
keeps the DEM as its target (never an invented value, plan §2).

The K rows, the max-grade rows, the transverse maximum and the pins stay
HARD; the profile smoothness stays senior to this term: the runway runs
straight between its holds and FILLS or CUTS toward the chord wherever
nothing senior holds it.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .geometry import project_to_chain
from .precedence import view
from .runway_profile import RUNWAY_FAMILY, ridge_chains, threshold_pins
from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["ChordReport", "runway_chord_targets", "with_runway_chord"]


class ChordReport(_t.TypedDict, total=False):
    """What the chord fit covered."""

    runways: int              # runways with two pins (a chord)
    runways_without: int      # runways with fewer than two pins (DEM fit kept)
    vertices: int             # runway-family vertices given a chord target
    max_above_dem_m: float    # the largest chord − DEM (the fill the target asks)
    max_below_dem_m: float    # the largest DEM − chord (the cut)


@_dc.dataclass(frozen=True)
class _Chord:
    """One runway's chord: the axis frame and the line between its pins."""

    a_xy: tuple[float, float]
    ux: float
    uy: float
    s0: float
    s1: float
    z0: float
    z1: float

    def station(self, x: float, y: float) -> float:
        return (x - self.a_xy[0]) * self.ux + (y - self.a_xy[1]) * self.uy

    def z(self, s: float) -> float:
        return self.z0 + (self.z1 - self.z0) * (s - self.s0) / (self.s1 - self.s0)


def runway_chord_targets(pm: PlanarMap, law: Law, airport: Airport,
                         report: ChordReport | None = None) -> dict[int, float]:
    """Vertex -> chord target for every runway-family vertex of a runway
    with two CIFP pins (module docstring)."""
    vw = view(pm, law)
    chains = ridge_chains(vw)
    pins = threshold_pins(pm, law, airport)
    crown = law.tables.common.runway_crown_transverse
    chords: dict[str, _Chord] = {}
    n_without = 0
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        own = [v for ch in chs for v in ch if v in pins]
        L = rw.length_m
        if len(own) < 2 or L <= 0.0:
            n_without += 1
            continue
        a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
        ux, uy = (b_xy[0] - a_xy[0]) / L, (b_xy[1] - a_xy[1]) / L
        st = {v: (vw.xy[v][0] - a_xy[0]) * ux + (vw.xy[v][1] - a_xy[1]) * uy for v in own}
        p0, p1 = min(own, key=st.get), max(own, key=st.get)
        if st[p1] - st[p0] <= 0.0:
            n_without += 1
            continue
        chords[rw.id] = _Chord(a_xy, ux, uy, st[p0], st[p1], pins[p0], pins[p1])
    out: dict[int, float] = {}
    above = below = 0.0
    for f in vw.faces_of_role(RUNWAY_FAMILY):
        refs = [r for r in ([f.ref] if f.role == "runway" else f.ref.split("+")) if r in chords]
        if not refs:
            continue
        for v in vw.rings[f.id]:
            if v in out:
                continue
            best: tuple[float, float] | None = None       # (lateral d, chord z at the foot)
            p = vw.xy[v]
            for r in refs:
                c = chords[r]
                for ch in chains.get(r, []):
                    if len(ch) < 2:
                        continue
                    d, k, t, _s = project_to_chain(p, [vw.xy[q] for q in ch])
                    (xa, ya), (xb, yb) = vw.xy[ch[k]], vw.xy[ch[k + 1]]
                    zc = c.z(c.station(xa + t * (xb - xa), ya + t * (yb - ya)))
                    if best is None or d < best[0]:
                        best = (d, zc)
            if best is None:
                continue
            d, zc = best
            out[v] = zc - crown * d
            dem = pm.vertices[v].dem_z
            if dem is not None:
                above = max(above, out[v] - dem)
                below = max(below, dem - out[v])
    if report is not None:
        report.update(runways=len(chords), runways_without=n_without, vertices=len(out),
                      max_above_dem_m=round(above, 3), max_below_dem_m=round(below, 3))
    return out


def with_runway_chord(pm: PlanarMap, law: Law, airport: Airport,
                      report: ChordReport | None = None) -> PlanarMap:
    """``pm`` with the chord targets merged into ``preferred_z`` (on a
    shared vertex the runway family's target wins: the runway is senior)."""
    targets = runway_chord_targets(pm, law, airport, report)
    if not targets:
        return pm
    merged = dict(pm.preferred_z)
    merged.update(targets)
    return _dc.replace(pm, preferred_z=merged)
