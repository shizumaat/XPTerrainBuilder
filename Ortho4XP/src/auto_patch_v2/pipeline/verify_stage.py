"""THE VERIFY STAGE (stage-cache spec §4b.7, §10 step 8): the in-build
census of the emitted surface — ``verify.census_frame`` over ``surf`` and
``pub`` with the road law caps and the lifted ramp caps — its summary,
DEFECT and under-floor lines, and the ``apron_over_preference`` report.  A
READ: it changes nothing that ships."""
from __future__ import annotations

import time
import typing as _t

from ..law import Law
from ..model import pulse as _pulse

__all__ = ["verify"]


def verify(icao: str, *, surf, pub, pm, law: Law, airport, report: dict, wall: dict,
           pool_out: list, out: _t.Callable[[str], None]) -> dict:
    """Census the emitted surface: ``report["verify"]`` and ``wall["verify"]``
    are written, the verify work pool's account appended to ``pool_out``;
    returns the rows by family."""
    _vpool = pool_out
    t = time.perf_counter()
    _pulse.tick("verifying the patch")
    from ..constraints.roads import road_law_caps
    from ..verify import census_frame
    # ONE FRAME FOR THE WHOLE VERIFY STAGE (lane ``v2cost2``,
    # RULINGS 2026-09-14q item 7): the caps and the ``Patch`` were
    # built TWICE — once here and once for
    # ``apron_over_preference`` below, the second time AFTER this
    # clock stopped, which is where OTHH's 105 unattributed
    # seconds were.  Same rows, one frame, inside the clock.
    _caps = road_law_caps(pm, law, airport)
    # §34 (9) (RULINGS 2026-09-14ak/14am): the PINCHED RAMP faces
    # whose within-shape longitudinal cap is LIFTED — the same map
    # ``face_tags`` stamps on the ways for the v1 census.
    from .publication import lifted_caps as _lifted_caps
    # the apron chords' work pool says its line through this log
    # and hands its account to the report (``report["pool"]``)
    _vpatch, vrows = census_frame(surf, law, pub, _caps,
                                  _lifted_caps(pm),
                                  say=lambda m: out("  " + m),
                                  on_pool=_vpool.append)
    # RULINGS 2026-09-08t: every row is counted LAW-TRUE — there is
    # no relaxed / yielded scope any more.  A row here is a DESIGN
    # TARGET the surface missed; the census reports, never blocks.
    _v_census_s = time.perf_counter() - t
    summary = {k: len(v) for k, v in vrows.items()}
    out(f"[{icao}] verify {_v_census_s:.2f} s  rows "
         f"{sum(summary.values())}  " + ", ".join(
             f"{k} {n}" for k, n in summary.items() if n))
    # THE STRUCTURAL-DEFECT GATE, ONE READING (owner RULINGS
    # 2026-09-14bx): a DEFECT row aborts the tile only when
    # MATERIAL — ``emit.verify.defect_min_excess_m`` of excess
    # beyond its own cap over its own span.  A row under the floor
    # stays a census VIOLATION (it is untouched in ``vrows`` and so
    # counted in ``by_family`` above, in ``rows`` below and in the
    # cockpit) and is NAMED here instead of killing the tile.
    from ..verify.census import defect_gate, under_floor_text
    defects, under_floor = defect_gate(law, vrows)
    for k, n in defects.items():
        out(f"[{icao}] verify: DEFECT {k} {n} — " + "; ".join(
            f"{r.get('way_a')} {r.get('reading')} {r.get('magnitude_m')} m"
            for r in vrows[k][:10]) + (" ..." if n > 10 else ""))
    if under_floor:
        out(f"[{icao}] verify: {under_floor_text(under_floor)} — "
             "a census violation, not an abort (RULINGS 2026-09-14bx)")
    from ..verify.within import apron_over_preference as _v_pref
    v_pref = _v_pref(_vpatch)
    from ..verify.census import WALL_S as _VWALL
    # the stage clock covers the preference report too (item 7)
    wall["verify"] = time.perf_counter() - t
    out(f"[{icao}] verify: apron_over_preference {v_pref['over_preference']}/{v_pref['rows']} "
         f"(max grade {v_pref['max_grade']:.4f}) — a report figure, the "
         f"design surface has no preference ladder")
    report["verify"] = {"by_family": summary,
                        "apron_over_preference": v_pref,
                        "defects": defects,
                        # the DEFECT rows the materiality floor
                        # spared (14bx) — still rows, still counted
                        "defects_under_floor": under_floor,
                        # THE PER-FAMILY VERIFY CLOCK (14q): which
                        # reader the stage's seconds went to
                        "wall_s": dict({"census": round(_v_census_s, 3),
                                        "stage": round(wall["verify"], 3)},
                                       **{k: round(v, 3)
                                          for k, v in sorted(_VWALL.items(),
                                                             key=lambda kv: -kv[1])}),
                        "rows": {k: v for k, v in vrows.items() if v}}
    return vrows
