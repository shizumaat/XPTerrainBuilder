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
    """What the chord fit covered."""

    runways: int              # runways with two pins (a chord)
    runways_without: int      # runways with fewer than two pins (DEM fit kept)
    vertices: int             # runway-family vertices given a chord target
    max_above_dem_m: float    # the largest chord − DEM (the fill the target asks)
    max_below_dem_m: float    # the largest DEM − chord (the cut)
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

    def station(self, x: float, y: float) -> float:
        return (x - self.a_xy[0]) * self.ux + (y - self.a_xy[1]) * self.uy

    def straight_z(self, s: float) -> float:
        """The line between the two CIFP pins, ignoring any knot — the
        value a GOVERNING runway hands the crossing (v1's ``agreed``)."""
        return self.z0 + (self.z1 - self.z0) * (s - self.s0) / (self.s1 - self.s0)

    def z(self, s: float) -> float:
        if not self.knots:
            return self.straight_z(s)
        pts = [(self.s0, self.z0), *self.knots, (self.s1, self.z1)]
        for (sa, za), (sb, zb) in zip(pts, pts[1:]):
            if s <= sb or (sb, zb) == pts[-1]:
                if sb - sa <= 0.0:
                    return za
                return za + (zb - za) * (s - sa) / (sb - sa)
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


def _chords(pm: PlanarMap, law: Law, airport: Airport
            ) -> tuple[dict[str, _Chord], int]:
    """Runway id -> its STRAIGHT threshold chord, and how many runways have
    fewer than two CIFP pins (those keep the DEM as their target)."""
    vw = view(pm, law)
    chains = ridge_chains(vw)
    pins = threshold_pins(pm, law, airport)
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
    STRAIGHT chord there, clamped to its two thresholds (v1's
    beyond-threshold clamp)."""
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
        z_pin = cg.straight_z(min(max(s_gov, cg.s0), cg.s1))
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
                             _with_knots(chords, crossings), crossings)
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
    """Vertex -> chord target for every runway-family vertex of a runway
    with two CIFP pins (module docstring).

    ``fill_roles`` (an EXPERIMENT ARM, lane ``v2chord2`` for owner decision
    08g-2 — v1's strips and connectors ride the runway's fill): the faces
    of these roles ALSO take the crown-plane chord target, restricted to
    vertices incident to a ``fill_within`` face (the strip), so a
    connector beyond the strip keeps its own target.  A runway-family
    target always wins on a shared vertex."""
    vw = view(pm, law)
    chains = ridge_chains(vw)
    crown = law.tables.common.runway_crown_transverse
    straight, n_without = _chords(pm, law, airport)
    # THE NEAREST-THRESHOLD CROSSING NODE (RULINGS 2026-09-09z (1)): the
    # governing runway's chord is UNCHANGED across the crossing; every other
    # runway's is RE-FIT piecewise through the node.
    crossings = runway_crossings(pm, law, airport, straight)
    chords = _with_knots(straight, crossings)
    if report is not None:
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
            best: tuple[float, float] | None = None       # (lateral d, chord z at the foot)
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
                        best = (d, zc)
            if best is None:
                continue
            d, zc = best
            out[v] = zc - crown * d
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
    ``fill_roles``: see ``runway_chord_targets`` (experiment arm)."""
    targets = runway_chord_targets(pm, law, airport, report, fill_roles=fill_roles)
    if not targets:
        return pm
    merged = dict(pm.preferred_z)
    merged.update(targets)
    return _dc.replace(pm, preferred_z=merged)
