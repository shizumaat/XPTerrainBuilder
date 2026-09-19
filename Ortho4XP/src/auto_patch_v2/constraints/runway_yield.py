"""§50 THE RUNWAY CAP YIELDS TO ITS PINS, UNIFORMLY (owner RULINGS
2026-09-18d (3), answered 2026-09-18f; spec ``auto-patch-v2/
design-surface-spec.md`` §50; founded on lane ``tffjverify``,
``docs/findings/tffj-verify-20260918.md``).

THRESHOLDS ARE TRUTH.  TFFJ 10/28 carries two CIFP thresholds 13.411 m
apart over 635 m of ridge — 2.112 % — against an
``icao.runway.longitudinal`` that was 1.5 % for every code.  The runway
family was therefore INFEASIBLE BY CONSTRUCTION ("48 rows are an
INFEASIBLE SET, min total shortfall 3.8812 m"), §16's projection enforced
the cap EXACTLY on every free column, and the 2.8 m that did not fit
landed as a 2.6 m STEP at the pins: ``runway_vertical_curve`` 3 +
``runway_transverse`` 5, and the app aborted the tile.

The owner's ruling, verbatim: "the cap yields, uniformly" — the runway
takes the SMALLEST UNIFORM OVER-GRADE THAT FITS pin to pin, and ships
with one loud report line (§50.4), never a new gating family.

THE DERIVATION IS ONE PASS, AT ONE SITE (§50.1 (3)).  Over a runway's ONE
ridge station sequence (:func:`runway_profile.curve_stations`) take every
station carrying a HARD PIN — a CIFP threshold
(:func:`runway_profile.threshold_pins`), a §17 crossing anchor
(``runway_chord._crossing_pin_map``) or a §38 tile-seam DEM pin
(``pm.seam_vertices``), in that seniority on a shared vertex.  For each
CONSECUTIVE pinned pair the span is the sum of the RIDGE CHORDS between
them (the Diff rows' own ``d``, never the axis station difference and
never the apt.dat threshold distance) and ``g = |Δz| / span``;
``g_pin`` is the largest over the runway's pairs.  Then

    cap = max(cap_law, g_pin + [design] runway_yield_margin)

— UNIFORM PER RUNWAY, not per segment (§50.1 (5)): a per-span cap is
infeasible by construction against the vertical-curve law, which admits
only ``spacing / K`` of grade change per station, so a span yielded to
exactly its own grade could not turn into the next one.  The chord target
still pulls every span to its own piecewise profile, so a lawful span
spends no allowance it does not need; the report names the GOVERNING span
and its two pins.

The record is carried on ``PlanarMap.runway_caps`` and read back by
``precedence.cap_of`` / ``precedence.face_cap`` (the SOLVE side) and by
the sidecar law key ``runway_caps`` (the PUBLISHED side) — one derivation,
two readers, the §34 (9) ``lifted_caps`` shape.

IMPORT DIRECTION (§50.6): this module reads ``runway_profile`` at module
level and ``runway_chord`` inside :func:`derive` only, because
``runway_chord`` calls it; ``cap_of`` lives in ``precedence`` (it reads
``pm.runway_caps`` and the table, nothing of this module), so no
constraint generator importing the cap can form a cycle.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..law.tables import role_cap
from ..model.airport import Airport
from ..model.planar import PlanarMap
from .precedence import view
from .runway_profile import curve_stations, ridge_chains, threshold_pins

__all__ = ["RunwayCap", "Pin", "derive", "report_line", "yielded_lines",
           "KIND_THRESHOLD", "KIND_CROSSING", "KIND_SEAM"]

#: The pin KINDS, in SENIORITY order on a shared ridge vertex (§50.1 (3)).
#: The line names the kind, so a seam-forced yield is visible at a glance.
KIND_THRESHOLD = "threshold"
KIND_CROSSING = "crossing"
KIND_SEAM = "seam"

_SENIORITY = {KIND_THRESHOLD: 0, KIND_CROSSING: 1, KIND_SEAM: 2}

#: How each kind reads in the §50.4 line and in the published record.
PIN_LABEL = {KIND_THRESHOLD: "CIFP", KIND_CROSSING: "crossing anchor",
             KIND_SEAM: "tile seam DEM"}


@_dc.dataclass(frozen=True)
class Pin:
    """One HARD PIN on a runway's ridge: what holds it, and where."""

    kind: str                 # threshold | crossing | seam
    name: str                 # the end's name, the crossing's pair, "seam"
    z: float
    vertex: int

    @property
    def label(self) -> str:
        """How the §50.4 line names this pin's kind."""
        base = PIN_LABEL.get(self.kind, self.kind)
        return (f"{base} of {self.name}" if self.kind == KIND_CROSSING
                else base)


@_dc.dataclass(frozen=True)
class RunwayCap:
    """One runway's EFFECTIVE longitudinal cap (§50.1 (3)).

    ``cap_law`` is the table's value for this runway's code, ``g_pin`` the
    steepest grade its own consecutive hard pins demand, ``cap`` the
    effective cap the build priced every runway row at, and ``yielded``
    whether the cap had to rise above the table.  ``span_m`` / ``dz_m``
    and ``pin_a`` / ``pin_b`` name the GOVERNING span — the pair that set
    ``g_pin`` — so the line, the report and the sidecar all name one
    thing."""

    ref: str
    code_number: int | None
    code_letter: str | None
    cap_law: float
    g_pin: float
    cap: float
    yielded: bool
    span_m: float
    dz_m: float
    pin_a: Pin | None = None
    pin_b: Pin | None = None

    def as_dict(self, ruleset: str = "",
                ll: _t.Mapping[int, tuple[float, float]] | None = None
                ) -> dict[str, _t.Any]:
        """The PUBLISHED record (§50.1 (4)) — one shape for the sidecar,
        ``report.json`` and the GradedSurface provenance."""
        def pin(p: Pin | None) -> dict[str, _t.Any] | None:
            if p is None:
                return None
            rec: dict[str, _t.Any] = {"kind": p.kind, "name": p.name,
                                      "z": round(p.z, 4)}
            if ll is not None and p.vertex in ll:
                lat, lon = ll[p.vertex]
                rec["ll"] = [round(float(lat), 11), round(float(lon), 11)]
            return rec

        return {"ref": self.ref, "code_number": self.code_number,
                "code_letter": self.code_letter, "ruleset": ruleset,
                "cap_law": self.cap_law, "cap": self.cap,
                "yielded": self.yielded, "pin_grade": round(self.g_pin, 8),
                "span_m": round(self.span_m, 3), "dz_m": round(self.dz_m, 4),
                "pins": [p for p in (pin(self.pin_a), pin(self.pin_b))
                         if p is not None]}


def _pin_sources(pm: PlanarMap, law: Law, airport: Airport, vw, chains
                 ) -> dict[int, Pin]:
    """Every ridge vertex carrying a HARD PIN, by the §50.1 (3) seniority
    (threshold > crossing anchor > seam DEM).  ``runway_chord`` is read
    HERE, inside the call, because it calls this module (module
    docstring)."""
    from .runway_chord import (_chords, _crossing_pin_map, _with_knots,
                               _with_seam_knots, runway_crossings)
    out: dict[int, Pin] = {}

    def put(v: int, p: Pin) -> None:
        old = out.get(v)
        if old is None or _SENIORITY[p.kind] < _SENIORITY[old.kind]:
            out[v] = p

    thresholds = threshold_pins(pm, law, airport)
    # WHICH END a threshold pin belongs to, for the §50.4 line: the pinned
    # ridge vertex nearest that end's own point (``threshold_pins``' own
    # choice, read back by geometry rather than re-derived).
    name_of: dict[int, str] = {}
    for rw in airport.runways:
        own = [v for ch in chains.get(rw.id, []) for v in ch if v in thresholds]
        for end in rw.ends:
            if end.threshold_elev_m is None or not own:
                continue
            v = min(own, key=lambda q: (vw.xy[q][0] - end.xy[0]) ** 2
                    + (vw.xy[q][1] - end.xy[1]) ** 2)
            name_of.setdefault(v, f"RWY {end.name}")
    for v, z in thresholds.items():
        put(v, Pin(KIND_THRESHOLD, name_of.get(v, "threshold"), float(z), v))

    straight, _n = _chords(pm, law, airport)
    crossings = runway_crossings(pm, law, airport, straight)
    if crossings:
        fitted = _with_seam_knots(_with_knots(straight, crossings), pm, law)
        for v, (z, x) in _crossing_pin_map(pm, law, airport, vw, chains,
                                           fitted, crossings).items():
            put(v, Pin(KIND_CROSSING, x.pair, float(z), v))

    if pm.seam_vertices:
        for chs in chains.values():
            for ch in chs:
                for v in ch:
                    if v not in pm.seam_vertices or v in out:
                        continue       # a senior pin holds it (seam_exempt)
                    dz = pm.vertices[v].dem_z
                    if dz is not None:
                        put(v, Pin(KIND_SEAM, "seam", float(dz), v))
    return out


def derive(pm: PlanarMap, law: Law, airport: Airport) -> dict[str, RunwayCap]:
    """Runway ref -> its EFFECTIVE longitudinal cap (module docstring).

    ONE record per runway with a ridge and a governed cap — yielded or
    not — so the published side carries the cap the build priced for
    EVERY runway (§50.1 (4), which is what closes 2026-09-04y).  A runway
    with fewer than two hard pins has ``g_pin = 0`` and never yields."""
    vw = view(pm, law)
    chains = ridge_chains(vw)
    if not chains:
        return {}
    margin = float(law.tables.emit.design.runway_yield_margin)
    min_d = float(law.tables.emit.identity.min_distinct_spacing_m)
    pins = _pin_sources(pm, law, airport, vw, chains)
    out: dict[str, RunwayCap] = {}
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        rc = role_cap(law, "runway", rw.code_number, rw.code_letter)
        if rc is None:
            continue
        a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
        L = rw.length_m
        ux = (b_xy[0] - a_xy[0]) / L if L > 0 else 0.0
        uy = (b_xy[1] - a_xy[1]) / L if L > 0 else 0.0

        def along(v: int, _ax=a_xy, _ux=ux, _uy=uy) -> float:
            x, y = vw.xy[v]
            return (x - _ax[0]) * _ux + (y - _ax[1]) * _uy

        st = curve_stations(vw.xy, chs, along, min_d)
        # THE PIN SITS AT A STATION.  ``curve_stations`` drops a vertex
        # closer than the IDENTITY FLOOR to the last kept one — by that
        # floor the two ARE one station — so a pinned vertex the sequence
        # dropped is read at the station it was merged into, never lost.
        index = {v: i for i, v in enumerate(st)}
        ridge = {v for ch in chs for v in ch}
        own = {v: p for v, p in pins.items() if v in ridge or v in index}
        at: dict[int, Pin] = {}
        for v, p in own.items():
            i = index.get(v)
            if i is None:
                if not st:
                    continue
                i = min(range(len(st)),
                        key=lambda k: (vw.xy[st[k]][0] - vw.xy[v][0]) ** 2
                        + (vw.xy[st[k]][1] - vw.xy[v][1]) ** 2)
            old = at.get(i)
            if old is None or _SENIORITY[p.kind] < _SENIORITY[old.kind]:
                at[i] = p
        order = sorted(at)
        g_pin = 0.0
        best: tuple[float, float, Pin, Pin] | None = None
        for i, j in zip(order, order[1:]):
            span = sum(vw.dist(st[k], st[k + 1]) for k in range(i, j))
            if span <= 0.0:
                continue
            dz = at[j].z - at[i].z
            g = abs(dz) / span
            if g > g_pin:
                g_pin = g
                best = (span, dz, at[i], at[j])
        cap = max(rc.longitudinal, g_pin + margin) if g_pin > 0.0 \
            else rc.longitudinal
        out[rw.id] = RunwayCap(
            ref=rw.id, code_number=rw.code_number, code_letter=rw.code_letter,
            cap_law=rc.longitudinal, g_pin=g_pin, cap=cap,
            yielded=cap > rc.longitudinal,
            span_m=best[0] if best else 0.0, dz_m=best[1] if best else 0.0,
            pin_a=best[2] if best else None, pin_b=best[3] if best else None)
    return out


def report_line(icao: str, rc: RunwayCap, authority: str = "") -> str:
    """§50.4 THE ONE LOUD LINE, for a runway whose cap YIELDED.

    One line per over-grade runway naming the pin-to-pin grade, the two
    pins that demand it (by KIND, so a seam-forced yield is visible at a
    glance) and the cap it exceeded.  It is a LINE, never a gate:
    ``defect_gate`` and ``LAW_FAMILIES`` are untouched (owner RULINGS
    2026-09-18d (3) / 18f (4))."""
    a, b = rc.pin_a, rc.pin_b
    kinds = {p.kind for p in (a, b) if p is not None}
    who = "thresholds" if kinds == {KIND_THRESHOLD} else "pins"
    where = ""
    if a is not None and b is not None:
        labels = a.label if a.label == b.label else f"{a.label} / {b.label}"
        where = (f" ({rc.dz_m:+.3f} m over {rc.span_m:.1f} m, {a.name} "
                 f"{a.z:.3f} m -> {b.name} {b.z:.3f} m, {labels})")
    if authority.upper() == "FAA":
        cls = f"FAA class {rc.code_letter}" if rc.code_letter else "FAA"
    else:
        cls = (f"{authority or 'ICAO'} code {rc.code_number}"
               if rc.code_number is not None else (authority or "ICAO"))
    return (f"[{icao}] RUNWAY OVER GRADE {rc.ref}: the {who} demand "
            f"{100 * rc.g_pin:.3f} % pin to pin{where}; the law's cap is "
            f"{100 * rc.cap_law:.3f} % ({cls}); the cap yields — built to "
            f"{100 * rc.cap:.3f} % uniformly (RULINGS 2026-09-18d)")


def yielded_lines(icao: str, caps: _t.Mapping[str, RunwayCap],
                  authority: str = "") -> list[str]:
    """:func:`report_line` for every YIELDED runway of ``caps``, in ref
    order — what ``pipeline/build.py``, ``--why-hard`` and the replay all
    print, from the one record."""
    return [report_line(icao, rc, authority)
            for _r, rc in sorted(caps.items()) if rc.yielded]
