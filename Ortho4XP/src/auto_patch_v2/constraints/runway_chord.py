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
The chord is a TARGET of the design surface at ``emit.toml [design] chord``
(RULINGS 2026-09-08t; the old per-metre ladder weight ``[common]
runway_chord_fit`` is deleted with the ladder), applied to the runway family's roles by
``pipeline.build.weights_under_law``.  A runway with fewer than two pins
keeps the DEM as its target (never an invented value, plan §2).

THE NEAREST-THRESHOLD CROSSING PIN (owner RULINGS 2026-09-09z (1), spec
§17, superseding 09r (2)'s "the primary governs").  At a runway x runway
crossing the runway whose THRESHOLD is nearest the crossing node solves
that node under its own laws — its chord is unchanged — and the node's
elevation becomes an ANCHOR for every other runway through the crossing,
exactly as a CIFP threshold or a tile-seam DEM value is: a hard ``Pin``
(:func:`runway_crossing_pins`, generator ``runway_crossing_pin``) on that
runway's ridge vertex at the node, and its chord target RE-FIT piecewise
through the same value.  This is v1's own logic — ``src/auto_patch/
pavement/runway_segments.py`` "Runway-runway centerline-crossing
reconciliation": "whichever runway has the threshold geometrically closer
to the crossing point gets its CIFP-linear-interp value used as the agreed
altitude ... and the OTHER runway accommodates by deviating from its own
linear interpolation as much as the FAA gates allow".

THE RUNWAY PROFILE FOLLOWS THE AIRPORT (owner RULINGS 2026-09-10q/10r,
ruled 10t (3); spec §21).  SPJC read the cost of a STRAIGHT chord: the
built ridge reproduced it to <= 0.01 m at every 250 m station — zero
vertical curves — and sat 26.71 m abeam a taxiway whose lawful envelope
admits the runway at 25.60, with mean |z - DEM| 2.14 m over the length.
The owner: "the runway also seems like it should be allowed to have a bit
more curvature, as in reality airports want to minimize the elevation
variance between adjacent paved areas when possible" (10q); "long gentle
curves are best for fast moving aircraft" (10r).

So the SAME ROW (weight ``[design] chord``) keeps a different TARGET: the
GROUND'S LONG-WAVE TREND along the ridge.  At a ridge station ``s`` the
target is the value at ``s`` of a moving QUADRATIC least-squares fit of
the PRODUCTION DEM sampled along that runway's own ridge over
``s +/- [design] runway_profile_window_m`` (:class:`_Trend`), shifted by
the LINEAR correction that puts the profile exactly through the two
threshold pins (:meth:`_Chord.z`).

WHY A LINEAR CORRECTION AND NOT A CONSTRAINED LEAST SQUARES (spec §21.2
(1) offers either; this is the one implemented, and the reason): adding an
affine function to the fitted trend leaves its SECOND DERIVATIVE
untouched, so the pins cost the profile no curvature at all — the window
alone bounds it, and the window is validated at or above the largest
``vertical_curve_k_m``.  A constrained LSQ would instead bend the fit to
reach the pins, spending curvature the K law has to pay for at the very
stations (the end zones) where the law is tightest.  With a crossing knot
(§17) the correction is PIECEWISE linear over the control points, which is
the same statement segment by segment and reduces byte-for-byte to the
straight chord when there is no trend.

THE CHORD IS THE FALLBACK (spec §21.2 (2), plan §2 — never an invented
value): where the production DEM frame is DEGRADED (``airport.dem.
provenance['degraded']``, the ``--allow-degraded-dem`` arm) or a runway's
ridge yields too few DEM samples to fit, the target is the straight
threshold chord exactly as before; a runway with fewer than two pins keeps
the DEM as its target, unchanged.

WHAT THE TARGET IS NOT (spec §21.2 (5)): a per-vertex DEM pull (08t (1)).
The window is longer than any DEM artefact the owner has read as
"unrealistic undulation" (09b) and the fit is quadratic over >= 1 km of
ridge, so the runway bends with the ground's TREND and cannot undulate
with the ground.

The K rows, the max-grade rows, the transverse maximum and the pins stay
HARD; the profile smoothness stays senior to this term: the runway runs
between its holds and FILLS or CUTS toward the target wherever nothing
senior holds it.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .geometry import project_to_chain
from .precedence import view
from .trend import Trend as _Trend, trend_of as _trend_of
from .runway_profile import RUNWAY_FAMILY, ridge_chains, threshold_pins
from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["ChordReport", "Crossing", "runway_chord_targets", "with_runway_chord",
           "runway_crossings", "runway_crossing_pins", "crossing_governor"]

#: The generator name of the crossing pin rows (``constraints/__init__``).
PIN_GEN = "runway_crossing_pin"

#: The ROLE whose faces ARE a runway x runway crossing (``classify/roles.py``
#: mints one per pairwise runway overlap, its ``ref`` the two runway ids
#: joined by ``+`` in sorted order).
CROSSING_ROLE = "runway_crossing"


class ChordReport(_t.TypedDict, total=False):
    """What the profile fit covered."""

    runways: int              # runways with two pins (a target profile)
    runways_without: int      # runways with fewer than two pins (DEM fit kept)
    vertices: int             # runway-family vertices given a profile target
    max_above_dem_m: float    # the largest target − DEM (the fill the target asks)
    max_below_dem_m: float    # the largest DEM − target (the cut)
    #: THE TARGET KIND (spec §21.2): ``trend`` where the ground's long-wave
    #: trend through the pins is the target, ``chord`` where the straight
    #: threshold chord is (the fallback), and per runway which it was
    target_kind: str
    window_m: float
    runways_trend: int
    runways_chord: int
    #: why the fallback ran, where it did (a degraded frame names itself)
    fallback: str
    by_runway: list   # [{"runway", "kind", "trend_max_off_chord_m"}]
    #: THE RUNWAY x RUNWAY CROSSINGS (RULINGS 2026-09-09z (1)): one record
    #: per crossing — the two runways, which one GOVERNS (its threshold is
    #: nearest the node), the node's elevation and the pinned vertex
    crossings: list   # [{"pair", "governing", "other", "z_pin_m", "pin_vertex", "pin_z_m"}]
    crossing_pins: int          # the crossing nodes actually pinned


@_dc.dataclass(frozen=True)
class _Chord:
    """One runway's chord: the axis frame and the line between its pins.

    ``knots`` (RULINGS 2026-09-09z (1), spec §17) are the CROSSING NODES a
    runway must pass through — ``(station, z)`` in this chord's own frame,
    sorted, strictly inside ``(s0, s1)``.  With none the chord is the
    straight line between the two CIFP pins, byte-for-byte as before; with
    them it is the PIECEWISE line through ``[(s0, z0)] + knots +
    [(s1, z1)]`` — the re-fit the ruling asks for."""

    a_xy: tuple[float, float]
    ux: float
    uy: float
    s0: float
    s1: float
    z0: float
    z1: float
    knots: tuple[tuple[float, float], ...] = ()
    #: THE TREND (spec §21.2 (1)): the ground's long-wave shape along this
    #: runway's ridge.  ``None`` = the CHORD FALLBACK (§21.2 (2)) — a
    #: degraded DEM frame or a ridge with no samples to fit — and every
    #: method below then reproduces the straight chord byte for byte.
    trend: _Trend | None = None

    def station(self, x: float, y: float) -> float:
        return (x - self.a_xy[0]) * self.ux + (y - self.a_xy[1]) * self.uy

    @property
    def kind(self) -> str:
        """``trend`` or ``chord`` — what this runway's target IS."""
        return "chord" if self.trend is None else "trend"

    def straight_z(self, s: float) -> float:
        """The line between the two CIFP pins, ignoring the trend and any
        knot — the STRAIGHT chord, the instrument every bow is read
        against and the fallback target of §21.2 (2)."""
        return self.z0 + (self.z1 - self.z0) * (s - self.s0) / (self.s1 - self.s0)

    def own_z(self, s: float) -> float:
        """This runway's OWN target profile, ignoring any crossing knot —
        the value a GOVERNING runway hands the crossing (v1's ``agreed``,
        §17.1).  Under §21 that is the trend through the pins, not the
        straight chord; with no trend it IS the straight chord."""
        return self._through(((self.s0, self.z0), (self.s1, self.z1)), s)

    def z(self, s: float) -> float:
        """The target profile at station ``s``: the trend carried through
        the control points — the two threshold pins and any crossing knot
        (§17.2) — by a PIECEWISE LINEAR correction (module docstring)."""
        if not self.knots:
            return self.own_z(s)
        return self._through(((self.s0, self.z0), *self.knots,
                              (self.s1, self.z1)), s)

    def _through(self, pts: tuple[tuple[float, float], ...], s: float) -> float:
        """``pts`` are the control points, ascending in station.  With no
        trend this is the piecewise line through them (the pre-§21
        behaviour, unchanged).  With one it is ``T(s)`` plus the linear
        function that makes the profile pass through the two control
        points bracketing ``s`` — the second derivative of the trend is
        therefore carried through untouched."""
        for (sa, za), (sb, zb) in zip(pts, pts[1:]):
            if s <= sb or (sb, zb) == pts[-1]:
                if sb - sa <= 0.0:
                    return za
                f = (s - sa) / (sb - sa)
                if self.trend is None:
                    return za + (zb - za) * f
                t, ta, tb = (self.trend.at(s), self.trend.at(sa),
                             self.trend.at(sb))
                if t is None or ta is None or tb is None:
                    return za + (zb - za) * f     # the window is empty: the chord
                ca, cb = za - ta, zb - tb
                return t + ca + (cb - ca) * f
        return pts[-1][1]

    def threshold_distance(self, s: float) -> float:
        """How far the station ``s`` is from this runway's NEAREST CIFP
        threshold (v1: ``min(|t|, |t-1|) x length``)."""
        return min(abs(s - self.s0), abs(s - self.s1))


@_dc.dataclass(frozen=True)
class Crossing:
    """One runway x runway crossing, resolved by the NEAREST THRESHOLD."""

    pair: str                      # the crossing face's ``ref`` (``A+B``)
    governing: str                 # the runway whose threshold is nearest
    other: str                     # the runway that grades to the node
    xy: tuple[float, float]        # the node: the two centrelines' intersection
    s_gov: float                   # its station on the governing chord
    s_other: float                 # its station on the other runway's chord
    z_pin: float                   # the governing chord's own value there
    d_gov: float                   # governing runway's threshold distance
    d_other: float                 # the other runway's threshold distance


def dem_degraded(airport: Airport) -> str:
    """Why the production DEM frame is DEGRADED, or ``""`` (spec §21.2 (2)).

    The ``--allow-degraded-dem`` FLAG is not the test — the flag only
    ACCEPTS a degradation; ``ProductionDem`` records one under
    ``provenance['degraded']`` only when a frame actually degraded.  A
    degraded frame keeps the STRAIGHT CHORD as the runway's target: a
    trend fitted to a surface the harness has refused is an invented
    value (plan §2)."""
    prov = getattr(getattr(airport, "dem", None), "provenance", None) or {}
    try:
        return str(prov.get("degraded") or "")
    except Exception:                     # a sampler with no mapping provenance
        return ""


def _trend(vw, chains: dict[str, list[list[int]]], rw_id: str, c: _Chord,
           pm: PlanarMap, window_m: float) -> _Trend | None:
    """The production DEM under this runway's own ridge, in ``c``'s station
    frame (module docstring), fitted by ``constraints/trend.py`` — the ONE
    construction §21 and §8.6 share.  ``None`` where fewer than three
    stations carry a sample, so the chord stands."""
    return _trend_of(((c.station(*vw.xy[v]), float(pm.vertices[v].dem_z))
                      for ch in chains.get(rw_id, []) for v in ch
                      if pm.vertices[v].dem_z is not None), window_m)


def _chords(pm: PlanarMap, law: Law, airport: Airport
            ) -> tuple[dict[str, _Chord], int]:
    """Runway id -> its TARGET PROFILE (the trend through its two threshold
    pins, else the straight chord — spec §21.2), and how many runways have
    fewer than two CIFP pins (those keep the DEM as their target)."""
    vw = view(pm, law)
    chains = ridge_chains(vw)
    pins = threshold_pins(pm, law, airport)
    window = float(law.tables.emit.design.runway_profile_window_m)
    degraded = dem_degraded(airport)
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
        c = _Chord(a_xy, ux, uy, st[p0], st[p1], pins[p0], pins[p1])
        if not degraded:
            c = _dc.replace(c, trend=_trend(vw, chains, rw.id, c, pm, window))
        chords[rw.id] = c
    return chords, n_without


def _axis_intersection(airport: Airport, a: str, b: str
                       ) -> tuple[float, float] | None:
    """Where the two runways' CENTRELINES cross, analytically from the
    apt.dat ends — the crossing NODE (spec §17.1 (1)).  ``None`` when the
    two axes are parallel or a runway id is unknown."""
    by_id = {rw.id: rw for rw in airport.runways}
    ra, rb = by_id.get(a), by_id.get(b)
    if ra is None or rb is None:
        return None
    (ax, ay), (bx, by) = ra.ends[0].xy, ra.ends[1].xy
    (cx, cy), (dx, dy) = rb.ends[0].xy, rb.ends[1].xy
    r = (bx - ax, by - ay)
    sdir = (dx - cx, dy - cy)
    den = r[0] * sdir[1] - r[1] * sdir[0]
    if abs(den) < 1e-9:
        return None
    t = ((cx - ax) * sdir[1] - (cy - ay) * sdir[0]) / den
    return (ax + t * r[0], ay + t * r[1])


def crossing_governor(airport: Airport, chords: dict[str, "_Chord"],
                      xy: tuple[float, float], a: str, b: str
                      ) -> tuple[str, str] | None:
    """(GOVERNING, OTHER) of a runway x runway crossing at ``xy`` (owner
    RULINGS 2026-09-09z (1); v1's ``runway_segments.py`` "closer-threshold
    runway dominates").

    The GOVERNING runway is the one whose nearest CIFP THRESHOLD is nearest
    the crossing node along its own axis — v1's reason verbatim: "a runway
    with thresholds close to the crossing has less profile flexibility ... a
    runway whose thresholds are far away has more total altitude budget to
    absorb a deviation."  Ties break to the LONGER runway, then to the lower
    id, so the answer never depends on the order the ids arrive in.  A
    runway with no chord (fewer than two CIFP pins) can never govern;
    ``None`` when neither has one."""
    by_id = {rw.id: rw for rw in airport.runways}

    def key(r: str) -> tuple[float, float, str] | None:
        c = chords.get(r)
        if c is None:
            return None
        rw = by_id.get(r)
        return (c.threshold_distance(c.station(*xy)),
                -(rw.length_m if rw is not None else 0.0), r)

    ka, kb = key(a), key(b)
    if ka is None and kb is None:
        return None
    if kb is None:
        return (a, b)
    if ka is None:
        return (b, a)
    return (a, b) if ka < kb else (b, a)


def runway_crossings(pm: PlanarMap, law: Law, airport: Airport,
                     chords: dict[str, "_Chord"] | None = None,
                     ) -> list[Crossing]:
    """Every runway x runway crossing, resolved (spec §17.1).

    One record per ``runway_crossing`` face pair (deduplicated by ``ref``,
    so a crossing broken into several faces by the noding is ONE node).
    The node is the two CENTRELINES' intersection; the governing runway is
    :func:`crossing_governor`'s; the pin value is the governing runway's
    OWN TARGET PROFILE there, clamped to its two thresholds (v1's
    beyond-threshold clamp).  Under §21 that profile is the trend through
    its pins, not the straight chord: the pin the other runway grades to is
    the value the governing runway is itself aiming at, which is what §17.1
    states and what the straight chord WAS before §21 (with no trend the
    two are the same value)."""
    if chords is None:
        chords, _ = _chords(pm, law, airport)
    vw = view(pm, law)
    out: list[Crossing] = []
    seen: set[str] = set()
    for f in vw.faces_of_role((CROSSING_ROLE,)):
        refs = [r for r in f.ref.split("+") if r]
        if len(refs) != 2 or f.ref in seen:
            continue
        seen.add(f.ref)
        xy = _axis_intersection(airport, refs[0], refs[1])
        if xy is None:
            continue
        pick = crossing_governor(airport, chords, xy, refs[0], refs[1])
        if pick is None:
            continue
        gov, other = pick
        cg = chords[gov]
        s_gov = cg.station(*xy)
        z_pin = cg.own_z(min(max(s_gov, cg.s0), cg.s1))
        co = chords.get(other)
        s_other = co.station(*xy) if co is not None else 0.0
        out.append(Crossing(f.ref, gov, other, xy, s_gov, s_other, z_pin,
                            cg.threshold_distance(s_gov),
                            co.threshold_distance(s_other) if co is not None else float("inf")))
    return out


def _with_knots(chords: dict[str, "_Chord"], crossings: list[Crossing]
                ) -> dict[str, "_Chord"]:
    """The chords RE-FIT through their crossing nodes (spec §17.2): the
    non-governing runway of each crossing gains a knot, so its target is
    the piecewise line threshold -> node -> threshold.  A node at or beyond
    a threshold mints no knot (the pin there IS the threshold's own value)."""
    knots: dict[str, list[tuple[float, float]]] = {}
    for x in crossings:
        c = chords.get(x.other)
        if c is None or not (c.s0 < x.s_other < c.s1):
            continue
        knots.setdefault(x.other, []).append((x.s_other, x.z_pin))
    if not knots:
        return chords
    out = dict(chords)
    for r, ks in knots.items():
        out[r] = _dc.replace(out[r], knots=tuple(sorted(ks)))
    return out


def _with_seam_knots(chords: dict[str, "_Chord"], pm: PlanarMap, law: Law
                     ) -> dict[str, "_Chord"]:
    """THE TILE SEAM IS A KNOT (§38 (2); owner RULINGS 2026-09-13ah,
    attributed 13am (7)).

    A seam vertex is a ``Pin`` at its own tile's DEM sample, held exactly
    — the same object as a CIFP threshold — so the runway's TARGET must
    pass through it, exactly as it passes through a runway x runway
    crossing node (:func:`_with_knots`).  Until 13ah ``_Chord.knots`` took
    only crossing pins and a seam vertex was never a control point, so the
    chord aimed BESIDE the value the pin holds and the end-zone chain paid
    the difference (the SPLP class: a 53-hop ``runway_end_zone`` chain
    down 02/20's 20-end, and the pin off its DEM by up to 3.430 m).

    The knots are this runway's own RIDGE vertices that are seam pins,
    valued at their DEM sample, strictly inside ``(s0, s1)``; a seam pin
    at or beyond a threshold mints none (the threshold's own pin IS the
    value there).  A runway that crosses no seam is untouched, so every
    single-tile airport reads byte for byte as before.
    """
    if not pm.seam_vertices or not chords:
        return chords
    vw = view(pm, law)
    chains = ridge_chains(vw)
    out = dict(chords)
    for r, c in chords.items():
        ks: list[tuple[float, float]] = []
        for ch in chains.get(r, []):
            for v in ch:
                if v not in pm.seam_vertices:
                    continue
                dz = pm.vertices[v].dem_z
                if dz is None:
                    continue
                s = c.station(*vw.xy[v])
                if c.s0 < s < c.s1:
                    ks.append((s, float(dz)))
        if ks:
            out[r] = _dc.replace(c, knots=tuple(sorted(set(c.knots) | set(ks))))
    return out


def runway_crossing_pins(pm: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE CROSSING NODE IS AN ANCHOR (owner RULINGS 2026-09-09z (1)): one
    hard ``Pin`` per (crossing, non-governing runway), on that runway's
    RIDGE vertex nearest the node, at its own RE-FIT chord's value there.

    The governing runway is never pinned — it solves the node under its own
    laws.  A vertex already carrying a CIFP threshold pin is never re-pinned
    (at CYXY the 14L/32R crossing sits ON 02/20's 20 threshold), and one
    vertex takes at most one crossing pin — the nearest crossing's."""
    vw = view(pm, law)
    chains = ridge_chains(vw)
    chords, _ = _chords(pm, law, airport)
    crossings = runway_crossings(pm, law, airport, chords)
    pins = _crossing_pin_map(pm, law, airport, vw, chains,
                             _with_seam_knots(_with_knots(chords, crossings),
                                              pm, law), crossings)
    return [Pin(v, float(z), Source(
        PIN_GEN, "RULINGS 2026-09-09z (1) nearest-threshold crossing anchor",
        (f"xing:{x.pair}", f"governs:{x.governing}", f"grades:{x.other}")))
        for v, (z, x) in sorted(pins.items())]


def _crossing_pin_map(pm: PlanarMap, law: Law, airport: Airport, vw,
                      chains: dict[str, list[list[int]]],
                      fitted: dict[str, "_Chord"], crossings: list[Crossing]
                      ) -> dict[int, tuple[float, Crossing]]:
    """Vertex -> ``(pinned z, its crossing)`` — the one site that picks the
    node vertex, so the generator and the chord report cannot disagree."""
    if not crossings:
        return {}
    thresholds = threshold_pins(pm, law, airport)
    best: dict[int, tuple[float, float, Crossing]] = {}
    for x in crossings:
        c = fitted.get(x.other)
        ridge = [v for ch in chains.get(x.other, []) for v in ch]
        if c is None or not ridge:
            continue
        v = min(ridge, key=lambda q: (vw.xy[q][0] - x.xy[0]) ** 2
                + (vw.xy[q][1] - x.xy[1]) ** 2)
        if v in thresholds:
            continue      # the node IS a CIFP threshold: it is already pinned
        d = ((vw.xy[v][0] - x.xy[0]) ** 2 + (vw.xy[v][1] - x.xy[1]) ** 2) ** 0.5
        if v in best and best[v][0] <= d:
            continue
        best[v] = (d, c.z(c.station(*vw.xy[v])), x)
    return {v: (z, x) for v, (_d, z, x) in best.items()}


def runway_chord_targets(pm: PlanarMap, law: Law, airport: Airport,
                         report: ChordReport | None = None, *,
                         fill_roles: tuple[str, ...] = (),
                         fill_within: str = "graded_strip") -> dict[int, float]:
    """Vertex -> TARGET PROFILE value for every runway-family vertex of a
    runway with two CIFP pins (module docstring): the ground's long-wave
    trend through the pins (spec §21), or the straight threshold chord
    where the DEM frame is degraded or the ridge cannot be fitted.

    ``fill_roles`` (an EXPERIMENT ARM, lane ``v2chord2`` for owner decision
    08g-2 — v1's strips and connectors ride the runway's fill): the faces
    of these roles ALSO take the crown-plane chord target, restricted to
    vertices incident to a ``fill_within`` face (the strip), so a
    connector beyond the strip keeps its own target.  A runway-family
    target always wins on a shared vertex."""
    vw = view(pm, law)
    chains = ridge_chains(vw)
    crown = law.tables.common.runway_crown_transverse
    half_of = {rw.id: rw.width_m / 2.0 for rw in airport.runways}
    straight, n_without = _chords(pm, law, airport)
    # THE NEAREST-THRESHOLD CROSSING NODE (RULINGS 2026-09-09z (1)): the
    # governing runway's chord is UNCHANGED across the crossing; every other
    # runway's is RE-FIT piecewise through the node.
    crossings = runway_crossings(pm, law, airport, straight)
    # §38 (2): the crossing nodes AND the tile-seam pins are control points
    chords = _with_seam_knots(_with_knots(straight, crossings), pm, law)
    if report is not None:
        kinds = [c.kind for c in chords.values()]
        report["window_m"] = round(float(
            law.tables.emit.design.runway_profile_window_m), 1)
        report["runways_trend"] = sum(1 for k in kinds if k == "trend")
        report["runways_chord"] = sum(1 for k in kinds if k == "chord")
        report["target_kind"] = ("trend" if report["runways_trend"] and not
                                 report["runways_chord"] else
                                 "chord" if not report["runways_trend"] else "mixed")
        deg = dem_degraded(airport)
        report["fallback"] = (f"degraded DEM frame: {deg}" if deg else
                              "" if not report["runways_chord"] else
                              "ridge with fewer than three DEM stations")
        # HOW FAR THE TARGET LEAVES THE STRAIGHT CHORD, per runway: the
        # curvature §21 buys, read at the target itself rather than at the
        # built surface (the report block does the built read)
        report["by_runway"] = [
            {"runway": r, "kind": c.kind,
             "trend_max_off_chord_m": round(max(
                 (abs(c.z(c.s0 + (c.s1 - c.s0) * i / 40.0)
                      - c.straight_z(c.s0 + (c.s1 - c.s0) * i / 40.0))
                  for i in range(41)), default=0.0), 3)}
            for r, c in sorted(chords.items())]
        report["crossings"] = [
            {"pair": x.pair, "governing": x.governing, "other": x.other,
             "z_pin_m": round(x.z_pin, 3),
             "gov_threshold_m": round(x.d_gov, 1),
             "other_threshold_m": round(x.d_other, 1)}
            for x in crossings]
    out: dict[int, float] = {}
    above = below = 0.0
    faces = [(f, False) for f in vw.faces_of_role(RUNWAY_FAMILY)]
    if fill_roles:
        faces += [(f, True) for f in vw.faces_of_role(fill_roles)]
    for f, is_fill in faces:
        if is_fill:
            refs = list(chords)                      # the nearest chain of any chord runway
        else:
            refs = [r for r in ([f.ref] if f.role == "runway" else f.ref.split("+")) if r in chords]
        if not refs:
            continue
        for v in vw.rings[f.id]:
            if v in out:
                continue
            if is_fill and f.role != fill_within and not any(
                    pm.faces[g].role == fill_within for g in pm.vertices[v].incident_faces):
                continue
            best: tuple[float, float, float] | None = None
            # (lateral d, chord z at the foot, that runway's half-width)
            p = vw.xy[v]
            for r in refs:
                c = chords[r]
                for ch in chains.get(r, []):
                    if len(ch) < 2:
                        continue
                    d, k, t, _s = project_to_chain(p, [vw.xy[q] for q in ch])
                    (xa, ya), (xb, yb) = vw.xy[ch[k]], vw.xy[ch[k + 1]]
                    sc = c.station(xa + t * (xb - xa), ya + t * (yb - ya))
                    if is_fill and not (c.s0 <= sc <= c.s1):
                        continue                 # a fill target never extrapolates past a pin
                    zc = c.z(sc)
                    if best is None or d < best[0]:
                        best = (d, zc, half_of.get(r, 0.0))
            if best is None:
                continue
            d, zc, half = best
            # §40 (1) THE CROWN STOPS AT THE RUNWAY EDGE (owner RULINGS
            # 2026-09-13co item 1).  The designed cross-fall is the
            # RUNWAY's, between its own edges; past them — a SHOULDER
            # vertex, pavement that joined the runway body — the target is
            # the runway EDGE's value, the datum the shoulder joins, and
            # the transverse MAXIMUM governs the fall from there.  MEASURED
            # at CYXY: without the clamp the target continues the crown at
            # exactly `runway_crown_transverse`, which IS the transverse
            # cap, so a 100 m shoulder reads 1.53 % against a 1.50 % cap —
            # 4 runway_transverse DEFECT rows (1.56-1.93 m, each 0.03 pp
            # over).  A vertex on the slab is UNMOVED (d <= half-width
            # there): every airport with no shoulder reads as before, and
            # the `fill_roles` experiment arm keeps its own unclamped
            # crown plane.
            out[v] = zc - crown * (d if is_fill or half <= 0.0 else min(d, half))
            dem = pm.vertices[v].dem_z
            if is_fill and dem is not None and out[v] < dem:
                continue                     # a fill target FILLS; where the DEM is higher it stays the target
            if dem is not None:
                above = max(above, out[v] - dem)
                below = max(below, dem - out[v])
    if report is not None:
        report.update(runways=len(chords), runways_without=n_without, vertices=len(out),
                      max_above_dem_m=round(above, 3), max_below_dem_m=round(below, 3),
                      crossing_pins=len(_crossing_pin_map(
                          pm, law, airport, vw, chains, chords, crossings)))
    return out


def with_runway_chord(pm: PlanarMap, law: Law, airport: Airport,
                      report: ChordReport | None = None, *,
                      fill_roles: tuple[str, ...] = ()) -> PlanarMap:
    """``pm`` with the chord targets merged into ``preferred_z`` (on a
    shared vertex the runway family's target wins: the runway is senior).
    ``fill_roles``: see ``runway_chord_targets`` (experiment arm).

    §50.1 (3) THE YIELD IS DERIVED HERE, ONCE.  This function already
    holds the pins, the chords and the crossings and is already called at
    exactly the right moment by every entry (``pipeline/build.py``,
    ``tools/v2_solve_replay.py``), so ``PlanarMap.runway_caps`` is set
    here and NO new call site exists to forget.  It is set on BOTH exits:
    a runway whose chord target is absent still carries a cap."""
    from .runway_yield import derive as _derive_caps
    caps = _derive_caps(pm, law, airport)
    targets = runway_chord_targets(pm, law, airport, report, fill_roles=fill_roles)
    if not targets:
        return _dc.replace(pm, runway_caps=caps) if caps else pm
    merged = dict(pm.preferred_z)
    merged.update(targets)
    return _dc.replace(pm, preferred_z=merged, runway_caps=caps)
