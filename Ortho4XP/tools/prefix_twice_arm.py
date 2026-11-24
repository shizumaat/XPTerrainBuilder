"""THE BUILD'S PREFIX TWICE IN ONE PROCESS (#2206 steps 0-1): the base
derive, then the late one, as ``pipeline/build`` orders them.

``tools/v2_solve_replay.py --replay PKL --from classify --prefix-twice
off`` runs ``pipeline/prefix.Deriver`` (no stage cache) on the base
classification (``stage_one_map.gap_free``: the gap pieces, pad roads and
car lots withheld) and then on the whole one, the second with the airport
the first returned (its flat-site verdict), exactly as the build hands the
late stage its ``derive``.  Printed: each run's step clocks
(``prefix_clocks``) and the late map's digest, whole and per field.  It
solves nothing.  (The ``on`` arm, the arrangement front memo, was deleted
in #2206 step 1: it served no late derive, and served it changed the map.)

Promoted from the lonemap lane's scratch ``warmprof.py`` (its second use)."""
from __future__ import annotations

import time
import typing as _t

__all__ = ["prefix_twice"]


def _digest(obj: _t.Any) -> str:
    """The VALUE digest (``stage_cache.content_digest``, blind to object
    sharing: a served front is a deep copy), ``~`` marking the canonical
    fallback for a product too deep for it (sharing-sensitive)."""
    from auto_patch_v2.airport.stage_cache import canonical_digest, content_digest
    try:
        return content_digest(obj)[:16]
    except (RecursionError, ValueError):
        try:
            return "~" + canonical_digest(obj)[:16]
        except Exception as exc:
            return f"undigested ({type(exc).__name__})"
    except Exception as exc:                  # a product that will not pickle
        return f"undigested ({type(exc).__name__})"


def _fields(obj: _t.Any) -> dict[str, str]:
    """One digest per dataclass field of ``obj`` (where a map differs)."""
    import dataclasses as _dc
    if not _dc.is_dataclass(obj):
        return {"value": _digest(obj)}
    return {f.name: _digest(getattr(obj, f.name)) for f in _dc.fields(obj)}


def prefix_twice(icao: str, airport, cl, law, inputs, pack, *,
                 out: _t.Callable[[str], None] = print) -> dict:
    """The two derives (module docstring); returns the clocks and the late
    map's digests."""
    from auto_patch_v2.pipeline.prefix import Deriver
    from auto_patch_v2.pipeline.stage_one_map import gap_free

    def both() -> dict:
        derive = Deriver(airport, law, inputs, pack)
        walls = []
        for what, cl_x in (("base", gap_free(cl) or cl), ("late", cl)):
            t, c = time.perf_counter(), time.process_time()
            derive(cl_x)
            walls.append((what, time.perf_counter() - t,
                          time.process_time() - c))
            # the build's later derives take the main pass's airport
            derive.airport = derive.last.airport
        pm, cs = derive.last.pm, derive.last.cs
        return {"walls": walls, "clocks": list(derive.clocks),
                "late_pm": _digest(pm), "late_cs": _digest(cs),
                "late_pm_fields": _fields(pm)}
    got = both()
    for (what, s, cpu), clock in zip(got["walls"], got["clocks"]):
        steps = ", ".join(f"{k} {v:.1f}" for k, v in clock["wall_s"].items())
        out(f"[{icao}] PREFIX TWICE {what} derive "
            f"{s:.1f} s (cpu {cpu:.1f} s), steps sum {clock['total_s']:.1f} s: {steps}")
    out(f"[{icao}] PREFIX TWICE late map digest pm {got['late_pm']} cs {got['late_cs']}")
    out(f"[{icao}] PREFIX TWICE late map fields "
        + " ".join(f"{k}={v}" for k, v in got["late_pm_fields"].items()))
    return got
