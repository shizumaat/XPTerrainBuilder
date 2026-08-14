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
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from .taut_string import string_with_pegs

__all__ = [
    "CAP_RIDE_FRACTION",
    "CAP_RIDE_MIN_SEGMENTS",
    "CorridorConflict",
    "RunAudit",
    "RunProfile",
    "audit_run",
    "solve_run_profile",
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
