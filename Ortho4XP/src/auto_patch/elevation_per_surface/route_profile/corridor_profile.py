"""THE WHOLE-RUN CORRIDOR PROFILE — one corridor, one 1-D constrained
solve, end to end (staged-solve round, lane S2).

WHY THIS EXISTS
---------------
"One corridor = ONE continuous law object" (owner ruling 2026-08-12b) was
landed as a PLAN law: the course registers whole in ``grade_graph``'s
centreline specs, and ``tools/corridor_axis_coverage.py`` reads that back
off the patch.  Its VERTICAL half was never built.  What graded a service
corridor's elevation was a POINTWISE rule —
``anchors._svc_spine_station_seeds``'s ``tgt = min(max(de, lo), c)``: each
station independently clamps its own DEM sample into its own reach band.
A pointwise clamp against a cap-Lipschitz envelope is a bang-bang
operator by construction, and it is what HECA's spines measured:

* a 6.18 m cap-ridden hump (crest 30.11268,31.40684) with no anchor
  within 60 m — the clamp tracing a DEM hump because each station could,
  one station at a time;
* +/-8 % cap-riding flank runs — every station not DEM-feasible sits
  EXACTLY on the envelope, so whole runs ride the cap;
* -25 % / -19 % discharge pockets — the ``floor > ceiling`` break blend,
  a distance-weighted average of two contradicting regimes, which is not
  a lawful profile at all and was quarantined rather than solved.

THE LAW THIS MODULE IMPLEMENTS (round spec, "WHOLE-RUN CORRIDOR
PROFILE").  Each corridor's vertical profile is solved as ONE 1-D
constrained problem over the whole run:

* MOUTH ENDPOINTS are welded stage-A airside values, read-only (pegs);
* FREE ENDS are hard DEM ties (landed law, ``anchors.free_end_targets``)
  — also pegs;
* the INTERIOR obeys the road cap (``config.SERVICE_ROAD_MAX_GRADE``,
  the existing constant — this module mints NO new number);
* the profile is the SMOOTHEST LAWFUL PATH, never a cap-riding trace;
* FLAT IS LAWFUL (owner 2026-08-14, "DRAINAGE RULING SCOPE CLARIFIED":
  corridors and roads get NO added drainage curvature — no minimum slope
  is minted here, and a run whose pegs agree comes out flat);
* band-lawful displacement TRUMPS DEM in the interior — the tube is the
  law, DEM is not an objective, and its deviation is neither an error nor
  a report line (owner 2026-08-14, "DEM DEVIATION IS NOT AN ERROR AND IS
  NOT REPORTED").

THE SOLVER IS THE EXISTING ONE.  ``taut_string.string_with_pegs`` already
IS the whole-run 1-D constrained solve this law asks for: the shortest
path in ``(s, z)`` through a tube with exact pass-through pegs.  It is the
same construction the AIRSIDE spine profile uses (``construct_taut_strings``),
which excluded service corridors by explicit filter.  Admitting the
corridor to that construction — as its OWN law object, with its own cap
and its own band — is the whole mechanism; this module is the assembly,
the audit and the conflict report around it, never a second solver
(tool-discipline law: extend a near-fit, never fork it).

WHY THE STRING IS CAP-LAWFUL WITHOUT A SLOPE CONSTRAINT.  The tube walls
are the cap-Lipschitz reach band grown FROM the pegs
(``anchors.apply_service_road_dem_follow._reach``): every wall value at
station ``j`` already satisfies ``|wall_j - v_peg| <= cap * d(peg, j)``.
The taut string between two pegs never leaves the tube and bends only
onto a wall, so each of its grades is a chord slope to a wall value from
a peg value — bounded by the cap that built the wall.  :func:`audit_run`
VERIFIES that rather than assuming it, and any segment over cap is
reported, never swallowed.

INTEGRAL CONSTRAINTS (the KCLT refused-wall clause).  "Where the wall
exclusion removes a wall, a graded transition must replace it" — the
step's rise absorbed ALONG the run.  In this formulation that is not a
second mechanism: an interior elevation the corridor must meet is an
INTERIOR PEG, and the string absorbs the transition to it over the
available run at <= cap by construction.  Where the run cannot absorb it,
:func:`solve_run_profile` REPORTS the conflict with numbers (rise, run,
cap, required grade) — feasibility-is-guaranteed, never a quarantine and
never a bare step (weld-or-gap: there is NO wall fallback behind this).

CONFLICTS ARE REPORTED, NOT BLENDED.  An inverted tube (``floor >
ceiling``: two anchor regimes that contradict) used to become a
distance-weighted blend and a quarantine export.  Here it is RELAXED to
the minimal interval containing both walls — ``[min(f, c), max(f, c)]``,
which is what lets one continuous lawful path route through it — and
recorded as a :class:`CorridorConflict` carrying the deficit and the
binding peg pair.  The profile stays one object; the conflict stays
visible.

R5 — ROAD RUNS TRACK TERRAIN (service-road law spec, owner-ratified
2026-08-15)
-----------------------------------------------------------------------
The taut string draws the STRAIGHTEST lawful profile.  That is CORRECT
for an airside spine (a taxiway is a designed surface between designed
anchors) and WRONG for a road, whose owner-law is terrain-hugging: a
road strung between two mouths rides a CHORD — CYXY road 349 as a 5.2 m
causeway over a 2.7 % terrain dip at 0.4 % grade, the CYXY junction-190
complex flat at ~706 m under 718-722 m of HRDEM, HECA as an elevated
plateau.

:func:`track_dem_profile` is the road form of the same 1-D law object:
the CAP-CONSTRAINED LEAST-DEVIATION TRACKER of the run's low-passed
station DEM.  Same tube, same pegs, same cap, same audit and conflict
types — a different OBJECTIVE.  ``solve_run_profile`` (the taut string)
is untouched and remains the airside form.

Mechanism, three O(n) stages, no new constant and no new solver:

1. THE PEG CONE.  Each peg is a LAW TARGET the profile must pass
   through exactly, so at station ``i`` the cap alone already bounds the
   profile to ``[max_j(p_j - cap*|s_i - s_j|), min_j(p_j + cap*|s_i -
   s_j|)]``.  Both envelopes are inf-convolutions with ``cap*d`` and are
   computed by one forward and one backward pass (not an O(n*p) double
   loop).  Intersected with the reach-band tube, this is the admissible
   interval; where the two disagree the minimal convex relaxation
   ``[min, max]`` applies, exactly as :func:`_relax_tube` does (the
   contradiction is already reported as a ``peg_pair`` conflict).
2. THE SEED IS THE TERRAIN.  ``z_i = clamp(dem_i, admissible_i)`` — the
   source IS the DEM, which is what separates this from the retired
   warm-start hazard class (whose carrier was cone-MIDPOINT-seeded at
   range and therefore flattened).  Pegs are written exactly.
3. THE CAP-LIPSCHITZ PROJECTION.  ``U_i = min_j(z_j + cap*d_ij)`` (the
   largest cap-Lipschitz minorant) and ``L_i = max_j(z_j - cap*d_ij)``
   (the smallest cap-Lipschitz majorant) are the same forward/backward
   pass pair; ``z' = (U + L)/2`` is cap-Lipschitz and is the MINIMAL
   move in the sup norm: no cap-Lipschitz profile is closer to ``z``
   than ``max_ij (z_i - z_j - cap*d_ij)^+ / 2``, and ``z'`` attains it.
   Where terrain stays within cap, ``U = L = z`` and the profile IS the
   terrain; where terrain out-runs the cap it departs, minimally.

PEGS COME OUT EXACT.  At a peg station ``p`` the cone collapses to
``[p, p]``, so every clamped ``z_j`` satisfies ``|z_j - p| <=
cap*d_pj``; therefore ``U_p = L_p = z_p = p``.  (Mutually infeasible
pegs are the reported ``peg_pair`` conflict and keep the string's own
semantics: the peg wins, the segment is audited over-cap.)

THE TUBE STILL BINDS.  The band walls are themselves cap-Lipschitz
(grown from the anchors at this same cap), and the inf-convolution of a
function under a cap-Lipschitz ceiling stays under it — so ``z'`` never
leaves the relaxed tube, and no post-clamp (which would break the cap)
is needed.

DEM DEVIATION MINTS NO CONFLICT (owner 2026-08-14, "DEM DEVIATION IS
NOT AN ERROR AND IS NOT REPORTED").  Departure spans ride the AUDIT —
which is the round's own instrument, not the census — so the acceptance
read can see where the cap out-ran the terrain without a single row
being reported anywhere a defect is counted.

R5c — GRADED-ROAD CHARACTER (service-road law spec, 2026-08-15; owner
in-sim on R5, CYXY 60.7087015,-135.0746305)
-----------------------------------------------------------------------
R5's tracker follows the low-passed terrain FAITHFULLY — including its
wiggles — where the owner wants ROAD character: "a smooth graded
surface", not terrain-hugging bumps.  :func:`_suppress_reversals` is
the tracker's last stage: every grade REVERSAL (a rise-fall-rise or
fall-rise-fall) whose INTERIOR AMPLITUDE is below
``config.SVC_PROFILE_REVERSAL_MIN_M`` is levelled through — a MONOTONE
BRIDGE between the excursion's endpoints — leaving piecewise-monotone
ramps between the terrain features that are real.  It is an AMPLITUDE
filter, not a smoothing length: a 2 m terrain feature survives at any
wavelength, and a 0.2 m wiggle dies at any wavelength.

Three properties make it safe to run AFTER the cap-Lipschitz
projection rather than instead of it:

* PEGS ARE FIXED TURNING POINTS.  A peg is a law target, so it can
  never be filtered away and no bridge may span it — the peg values
  come out of this stage untouched.
* THE BRIDGE IS CAP-LAWFUL BY CONSTRUCTION.  The monotone bridge is a
  running max (rising run) / running min (falling run) of the tracker
  profile clamped to the run's far endpoint; a running extremum of a
  cap-Lipschitz sequence is cap-Lipschitz with the SAME constant, and
  clamping against a constant preserves it.
* THE TUBE STILL BINDS.  The bridge is re-clamped into (tube ∩ peg
  cone) and re-projected onto the cap-Lipschitz set, so a bridge that
  would push through a band wall yields to the wall — character never
  outranks law.  Where nothing binds (the common case) the re-clamp
  and re-projection are the identity and the bridge stands as drawn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Sequence

from .taut_string import string_with_pegs

__all__ = [
    "CAP_RIDE_FRACTION",
    "CAP_RIDE_MIN_SEGMENTS",
    "CorridorConflict",
    "RunAudit",
    "RunProfile",
    "audit_run",
    "monotone_bridge",
    "solve_run_profile",
    "track_dem_profile",
    "turning_points",
]

#: A grade at or above this fraction of the cap counts as RIDING it.  A
#: reporting threshold for the acceptance instrument only — it constrains
#: nothing and is not a law value (the law value is the cap itself).
CAP_RIDE_FRACTION = 0.995

#: Consecutive cap-riding segments before the run is reported as a
#: cap-riding RUN (a single bend onto a wall is lawful and expected; a
#: RUN is the bang-bang signature).
CAP_RIDE_MIN_SEGMENTS = 3

#: Floating-point slack for the cap audit and the tube checks.
_TOL = 1e-9

#: The standing 0.01 m elevation materiality floor (round spec,
#: "Materiality: 0.01 m elevation classes").  A tube inversion smaller
#: than this is the two reach fields' float noise, not a contradiction.
MATERIALITY_M = 0.01


@dataclass(frozen=True)
class CorridorConflict:
    """A law conflict on one run, reported with its numbers.

    ``kind`` is one of:

    ``"inverted_tube"``
        ``floor > ceiling`` at a station: two anchor regimes contradict
        there.  ``deficit_m`` is ``floor - ceiling``.
    ``"peg_pair"``
        two consecutive pegs whose separation cannot carry their
        difference at the cap: ``rise_m / run_m > cap``.  This is the
        integral-constraint infeasibility the round spec asks to be
        reported with numbers.
    ``"over_cap_segment"``
        an emitted segment steeper than the cap — only reachable through
        a relaxed inverted tube, and the honest read-out of it.
    """

    kind: str
    station_index: int
    station_s_m: float
    cap: float
    floor: float | None = None
    ceiling: float | None = None
    deficit_m: float | None = None
    rise_m: float | None = None
    run_m: float | None = None
    required_grade: float | None = None
    xy: tuple[float, float] | None = None

    def describe(self) -> str:
        if self.kind == "inverted_tube":
            return (f"inverted tube at s={self.station_s_m:.1f} m: "
                    f"floor {self.floor:.3f} > ceiling {self.ceiling:.3f} "
                    f"(deficit {self.deficit_m:.3f} m)")
        if self.kind == "peg_pair":
            return (f"peg pair at s={self.station_s_m:.1f} m: rise "
                    f"{self.rise_m:.3f} m over run {self.run_m:.1f} m "
                    f"needs {self.required_grade * 100:.2f} % > cap "
                    f"{self.cap * 100:.2f} %")
        return (f"segment at s={self.station_s_m:.1f} m rides "
                f"{self.required_grade * 100:.2f} % > cap "
                f"{self.cap * 100:.2f} %")


@dataclass(frozen=True)
class RunAudit:
    """What the emitted run actually does — the acceptance read-out."""

    segments: int = 0
    worst_grade: float = 0.0
    over_cap_segments: int = 0
    cap_ride_segments: int = 0
    cap_ride_runs: int = 0
    cap_ride_length_m: float = 0.0
    #: R5 — where the CAP (or the tube) forced the tracker off the
    #: terrain it tracks.  Populated by :func:`track_dem_profile` only.
    #: These are AUDIT rows, never conflicts and never census rows: DEM
    #: deviation is not an error and is not reported (owner 2026-08-14).
    dem_stations: int = 0
    dem_departure_stations: int = 0
    dem_departure_max_m: float = 0.0
    #: ``(s_start_m, s_end_m)`` per contiguous departure span.
    dem_departure_spans: tuple[tuple[float, float], ...] = ()
    #: R5c — grade REVERSALS collapsed into monotone bridges, and the
    #: largest interior amplitude that was levelled through.  Audit
    #: rows: character is not a defect class and mints no census row.
    reversals_collapsed: int = 0
    reversal_max_amplitude_m: float = 0.0
    #: Turning points the emitted profile still carries (its
    #: piecewise-monotone segment count is ``reversals_kept + 1``).
    reversals_kept: int = 0


@dataclass
class RunProfile:
    """One corridor run's solved profile."""

    z: list[float]
    pegs: dict[int, float]
    audit: RunAudit = field(default_factory=RunAudit)
    conflicts: list[CorridorConflict] = field(default_factory=list)
    #: True when the run had fewer than two pegs and DEM end ties were
    #: synthesised to make the run well-posed (the free-end DEM tie law
    #: generalised: a terminus over open terrain is a law target).
    synthetic_end_ties: int = 0


def _relax_tube(floor: list[float], ceiling: list[float],
                stations: Sequence[float], cap: float,
                xy: Sequence[tuple[float, float]] | None,
                conflicts: list[CorridorConflict]) -> None:
    """Make the tube non-inverted IN PLACE, recording every inversion.

    The minimal convex relaxation is ``[min(f, c), max(f, c)]``: it
    contains both contradicting walls, so one continuous lawful path can
    route through the conflict instead of a distance-weighted blend
    standing in for a profile.  The conflict is not softened — it is
    RECORDED with the deficit that names it.
    """
    for i, (f, c) in enumerate(zip(floor, ceiling)):
        if f <= c:
            continue
        # ALWAYS levelled — an inversion of any size would make the tube
        # ill-formed for the string.  REPORTED only above the standing
        # 0.01 m elevation materiality floor: below it the "conflict" is
        # the two reach fields' own float noise (measured at HECA: a
        # 5e-14 m inversion at a weld), and reporting it would bury the
        # real contradictions this list exists to surface.
        if f - c > MATERIALITY_M:
            conflicts.append(CorridorConflict(
                kind="inverted_tube", station_index=i,
                station_s_m=float(stations[i]), cap=cap,
                floor=float(f), ceiling=float(c), deficit_m=float(f - c),
                xy=(xy[i] if xy is not None else None)))
        floor[i], ceiling[i] = c, f


def _peg_pair_conflicts(stations: Sequence[float], pegs: dict[int, float],
                        cap: float,
                        xy: Sequence[tuple[float, float]] | None,
                        conflicts: list[CorridorConflict]) -> None:
    """THE INTEGRAL CONSTRAINT, checked before the string is drawn.

    Two consecutive pegs are a rise over a run.  If ``rise/run > cap`` no
    lawful profile joins them — the available run cannot absorb the step
    — and that is a REPORTED law conflict with numbers, never a
    quarantine and never a bare step (round spec, pre-delegated decision:
    "report with numbers; no quarantine").
    """
    order = sorted(pegs)
    for p, q in zip(order, order[1:]):
        run = float(stations[q]) - float(stations[p])
        if run <= _TOL:
            continue
        rise = abs(float(pegs[q]) - float(pegs[p]))
        required = rise / run
        if required <= cap + _TOL:
            continue
        conflicts.append(CorridorConflict(
            kind="peg_pair", station_index=p,
            station_s_m=float(stations[p]), cap=cap,
            rise_m=rise, run_m=run, required_grade=required,
            xy=(xy[p] if xy is not None else None)))


def audit_run(stations: Sequence[float], z: Sequence[float], cap: float,
              *, xy: Sequence[tuple[float, float]] | None = None,
              conflicts: list[CorridorConflict] | None = None,
              emit_noise_m: float = 0.0) -> RunAudit:
    """Measure the emitted run: worst grade, over-cap segments, and
    CAP-RIDING RUNS (the bang-bang signature the round must show gone).

    Cap compliance is VERIFIED here rather than assumed from the band's
    construction; an over-cap segment is appended to ``conflicts`` when
    one is supplied.

    ``emit_noise_m`` is the elevation QUANTUM of the values being read.
    In the solver it is 0 (exact floats).  A reader working off an
    emitted patch passes the emit precision (2 decimals = 0.01 m), which
    on a short station spacing swamps the cap on its own — the same
    allowance ``check_grade._check_spine_curvature`` makes, for the same
    reason, so a rounding artefact is never reported as a pocket.
    """
    worst = 0.0
    over = 0
    ride_seg = 0
    ride_runs = 0
    ride_len = 0.0
    run_len = 0
    ride_floor = CAP_RIDE_FRACTION * cap
    for i in range(1, len(z)):
        ds = float(stations[i]) - float(stations[i - 1])
        if ds <= _TOL:
            continue
        g = abs(float(z[i]) - float(z[i - 1])) / ds
        worst = max(worst, g)
        if g > cap + 1e-6 + (emit_noise_m / ds if emit_noise_m else 0.0):
            over += 1
            if conflicts is not None:
                conflicts.append(CorridorConflict(
                    kind="over_cap_segment", station_index=i,
                    station_s_m=float(stations[i]), cap=cap,
                    rise_m=abs(float(z[i]) - float(z[i - 1])),
                    run_m=ds, required_grade=g,
                    xy=(xy[i] if xy is not None else None)))
        if g >= ride_floor:
            ride_seg += 1
            run_len += 1
            ride_len += ds
        else:
            if run_len >= CAP_RIDE_MIN_SEGMENTS:
                ride_runs += 1
            run_len = 0
    if run_len >= CAP_RIDE_MIN_SEGMENTS:
        ride_runs += 1

    return RunAudit(segments=max(0, len(z) - 1), worst_grade=worst,
                    over_cap_segments=over, cap_ride_segments=ride_seg,
                    cap_ride_runs=ride_runs, cap_ride_length_m=ride_len)


def solve_run_profile(stations: Sequence[float],
                      floor: Sequence[float],
                      ceiling: Sequence[float],
                      pegs: dict[int, float],
                      cap: float,
                      *,
                      dem: Sequence[float] | None = None,
                      xy: Sequence[tuple[float, float]] | None = None
                      ) -> RunProfile | None:
    """Solve ONE corridor run's whole-run vertical profile.

    ``stations``   strictly increasing arclengths along the run (m).
    ``floor``/``ceiling``  the run's reach band per station (``+/-inf``
                   allowed where a station is unreachable from any peg).
    ``pegs``       station index -> value: mouth welds (stage-A airside
                   values, read-only) and free-end DEM ties, plus any
                   INTERIOR value the run must meet (a refused wall's
                   step becomes one of these).
    ``cap``        the road cap, ``config.SERVICE_ROAD_MAX_GRADE``.
    ``dem``        optional per-station DEM, used ONLY to synthesise end
                   ties on an under-pegged run.  It is never an objective
                   and its deviation is never measured: DEM deviation is
                   not an error and is not reported (owner 2026-08-14).

    Returns ``None`` when the run is too short or cannot be made
    well-posed (no pegs and no DEM) — the caller keeps its own fallback.
    """
    k = len(stations)
    if k < 2:
        return None
    floor = [float(v) for v in floor]
    ceiling = [float(v) for v in ceiling]
    conflicts: list[CorridorConflict] = []

    _relax_tube(floor, ceiling, stations, cap, xy, conflicts)

    work = {int(i): float(v) for i, v in pegs.items()
            if 0 <= int(i) < k and math.isfinite(float(v))}
    synthetic = 0
    if len(work) < 2 and dem is not None:
        # THE FREE-END DEM TIE, generalised: a run with fewer than two
        # law targets is not well posed, and its terminus over open
        # terrain is exactly what the landed free-end law ties to DEM.
        for end in (0, k - 1):
            if end in work:
                continue
            d = dem[end] if end < len(dem) else None
            if d is None or not math.isfinite(float(d)):
                continue
            v = min(max(float(d), floor[end]), ceiling[end])
            if not math.isfinite(v):
                continue
            work[end] = v
            synthetic += 1
    if len(work) < 2:
        return None

    _peg_pair_conflicts(stations, work, cap, xy, conflicts)

    z = string_with_pegs(list(map(float, stations)), floor, ceiling, work)
    if z is None:                                    # pragma: no cover
        return None

    audit = audit_run(stations, z, cap, xy=xy, conflicts=conflicts)
    return RunProfile(z=z, pegs=work, audit=audit, conflicts=conflicts,
                      synthetic_end_ties=synthetic)


# ── R5: THE CAP-CONSTRAINED LEAST-DEVIATION TERRAIN TRACKER ─────────

def _lipschitz_min_envelope(stations: Sequence[float], seed: list[float],
                            cap: float) -> list[float]:
    """``E_i = min_j (seed_j + cap * |s_i - s_j|)`` — the inf-convolution
    of ``seed`` with the cap metric, in one forward and one backward
    pass.  ``+inf`` seeds are inert (they name "no constraint here")."""
    e = list(seed)
    for i in range(1, len(e)):
        b = e[i - 1] + cap * (float(stations[i]) - float(stations[i - 1]))
        if b < e[i]:
            e[i] = b
    for i in range(len(e) - 2, -1, -1):
        b = e[i + 1] + cap * (float(stations[i + 1]) - float(stations[i]))
        if b < e[i]:
            e[i] = b
    return e


def _lipschitz_max_envelope(stations: Sequence[float], seed: list[float],
                            cap: float) -> list[float]:
    """``E_i = max_j (seed_j - cap * |s_i - s_j|)`` — the sup-convolution
    twin of :func:`_lipschitz_min_envelope` (``-inf`` seeds inert)."""
    e = list(seed)
    for i in range(1, len(e)):
        b = e[i - 1] - cap * (float(stations[i]) - float(stations[i - 1]))
        if b > e[i]:
            e[i] = b
    for i in range(len(e) - 2, -1, -1):
        b = e[i + 1] - cap * (float(stations[i + 1]) - float(stations[i]))
        if b > e[i]:
            e[i] = b
    return e


def _fill_dem(dem: Sequence[float | None],
              stations: Sequence[float]) -> tuple[list[float], list[bool]] | None:
    """Return ``(values, sampled)`` — the DEM with interior holes bridged
    by linear interpolation in ``s`` and the ends held flat at the
    nearest sample.  ``sampled[i]`` marks a station that really carries a
    DEM sample (only those are audited for departure).  ``None`` when the
    run carries no sample at all: there is no terrain to track, and the
    caller keeps its own fallback."""
    k = len(stations)
    known = [i for i in range(k)
             if i < len(dem) and dem[i] is not None
             and math.isfinite(float(dem[i]))]
    if not known:
        return None
    vals = [0.0] * k
    sampled = [False] * k
    for i in known:
        vals[i] = float(dem[i])
        sampled[i] = True
    # One linear sweep: nearest sample at or before / at or after i.
    prev_i = [-1] * k
    p = -1
    for i in range(k):
        if sampled[i]:
            p = i
        prev_i[i] = p
    next_i = [-1] * k
    n = -1
    for i in range(k - 1, -1, -1):
        if sampled[i]:
            n = i
        next_i[i] = n
    for i in range(k):
        if sampled[i]:
            continue
        a, b = prev_i[i], next_i[i]
        if a >= 0 and b >= 0:
            sa, sb = float(stations[a]), float(stations[b])
            t = ((float(stations[i]) - sa) / (sb - sa)) if sb > sa else 0.0
            vals[i] = vals[a] + (vals[b] - vals[a]) * t
        elif a >= 0:
            vals[i] = vals[a]
        else:
            vals[i] = vals[b]
    return vals, sampled


# ── R5c: REVERSAL SUPPRESSION — the graded-road character filter ────

def turning_points(z: Sequence[float], *,
                   fixed: Sequence[int] = (),
                   tol: float = 1e-12) -> list[int]:
    """The profile's DIRECTION CHANGES, plus both ends and ``fixed``.

    Consecutive entries bound a MONOTONE run of ``z``.  Flats belong to
    the run they extend (a plateau is not a reversal), and ``fixed``
    indices — the run's pegs — are always kept: a peg is a law target,
    so no bridge may span it and no filter may remove it.
    """
    k = len(z)
    if k < 2:
        return list(range(k))
    keep = {0, k - 1}
    keep.update(int(i) for i in fixed if 0 <= int(i) < k)
    cur = 0
    for i in range(1, k):
        d = float(z[i]) - float(z[i - 1])
        s = 0 if abs(d) <= tol else (1 if d > 0.0 else -1)
        if s == 0:
            continue
        if cur == 0:
            cur = s
        elif s != cur:
            keep.add(i - 1)             # the extremum ends the old run
            cur = s
    return sorted(keep)


def monotone_bridge(z: Sequence[float], a: int, b: int) -> list[float]:
    """The MONOTONE BRIDGE of ``z`` over ``[a, b]``: the running
    extremum toward ``z[b]``, clamped to it.

    Rising (``z[b] >= z[a]``) it is the running MAX clamped from above
    by ``z[b]``; falling, the running MIN clamped from below.  Both
    endpoints come out exactly as they went in, the interior is
    monotone, and the result is cap-Lipschitz whenever ``z`` is — a
    running extremum can never move by more than the step that produced
    it (``|M_i - M_{i-1}| = max(0, z_i - M_{i-1}) <= max(0, z_i -
    z_{i-1})``), and clamping against a constant only shrinks steps.
    """
    out = [float(v) for v in z]
    if b <= a:
        return out
    va, vb = out[a], out[b]
    prev = va
    if vb >= va:
        for i in range(a + 1, b):
            v = min(max(out[i], prev), vb)
            out[i] = v
            prev = v
    else:
        for i in range(a + 1, b):
            v = max(min(out[i], prev), vb)
            out[i] = v
            prev = v
    return out


def _suppress_reversals(stations: Sequence[float], z: list[float],
                        lo: Sequence[float], hi: Sequence[float],
                        pegs: dict[int, float], cap: float,
                        min_amplitude_m: float
                        ) -> tuple[list[float], int, float, int]:
    """R5c(1): collapse sub-materiality grade REVERSALS into monotone
    ramps — the graded-road character filter.

    An EXCURSION is one monotone run between two consecutive turning
    points; its AMPLITUDE is the elevation it covers.  An INTERIOR
    excursion — one with a run on both sides, i.e. the spec's
    rise-fall-rise or fall-rise-fall — below ``min_amplitude_m`` is not
    a terrain feature a road should ramp for, so its two turning points
    are dropped and the runs on either side merge into one:
    repeatedly, smallest first, so a stack of small wiggles inside one
    ramp dies together while a real feature between them survives.
    Then each surviving run is redrawn as a :func:`monotone_bridge`.

    Law outranks character, in this order:

    * pegs are FIXED turning points (never dropped, never spanned);
    * the bridged profile is re-clamped into ``[lo, hi]`` — the tube
      intersected with the peg cone — and re-projected onto the
      cap-Lipschitz set, so the cap and the band both still bind;
    * pegs are rewritten exactly afterwards.

    Returns ``(z, collapsed, worst_amplitude_m, turning_points_kept)``.
    """
    k = len(z)
    if k < 3 or min_amplitude_m <= 0.0:
        return z, 0, 0.0, max(0, len(turning_points(z)) - 2)

    fixed = {int(i) for i in pegs if 0 <= int(i) < k}
    fixed.update((0, k - 1))
    tp = turning_points(z, fixed=fixed)
    collapsed = 0
    worst = 0.0
    # THE PATTERN IS THE SPEC'S: rise-fall-rise (or fall-rise-fall) — an
    # excursion with a run on BOTH sides.  Only its two INTERIOR turning
    # points are dropped, never a run's own end.
    #
    # Why not the ends too: an end excursion is a HALF feature, and
    # collapsing one re-measures its neighbour against the run's
    # endpoint instead of the extremum it actually turned at, so the
    # amplitudes cascade downward and a genuine feature dies.  Measured
    # on the R5 twin ``test_r5_empty_pegs_still_returns_a_profile_that_
    # tracks_dem``: a 0.6 m sine (well over the 0.4 m floor) has 0.3 m
    # HALF-excursions at both ends, and end-aware collapsing ate the
    # whole feature in three cascading steps.  A single residual
    # reversal at a run's tail is what the R5c acceptance already
    # allows ("monotone within one reversal").
    while len(tp) >= 4:
        best = None
        for m in range(1, len(tp) - 2):
            a, b = tp[m], tp[m + 1]
            if a in fixed or b in fixed:
                continue                # a peg is a law target, not a wiggle
            amp = abs(z[b] - z[a])
            if amp >= min_amplitude_m:
                continue
            if best is None or amp < best[0]:
                best = (amp, m)
        if best is None:
            break
        amp, m = best
        del tp[m:m + 2]
        collapsed += 1
        worst = max(worst, amp)

    if collapsed:
        out = list(z)
        for m in range(len(tp) - 1):
            bridged = monotone_bridge(out, tp[m], tp[m + 1])
            out[tp[m]:tp[m + 1] + 1] = bridged[tp[m]:tp[m + 1] + 1]
        # LAW OUTRANKS CHARACTER: back into (tube ∩ peg cone), back onto
        # the cap-Lipschitz set, pegs exact.  Where nothing binds these
        # three are the identity and the bridge stands as drawn.
        out = [min(max(out[i], float(lo[i])), float(hi[i]))
               for i in range(k)]
        for i, v in pegs.items():
            if 0 <= int(i) < k:
                out[int(i)] = float(v)
        upper = _lipschitz_min_envelope(stations, out, cap)
        lower = _lipschitz_max_envelope(stations, out, cap)
        out = [0.5 * (upper[i] + lower[i]) for i in range(k)]
        for i, v in pegs.items():
            if 0 <= int(i) < k:
                out[int(i)] = float(v)
        z = out

    # ``reversals_kept`` measures the EMITTED profile, so pegs are not
    # forced into the count: it is the road's real direction changes.
    return z, collapsed, worst, max(0, len(turning_points(z)) - 2)


def track_dem_profile(stations: Sequence[float],
                      floor: Sequence[float],
                      ceiling: Sequence[float],
                      pegs: dict[int, float],
                      cap: float,
                      *,
                      dem: Sequence[float | None],
                      xy: Sequence[tuple[float, float]] | None = None,
                      reversal_min_m: float | None = None
                      ) -> RunProfile | None:
    """R5: solve ONE service-road run's profile as the CAP-CONSTRAINED
    LEAST-DEVIATION TRACKER of ``dem``.

    Same contract as :func:`solve_run_profile` — same arguments, same
    :class:`RunProfile` shape, same audit and conflict types — with the
    OBJECTIVE swapped: instead of the shortest path through the tube
    (which draws a chord, the causeway/canyon defect R5 names), this is
    the terrain, moved as little as the cap and the tube allow.

    ``dem``   per-station low-passed DEM (``smooth_de``), ``None``
              entries allowed: interior holes interpolate, the ends hold
              flat, and only really-sampled stations are audited for
              departure.  A run with NO sample returns ``None``.
    ``reversal_min_m``
              R5c: the grade-REVERSAL amplitude floor.  ``None`` (the
              production path) takes ``config.SVC_PROFILE_REVERSAL_MIN_M``;
              ``0.0`` disables the character filter and returns the bare
              R5 tracker (what the R5 twins measure).

    Pegs come out EXACT.  Every adjacent-station grade obeys ``cap``.
    DEM deviation mints NO conflict — the departure spans ride
    ``RunProfile.audit`` (``dem_departure_*``), which is the round's
    instrument, never the census.

    Returns ``None`` when the run is too short or carries no terrain.
    """
    k = len(stations)
    if k < 2:
        return None
    filled = _fill_dem(dem, stations)
    if filled is None:
        return None
    de, sampled = filled

    floor = [float(v) for v in floor]
    ceiling = [float(v) for v in ceiling]
    conflicts: list[CorridorConflict] = []
    _relax_tube(floor, ceiling, stations, cap, xy, conflicts)

    work = {int(i): float(v) for i, v in pegs.items()
            if 0 <= int(i) < k and math.isfinite(float(v))}
    _peg_pair_conflicts(stations, work, cap, xy, conflicts)

    # 1. THE PEG CONE, intersected with the tube.
    inf = float("inf")
    cone_hi = _lipschitz_min_envelope(
        stations, [work.get(i, inf) for i in range(k)], cap)
    cone_lo = _lipschitz_max_envelope(
        stations, [work.get(i, -inf) for i in range(k)], cap)
    lo = [max(floor[i], cone_lo[i]) for i in range(k)]
    hi = [min(ceiling[i], cone_hi[i]) for i in range(k)]
    for i in range(k):
        if lo[i] > hi[i]:
            # The minimal convex relaxation _relax_tube applies, applied
            # to the tube-vs-cone contradiction: the peg pair that mints
            # it is already a reported conflict.
            lo[i], hi[i] = hi[i], lo[i]

    # 2. THE SEED IS THE TERRAIN (pegs written exactly).
    z = [min(max(de[i], lo[i]), hi[i]) for i in range(k)]
    for i, v in work.items():
        z[i] = v

    # 3. THE MINIMAL CAP-LIPSCHITZ PROJECTION.
    upper = _lipschitz_min_envelope(stations, z, cap)   # U <= z
    lower = _lipschitz_max_envelope(stations, z, cap)   # L >= z
    z = [0.5 * (upper[i] + lower[i]) for i in range(k)]
    for i, v in work.items():
        z[i] = v                        # exact by construction; explicit

    # 4. R5c — GRADED-ROAD CHARACTER: sub-materiality grade reversals
    #    become monotone ramps.  Law still outranks character: the
    #    bridge is re-clamped into (tube ∩ peg cone), re-projected onto
    #    the cap-Lipschitz set and the pegs rewritten exactly.
    if reversal_min_m is None:
        try:
            from auto_patch.config import SVC_PROFILE_REVERSAL_MIN_M
            reversal_min_m = float(SVC_PROFILE_REVERSAL_MIN_M)
        except Exception:                                # pragma: no cover
            reversal_min_m = 0.0
    z, _rev_n, _rev_amp, _rev_kept = _suppress_reversals(
        stations, z, lo, hi, work, cap, float(reversal_min_m))

    audit = audit_run(stations, z, cap, xy=xy, conflicts=conflicts)
    audit = replace(audit, reversals_collapsed=_rev_n,
                    reversal_max_amplitude_m=_rev_amp,
                    reversals_kept=_rev_kept)

    # THE DEPARTURE SPANS — audit only, no conflict, no census row.
    spans: list[tuple[float, float]] = []
    n_dep = 0
    worst_dep = 0.0
    open_from: float | None = None
    last_s = 0.0
    for i in range(k):
        if not sampled[i]:
            continue
        d = abs(z[i] - de[i])
        s_i = float(stations[i])
        if d > MATERIALITY_M:
            n_dep += 1
            worst_dep = max(worst_dep, d)
            if open_from is None:
                open_from = s_i
            last_s = s_i
        elif open_from is not None:
            spans.append((open_from, last_s))
            open_from = None
    if open_from is not None:
        spans.append((open_from, last_s))

    audit = replace(audit, dem_stations=sum(1 for f in sampled if f),
                    dem_departure_stations=n_dep,
                    dem_departure_max_m=worst_dep,
                    dem_departure_spans=tuple(spans))
    return RunProfile(z=z, pegs=work, audit=audit, conflicts=conflicts,
                      synthetic_end_ties=0)
