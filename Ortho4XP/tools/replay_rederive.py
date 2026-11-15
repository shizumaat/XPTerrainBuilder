"""THE ROUTE / TREND RE-DERIVATION, offline (issue #1899): the two
derivations a grade-rule variant usually touches —
``constraints/taxi_trend.low_hold_retarget`` (the ceiling between two low
holds, #517) and ``constraints/taxi_route_yield.derive`` (the yielded
routes) — re-run ALONE against a ``v2_solve_replay --solved-out`` pickle,
so a variant is screened in seconds before paying for a full solve.

The pickle carries the stage-1 levels pass 1b held and the trend targets
they were held against (``stage1_levels`` / ``stage1_taxi_trend_z``, kept
by the replay's ``hold_rewrite``); a pickle written before #1899 has
neither and is refused by name.  ``--design-weight`` overrides apply to
the law both derivations read.  Nothing is solved and nothing is emitted:
the result is a summary (and, with ``--json``, the moved targets and the
routes) — a screen, never a pass.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import pickle
from pathlib import Path

__all__ = ["rederive", "summarise"]


def _law(icao: str, design: dict):
    from auto_patch_v2.law import Law
    law = Law.for_airport(icao)
    if not design:
        return law
    d0 = law.tables.emit.design
    return _dc.replace(law, tables=_dc.replace(law.tables, emit=_dc.replace(
        law.tables.emit, design=_dc.replace(d0, **design))))


def summarise(pm, law, airport, levels: dict, trend_z: dict) -> dict:
    """Both derivations on ``pm`` with its trend targets set to the ones
    stage 1 was held against; the counts a variant is screened by."""
    from auto_patch_v2.constraints.taxi_route_yield import derive
    from auto_patch_v2.constraints.taxi_trend import low_hold_retarget
    pm_x = _dc.replace(pm, taxi_trend_z=dict(trend_z))
    rep: dict = {}
    tz = low_hold_retarget(pm_x, law, levels, rep)
    routes = derive(pm, law, airport)
    moved = {} if tz is None else {
        int(v): round(float(z) - float(trend_z[v]), 3)
        for v, z in tz.items() if v in trend_z and abs(z - trend_z[v]) > 1e-9}
    return {
        "low_hold": {k: rep.get(k) for k in ("low_hold_spans", "low_hold_beyond",
                                             "low_hold_moved", "low_hold_worst_m")},
        "low_hold_targets_moved": len(moved),
        "moved": moved,
        "routes": [{"high_ll": r.high_ll, "low_ll": r.low_ll,
                    "length_m": round(r.length_m, 1), "needed": round(r.needed, 4),
                    "cap": round(r.cap, 4), "over_ceiling": bool(r.over_ceiling),
                    "edges": len(r.edges)} for r in routes],
    }


def rederive(pkl: Path, design: dict, json_out: Path | None,
             install=None) -> int:
    """The ``--rederive-from`` mode: load, install the pickle's registries
    through ``install`` (the replay's ``install_capture_state``), summarise."""
    with Path(pkl).open("rb") as fh:
        sv = pickle.load(fh)
    if sv.get("stage1_levels") is None:
        raise SystemExit(f"REFUSED: {pkl} carries no stage-1 levels (written "
                         "before #1899, or by a run whose solve was not staged); "
                         "re-run the arm with --replay ... --solved-out PKL")
    icao, pm = sv["icao"], sv["pm"]
    if install is not None:
        install(sv, icao, "rederive", str(pkl),
                "Re-run the arm that wrote it (--replay ... --solved-out PKL).",
                reg=pm.registries)
    law = _law(icao, design)
    res = summarise(pm, law, sv.get("airport"), sv["stage1_levels"],
                    sv["stage1_taxi_trend_z"] or {})
    for k, v in design.items():
        print(f"REDERIVE ARM --design-weight {k}={v}")
    lh = res["low_hold"]
    print(f"[{icao}] low_hold_retarget: spans {lh['low_hold_spans']}, "
          f"targets moved {res['low_hold_targets_moved']}, "
          f"worst {lh['low_hold_worst_m']} m")
    over = sum(r["over_ceiling"] for r in res["routes"])
    print(f"[{icao}] taxi_route_yield: {len(res['routes'])} route(s), "
          f"{over} over the exception ceiling")
    if json_out is not None:
        Path(json_out).write_text(json.dumps(res, indent=1, default=str))
    return 0
