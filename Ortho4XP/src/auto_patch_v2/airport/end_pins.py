"""THE RUNWAY-END PIN RULE — where each end's height pin sits and whether
its CIFP value is trusted (owner RULINGS 2026-10-25a, 2026-10-26a,
2026-10-26e; issues #1342, #1358, #1394; spec and consumer census
``docs/findings/lrwypin-runway-end-pins.md``).

ONE derivation, at load, on the Airport every reader takes:

* WHERE (#1358): a joined CIFP record's coordinate IS its landing
  threshold, so the pin sits at that point projected onto the runway axis
  (:func:`cifp_station`, stored as ``RunwayEnd.pin_along_m``) — never at
  the apt.dat end advanced by apt.dat's displaced length.  KDIJ 04: the
  CIFP threshold lies 593.5 m in from the apt.dat end, and its height was
  pinned at the end, 5.28 m over the lidar.
* WHETHER (#1342, 25a): per runway, before the value becomes a pin
  (:func:`verify`):
  (a) PLACEHOLDER — two CIFP ends, the same number, equal to the field
      elevation, while the DEM's end-to-end difference is beyond its
      tier's noise (CBR2: 717.5 / 717.5 m against a 17.3 m lidar fall);
  (b) GRADE — the CIFP end-to-end difference disagrees with the DEM's by
      more than the tier's tolerance (VNLK: 0 against about 31 m);
  (c) CROSS-CHECK — a cached open-data source disagrees with a CIFP end
      by more than a few feet (``airport/runway_refs``);
  (d) ZERO PLACEHOLDER (owner RULINGS 2026-10-26j) — both CIFP ends read
      0 ft (92 runways in the census, 08VA: DEM 311.7 / 296.7 m).
  A flagged runway's CIFP is not truth: each source of 26a's order whose
  end-to-end difference agrees with the DEM's supplies the ends — and a
  runway flagged by (c) ALONE keeps its CIFP unless the source fits the
  DEM BETTER than the CIFP does (owner RULINGS 2026-10-26m) (pinned
  at the source's END, which is what it states); none agreeing, the ends
  follow the DEM — ``pin_source = "dem"`` and ``threshold_elev_m = None``,
  valued by ``constraints/runway_profile.datum_pins`` (the 22a DEM rule's
  one site, which needs the planar ridge trend).
* Ends with no CIFP record are untouched here: the 30z (2) apt.dat datum,
  22a's DEM end and 26e / 28m's yield to the survey ground (by the same
  DEM class rule) are ``datum_pins``' cases.

Every flag says one loud line with all the values and publishes a record
(``LoadReport.end_pins``; the sidecar's ``runway_end_pins``).  The DEM read
is the median of production-DEM samples on the centreline within half of
``runway_ends.dem_window_m`` of the station; the DEM class is the
airport's (``law/inset_class.dem_source_class``).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..law import Law
from ..law.inset_class import dem_source_class
from ..law.tables import runway_ends
from ..model.airport import Airport, Runway
from .cifp import match_designator
from .dem import dem_z_many
from .runway_ref_record import RefEnd

__all__ = ["cifp_station", "shifted_ends", "verify", "FT"]

FT = 0.3048
_STEP_M = 5.0
#: ``RunwayEnd.pin_source`` of an end pinned on a shifted runway's CIFP line
SHIFTED = "cifp_line"
#: ``verify``'s resolution when a (c)-only runway's CIFP stands (RULINGS 2026-10-26m)
CIFP = "cifp"


def cifp_station(end_xy: tuple[float, float], other_xy: tuple[float, float],
                 p: tuple[float, float]) -> float:
    """Metres along the runway from ``end_xy`` (toward ``other_xy``) of
    the CIFP point ``p`` projected onto the axis, clamped to the runway
    (the join, RULINGS 2026-10-22a, already refused a point off it)."""
    L = math.hypot(other_xy[0] - end_xy[0], other_xy[1] - end_xy[1])
    if L <= 0.0:
        return 0.0
    s = ((p[0] - end_xy[0]) * (other_xy[0] - end_xy[0])
         + (p[1] - end_xy[1]) * (other_xy[1] - end_xy[1])) / L
    return max(0.0, min(L, s))


def shifted_ends(icao: str, runways: _t.Sequence[_t.Any], cifp: dict, recs: dict,
                 to_xy: _t.Callable[[float, float], tuple[float, float]], tol_m: float
                 ) -> tuple[dict[tuple[int, int], tuple[float, _t.Any]], list[str]]:
    """THE SHIFTED RUNWAY (issue #1358 (2)): ``{(runway index, end index):
    (value, record)}`` for an apt.dat end whose CIFP record the join refused
    because it lies BEYOND that end on the runway's own axis, while the
    other end's joined CIFP threshold sits the SAME distance inside its end
    — the CIFP runway is the apt.dat runway moved along its axis (KDIJ 4/22:
    both thresholds 594 m north-east of the apt.dat ends).  Both records are
    surveyed points of ONE line, so the refused end is pinned on the
    straight line through the two CIFP thresholds, at its own apt.dat
    landing threshold; the verification (:func:`verify`) then judges that
    line against the DEM like any CIFP pair.  One loud line each."""
    out: dict[tuple[int, int], tuple[float, _t.Any]] = {}
    lines: list[str] = []
    claimed = {r.designator for r in recs.values() if r is not None}
    for i, rw in enumerate(runways):
        for k in (0, 1):
            ra, rb = recs.get((i, 1 - k)), recs.get((i, k))
            if rb is not None or ra is None:
                continue
            far = match_designator(rw.ends[k][0], cifp)
            if far is None or far.designator in claimed:
                continue
            a_desig, a_lat, a_lon, a_disp, _o = rw.ends[1 - k]
            _b, b_lat, b_lon, b_disp, _o2 = rw.ends[k]
            a_xy, b_xy = to_xy(a_lon, a_lat), to_xy(b_lon, b_lat)
            L = math.hypot(b_xy[0] - a_xy[0], b_xy[1] - a_xy[1])
            if L <= 0.0:
                continue
            ux, uy = (b_xy[0] - a_xy[0]) / L, (b_xy[1] - a_xy[1]) / L
            pa, pb = to_xy(ra.lon, ra.lat), to_xy(far.lon, far.lat)
            sa = (pa[0] - a_xy[0]) * ux + (pa[1] - a_xy[1]) * uy
            sb = (pb[0] - a_xy[0]) * ux + (pb[1] - a_xy[1]) * uy
            lat_b = abs((pb[0] - a_xy[0]) * uy - (pb[1] - a_xy[1]) * ux)
            shift_a, shift_b = sa - a_disp, sb - (L - b_disp)
            if (lat_b > tol_m or shift_b <= tol_m or abs(shift_a - shift_b) > tol_m
                    or sb - sa <= 0.0):
                continue
            s_end = L - b_disp
            z = ra.elevation_m + (far.elevation_m - ra.elevation_m) * (s_end - sa) / (sb - sa)
            out[(i, k)] = (z, far)
            lines.append(f"SHIFTED RUNWAY (#1358): {icao} {a_desig}/{rw.ends[k][0]}: both CIFP "
                         f"thresholds lie {shift_a:.1f} / {shift_b:.1f} m along the axis from "
                         f"the apt.dat thresholds; RWY {rw.ends[k][0]} pinned on the CIFP line "
                         f"at {z:.2f} m (CIFP {ra.elevation_m:.2f} -> {far.elevation_m:.2f} m)")
    return out, lines


def _dem_at(dem, rw: Runway, k: int, along: float, window: float) -> float | None:
    """The DEM at ``along`` metres from end ``k``: the median of centreline
    samples within ``window / 2`` of it, clamped to the runway."""
    a, b = rw.ends[k].xy, rw.ends[1 - k].xy
    L = rw.length_m
    if L <= 0.0:
        return None
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    lo, hi = max(0.0, along - window / 2.0), min(L, along + window / 2.0)
    n = max(1, int(math.ceil((hi - lo) / _STEP_M)))
    ss = np.linspace(lo, hi, n + 1)
    try:
        z = dem_z_many(dem, a[0] + ux * ss, a[1] + uy * ss)
    except Exception:                       # a sampler over nothing
        return None
    z = z[np.isfinite(z)]
    return float(np.median(z)) if z.size else None


def _unvoid(z: float | None, field_m: float, det) -> float | None:
    """A DEM read at or under the sea / void band (flat-site S2a's own
    ``sea_band_max_m``) at an airport whose field stands at or above
    ``sea_band_min_z0_m`` is VOID FILL, not ground: unread."""
    if z is not None and z <= det.sea_band_max_m and field_m >= det.sea_band_min_z0_m:
        return None
    return z


def _ref_pair(rw: Runway, refs) -> list[tuple[str, dict[int, RefEnd]]]:
    """Per source, the runway's ends it carries: ``[(source, {k: RefEnd})]``."""
    out = []
    for src, ends in refs:
        got = {k: r for k, e in enumerate(rw.ends)
               if (r := match_designator(e.name, ends)) is not None}
        if got:
            out.append((src, got))
    return out


def _agrees(got: dict[int, RefEnd], dem_end: list[float | None], tol: float) -> bool:
    """Whether a source's ends agree with the DEM AT THE ENDS: its
    end-to-end difference within ``tol`` of the DEM's (two ends), or its
    one value within ``tol`` of the DEM there (one end)."""
    if len(got) == 2:
        if dem_end[0] is None or dem_end[1] is None:
            return False
        d_src = got[1].elevation_m - got[0].elevation_m
        return abs(d_src - (dem_end[1] - dem_end[0])) <= tol
    (k, r), = got.items()
    return dem_end[k] is not None and abs(r.elevation_m - dem_end[k]) <= tol


def _misfit(vals: dict[int, float], dem: list[float | None]) -> float:
    """How far values ``vals`` (end index -> z) sit off the DEM read at the
    same stations: the end-to-end difference against the DEM's (two ends),
    else the one value against the DEM there; ``inf`` where the DEM is
    unread (owner RULINGS 2026-10-26m's "fits the DEM better")."""
    if len(vals) == 2:
        if dem[0] is None or dem[1] is None:
            return math.inf
        return abs((vals[1] - vals[0]) - (dem[1] - dem[0]))
    (k, z), = vals.items()
    return math.inf if dem[k] is None else abs(z - dem[k])


def _flags(rw: Runway, field_m: float, cifp: dict[int, float], dem_pin, refs,
           t, klass) -> tuple[list[str], dict[str, dict[str, float]]]:
    """The verification flags that fire on runway ``rw`` and the cross-check
    values each source states for its CIFP ends."""
    flags: list[str] = []
    seen: dict[str, dict[str, float]] = {}
    noise, tol = t.dem_noise_m.of(klass), t.grade_disagree_m.of(klass)
    # (d) ZERO PLACEHOLDER (owner RULINGS 2026-10-26j): every end 0 ft is
    # untrusted whatever the DEM says — no DEM is needed to refuse it
    if len(cifp) == 2 and all(abs(z) <= t.zero_placeholder_ft * FT + 1e-6
                              for z in cifp.values()):
        flags.append("d")
    if (klass is not None and len(cifp) == 2 and dem_pin[0] is not None
            and dem_pin[1] is not None):
        d_dem = dem_pin[1] - dem_pin[0]
        d_cifp = cifp[1] - cifp[0]
        same = abs(d_cifp) <= t.placeholder_spread_ft * FT + 1e-6
        at_field = all(abs(z - field_m) <= t.field_equal_ft * FT + 1e-6 for z in cifp.values())
        if same and at_field and abs(d_dem) > noise:
            flags.append("a")
        if abs(d_cifp - d_dem) > tol:
            flags.append("b")
    for src, got in _ref_pair(rw, refs):
        for k, r in got.items():
            seen.setdefault(src, {})[rw.ends[k].name] = round(r.elevation_m, 3)
            if k not in cifp:
                continue
            if rw.ends[k].pin_along() > 1.0 or r.displaced_m > 0.0:
                continue                  # a displaced value is not the end's
            if abs(cifp[k] - r.elevation_m) > t.crosscheck_tol_ft * FT and "c" not in flags:
                flags.append("c")
    return flags, seen


def verify(airport: Airport, law: Law, refs: _t.Sequence = (),
           klass: str | None = "") -> tuple[Airport, list[dict], list[str]]:
    """THE RULE (module docstring) on ``airport``: the airport with every
    CIFP end resolved, one record per runway end, and the loud lines.
    ``refs`` is ``runway_refs.lookup``'s list (``()``: DEM-only rules).

    ``klass`` is the DEM's source class; ``""`` reads it off the sampler
    (``law/inset_class.dem_source_class``).  A sampler that states NO
    class (the authored ``.hgt`` sampler of fixtures and probes) is no
    witness of known quality, so (a) and (b) do not judge on it; (c) still
    does."""
    t = runway_ends(law)
    if klass == "":
        try:
            klass, _pixel, _whence = dem_source_class(airport.dem, law)
        except Exception:                  # pragma: no cover - fixtures
            klass = None
    field_m = float(airport.elevation_m)
    det = law.tables.flat_site.detector
    tol_dem = t.grade_disagree_m.of(klass)
    win = float(t.dem_window_m)
    runways, records, lines = [], [], []
    for rw in airport.runways:
        cifp = {k: float(e.threshold_elev_m) for k, e in enumerate(rw.ends)
                if e.threshold_elev_m is not None
                and getattr(e, "pin_source", "cifp") in ("cifp", SHIFTED)}
        dem_pin = [_unvoid(_dem_at(airport.dem, rw, k, e.pin_along(), win), field_m, det)
                   for k, e in enumerate(rw.ends)]
        dem_end = [_unvoid(_dem_at(airport.dem, rw, k, 0.0, win), field_m, det) for k in range(2)]
        flags, seen = _flags(rw, field_m, cifp, dem_pin, refs, t, klass) if cifp else ([], {})
        ends = list(rw.ends)
        decided = ""
        if flags:
            # RULINGS 2026-10-26m: flagged by (c) ALONE, the CIFP is not yet
            # refuted — a source takes it off truth only where the source
            # fits the DEM BETTER than the CIFP does; otherwise CIFP stands
            c_only = set(flags) == {"c"}
            decided = CIFP if c_only else "dem"
            cifp_miss = _misfit(cifp, dem_pin)
            for src, got in _ref_pair(rw, refs):
                if not (set(cifp) <= set(got) and _agrees(got, dem_end, tol_dem)):
                    continue
                if c_only and not _misfit({k: got[k].elevation_m for k in cifp},
                                          dem_end) < cifp_miss:
                    continue
                decided = src
                for k in cifp:
                    ends[k] = _dc.replace(ends[k], threshold_elev_m=got[k].elevation_m,
                                          pin_along_m=0.0, pin_source=src)
                break
            if decided == "dem":
                for k in cifp:
                    ends[k] = _dc.replace(ends[k], threshold_elev_m=None, pin_source="dem")
            for k in cifp:
                ends[k] = _dc.replace(ends[k], cifp_elev_m=cifp[k], pin_flags=",".join(flags))
            if decided == CIFP:              # the CIFP stood: its pins are untouched
                ends = [e if k not in cifp else _dc.replace(e, cifp_elev_m=None)
                        for k, e in enumerate(ends)]
            lines.append(_line(airport.icao, rw, flags, cifp, field_m, dem_pin, klass,
                               seen, decided))
        new = _dc.replace(rw, ends=(ends[0], ends[1]))
        runways.append(new)
        for k, e in enumerate(new.ends):
            moved = e.pin_along() - float(e.displaced_m or 0.0)
            records.append({
                "runway": rw.id, "end": e.name,
                "source": e.pin_source,
                "flags": list(flags) if k in cifp else [],
                "cifp_m": None if k not in cifp else round(cifp[k], 3),
                "pin_m": (None if e.threshold_elev_m is None
                          else round(float(e.threshold_elev_m), 3)),
                "pin_along_m": round(e.pin_along(), 2),
                "pin_moved_m": round(moved, 2),
                "field_m": round(field_m, 3),
                "dem_m": None if dem_pin[k] is None else round(dem_pin[k], 3),
                "dem_class": klass, "crosscheck": {s: v.get(e.name) for s, v in seen.items()},
            })
            if k in cifp and abs(moved) > float(law.tables.emit.identity.cifp_threshold_join_m):
                lines.append(f"CIFP threshold pinned at its own point (#1358): {airport.icao} "
                             f"RWY {e.name} lies {e.pin_along():.1f} m along the runway; the "
                             f"apt.dat threshold is at {float(e.displaced_m or 0.0):.1f} m")
    return _dc.replace(airport, runways=tuple(runways)), records, lines


def _line(icao: str, rw: Runway, flags, cifp, field_m, dem_pin, klass, seen, decided) -> str:
    """The ONE loud line of a flagged runway: every value the rule read."""
    def m(v):
        return "-" if v is None else f"{v:.2f}"
    names = [e.name for e in rw.ends]
    cif = "/".join(m(cifp.get(k)) for k in range(2))
    dem = "/".join(m(v) for v in dem_pin)
    xs = "; ".join(f"{s} " + "/".join(m(v.get(n)) for n in names) for s, v in seen.items())
    then = ("the ends follow the DEM" if decided == "dem"
            else "CIFP stands: no source fits the DEM better (RULINGS 2026-10-26m)"
            if decided == CIFP else f"the ends take {decided}'s values")
    return (f"CIFP THRESHOLDS FLAGGED (#1342, RULINGS 2026-10-25a) {icao} {rw.id} rule "
            f"({','.join(flags)}): CIFP {names[0]}/{names[1]} {cif} m, field {field_m:.2f} m, "
            f"DEM ({klass or 'unknown'}) {dem} m"
            + (f", cross-check {xs}" if xs else ", no cross-check cached")
            + f" -> {then}")


