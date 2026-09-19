"""The RUNWAY PROFILE report block (spec §21.2 (4); RULINGS 2026-09-10x):
per runway, the built ridge against its long-wave trend target and the
binding family law.  Lives in ``pipeline`` because it reads the
constraints (the ridge chains, the chords, the crossings) as well as the
solve — the M0 §1 dependency direction keeps ``solve`` below ``constraints``
(``tests/auto_patch_v2/test_model.py::test_dependency_direction``); the
function itself is unchanged from lane ``v2rwycurve``'s.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..law import Law
from ..model.planar import PlanarMap
from ..solve.rows import _law_sides, _violation

__all__ = ["runway_profile_block"]


def runway_profile_block(planar: PlanarMap, law: Law, airport,
                         cs, z: _t.Sequence[float]) -> dict[str, _t.Any]:
    """THE REPORT NAMES THE RESIDUAL PER RUNWAY (spec §21.2 (4)).

    "The final projection (§16) still settles the family exactly; a target
    the laws refuse is simply not reached, and the report names the
    residual per runway."  Per runway with a target profile:

    * ``kind`` — ``trend`` or the ``chord`` fallback, and the window;
    * ``target_rms_m`` / ``target_max_m`` — the BUILT ridge against the
      target it was given, the §21.4 twin's own bar;
    * ``dem_mean_abs_m`` — mean |z − DEM| along the ridge, the SPJC bar
      (2.14 m on the straight chord);
    * ``chord_bow_m`` — the built ridge's worst fall under the STRAIGHT
      threshold chord, kept for continuity with every earlier round's bow;
    * ``binding`` / ``binding_slack_m`` — the law row with the least slack
      among the rows whose feet ALL lie on this runway's ridge: what the
      surface is held by where it does not reach its target.

    Reads only what the pipeline already has (the constraint set and the
    solved z); mints nothing.
    """
    from ..constraints.runway_chord import _chords, _with_knots, runway_crossings
    from ..constraints.runway_profile import ridge_chains
    from ..constraints.precedence import view
    vw = view(planar, law)
    chains = ridge_chains(vw)
    straight, n_without = _chords(planar, law, airport)
    chords = _with_knots(straight, runway_crossings(planar, law, airport, straight))
    # the least-slack law row per runway ridge (the binding law)
    one, eq = _law_sides(cs)
    zz = np.asarray(z, dtype=float)
    ridge_of: dict[int, str] = {}
    for r, chs in chains.items():
        for ch in chs:
            for v in ch:
                ridge_of[v] = r
    worst: dict[str, tuple[float, str]] = {}
    for side in one:
        terms, _hi, row = side
        rs = {ridge_of.get(v) for v, _c in terms}
        if len(rs) != 1 or None in rs:
            continue
        r = rs.pop()
        slack = -_violation(side, zz)
        if r not in worst or slack < worst[r][0]:
            worst[r] = (slack, row.source.ruling)
    out: list[dict[str, _t.Any]] = []
    for r, c in sorted(chords.items()):
        ridge = sorted({v for ch in chains.get(r, []) for v in ch},
                       key=lambda q: c.station(*vw.xy[q]))
        if not ridge:
            continue
        d2 = t_max = 0.0
        dem_abs: list[float] = []
        bow = 0.0
        for v in ridge:
            s = c.station(*vw.xy[v])
            d = float(zz[v]) - c.z(s)
            d2 += d * d
            t_max = max(t_max, abs(d))
            bow = min(bow, float(zz[v]) - c.straight_z(s))
            dem = planar.vertices[v].dem_z
            if dem is not None:
                dem_abs.append(abs(float(zz[v]) - float(dem)))
        wr = worst.get(r)
        # §50.2 Y23 (spec §50.4): the CAP THIS RUNWAY WAS BUILT UNDER and
        # the grade it actually reached.  ``built_max_grade`` is read off
        # the solved ``z`` along the ridge BETWEEN THE GOVERNING PINS —
        # the span the yield was derived for — so the report's own number
        # can be held against ``cap`` (the §50.1 (5) uniformity read).
        rc = (planar.runway_caps or {}).get(r)
        span_v = {rc.pin_a.vertex, rc.pin_b.vertex} if (
            rc is not None and rc.pin_a is not None
            and rc.pin_b is not None) else set()
        s_lo, s_hi = (min(c.station(*vw.xy[v]) for v in span_v),
                      max(c.station(*vw.xy[v]) for v in span_v)) \
            if span_v else (-float("inf"), float("inf"))
        built = 0.0
        for va, vb in zip(ridge, ridge[1:]):
            sa, sb = c.station(*vw.xy[va]), c.station(*vw.xy[vb])
            if sa < s_lo - 1e-9 or sb > s_hi + 1e-9:
                continue
            dd = vw.dist(va, vb)
            # THE IDENTITY FLOOR, as every other ridge reader applies it
            # (``curve_stations``' own ``min_distinct_spacing_m``): two
            # stations closer than it ARE one station, and a rate stated
            # over a noding sliver is an instrument artefact, not a grade.
            if dd >= float(law.tables.emit.identity.min_distinct_spacing_m):
                built = max(built, abs(float(zz[vb]) - float(zz[va])) / dd)
        cap_yield = None if rc is None else {
            "cap_law": rc.cap_law, "cap": rc.cap, "yielded": rc.yielded,
            "pin_grade": round(rc.g_pin, 8), "span_m": round(rc.span_m, 3),
            "dz_m": round(rc.dz_m, 4),
            "pins": [p.label for p in (rc.pin_a, rc.pin_b) if p is not None]}
        out.append({
            "runway": r, "kind": c.kind,
            "cap_yield": cap_yield,
            "built_max_grade": round(built, 8),
            "window_m": round(float(law.tables.emit.design.runway_profile_window_m), 1),
            "stations": len(ridge),
            "target_rms_m": round((d2 / len(ridge)) ** 0.5, 4),
            "target_max_m": round(t_max, 4),
            "dem_mean_abs_m": round(sum(dem_abs) / len(dem_abs), 4) if dem_abs else None,
            "chord_bow_m": round(bow, 3),
            "binding": wr[1] if wr else "",
            "binding_slack_m": round(wr[0], 4) if wr else None,
        })
    return {"runways": out, "runways_without_pins": n_without,
            "window_m": round(float(law.tables.emit.design.runway_profile_window_m), 1)}
