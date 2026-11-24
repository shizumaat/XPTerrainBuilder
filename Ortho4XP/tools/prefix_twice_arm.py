"""THE BUILD'S PREFIX TWICE IN ONE PROCESS (#2206 steps 0-1): the base
derive, then the late one, as ``pipeline/build`` orders them.

``tools/v2_solve_replay.py --replay PKL --from classify --prefix-twice
on|off`` runs ``pipeline/prefix.Deriver`` (no stage cache) on the base
classification (``stage_one_map.gap_free``: the gap pieces, pad roads and
car lots withheld) and then on the whole one, the second with the airport
the first returned (its flat-site verdict), exactly as the build hands the
late stage its ``derive``.  ``on`` runs both under
``planar/arrangement_memo.scoped`` (a build), ``off`` outside it.  Printed:
each run's step clocks (``prefix_clocks``), the memo's outcomes and the late
map's digest — equal for ``on`` and ``off`` when serving the front changes
nothing.  It solves nothing.  The late classification is the uncut one: the
front reads only the non-late cells, which the cut never changes.

Promoted from the lonemap lane's scratch ``warmprof.py`` (its second use)."""
from __future__ import annotations

import time
import typing as _t

__all__ = ["prefix_twice"]


def _digest(obj: _t.Any) -> str:
    from auto_patch_v2.airport.stage_cache import value_digest
    try:
        return value_digest(obj)[:16]
    except Exception as exc:                  # a product that will not pickle
        return f"undigested ({type(exc).__name__})"


def prefix_twice(icao: str, airport, cl, law, inputs, pack, *, memo: bool,
                 out: _t.Callable[[str], None] = print) -> dict:
    """The two derives (module docstring); returns the clocks, the memo's
    outcomes (``None`` with ``memo`` off) and the late map's digests."""
    from auto_patch_v2.pipeline.prefix import Deriver
    from auto_patch_v2.pipeline.stage_one_map import gap_free
    from auto_patch_v2.planar import arrangement_memo as _arr_memo

    def both() -> dict:
        derive = Deriver(airport, law, inputs, pack)
        walls = []
        for what, cl_x in (("base", gap_free(cl) or cl), ("late", cl)):
            t = time.perf_counter()
            derive(cl_x)
            walls.append((what, time.perf_counter() - t))
            # the build's later derives take the main pass's airport
            derive.airport = derive.last.airport
        pm, cs = derive.last.pm, derive.last.cs
        return {"walls": walls, "clocks": list(derive.clocks),
                "outcomes": _arr_memo.outcomes(),
                "late_pm": _digest(pm), "late_cs": _digest(cs)}
    got = (_arr_memo.scoped(both) if memo else both)()
    for (what, s), clock in zip(got["walls"], got["clocks"]):
        steps = ", ".join(f"{k} {v:.1f}" for k, v in clock["wall_s"].items())
        out(f"[{icao}] PREFIX TWICE ({'memo on' if memo else 'memo off'}) {what} derive "
            f"{s:.1f} s, steps sum {clock['total_s']:.1f} s: {steps}")
    out(f"[{icao}] PREFIX TWICE front memo outcomes: {got['outcomes']}")
    out(f"[{icao}] PREFIX TWICE late map digest pm {got['late_pm']} cs {got['late_cs']}")
    return got
