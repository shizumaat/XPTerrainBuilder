"""THE BUILD'S PREFIX RUN AHEAD IN ONE POOL WORKER — the plumbing the
speculative derives share (issue #2044; cold-patch-300s spec §3.1 C4b).

A build runs its prefix (``pipeline/prefix.Deriver``) four times: the main
pass, stage 1's ribbon-free map, the gap stage and the pad roads.  Where a
derive's inputs are known before the build reaches it, ONE pool worker runs
it ahead, beside the work the build is doing here:

* the pad roads' derive beside the gap stage (``pipeline/late_speculate``);
* stage 1's ribbon-free derive beside the main pass's shapes, constraints
  and strips (``pipeline/stage_one_ahead``).

This module is what both do the same way: whether a worker may be started
at all (:func:`may_start` — the pool's budget, and room on the machine for
one more process this build's size, ``pool_memory.room_for_copy``), the
payload a worker rebuilds the build's own :class:`Deriver` from
(:func:`payload`, :func:`worker_deriver`), the answer it ships back
(:func:`answer`) and how the build takes that answer as its own next run
(:func:`install`).  The worker writes the prefix's records through the
build's own cache, rebuilt from :meth:`~pipeline.front_cache.FrontCache.
worker_state`, so a later build is served exactly as after a serial one.

A caller's fallback IS the serial path: any doubt — no worker, a worker
that raised, an answer to another question — and the derive runs here, so
the output cannot change; only the clock does."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..airport import pool as _pool
from ..airport import pool_memory as _mem

__all__ = ["may_start", "raw_airport", "payload", "start", "worker_deriver", "answer",
           "install", "worker_clock"]


def may_start(what: str) -> str:
    """``""`` when a worker may run a copy of this build's prefix now, else
    why not (a phrase for the caller's "not speculated" line): the pool's
    budget is one, or the machine has no room for one more process this
    build's size above its free floor."""
    allowed, bound = _pool.budget_bound()
    if allowed < 2:
        return f"pool budget 1 ({bound})"
    ok, why = _mem.room_for_copy(_pool.physical_ram_gb())
    return "" if ok else f"no room for a second {what}: {why}"


def raw_airport(airport):
    """``airport`` with its real DEM (a cache's recorder stays here)."""
    from ..airport.dem_record import DemRecorder
    dem = getattr(airport, "dem", None)
    return _dc.replace(airport, dem=dem.target()) if type(dem) is DemRecorder else airport


def payload(derive, runs: int, **extra: _t.Any) -> dict:
    """What a worker rebuilds ``derive`` from (:func:`worker_deriver`):
    its airport, law, inputs, pack, keywords and common inputs, the build's
    cache state and ``classify``'s side state; ``runs`` is the worker
    deriver's run count BEFORE its call (the build's own derive's count
    where this run would sit), ``extra`` the caller's own entries."""
    from .front_cache import classify_side_state
    cache = derive.cache
    return {"derive_airport": raw_airport(derive.airport), "law": derive.law,
            "inputs": derive.inputs, "pack": _pack(derive), "kw": dict(derive.kw),
            "common": derive.common, "runs": int(runs),
            "cache": cache.worker_state() if cache is not None else None,
            "side": classify_side_state(), **extra}


def _law_of(derive):
    """The law the prefix's planar stage is handed (the cache's recording
    proxy while it is on, ``FrontCache.stage_law``)."""
    return derive.cache.stage_law() if derive.cache is not None else derive.law


def _pack(derive):
    """The build's pack read with its ``ResourceCache`` carrying this
    build's pack readings to the worker (``planar/pack_reads.shipped``)."""
    from ..planar.pack_reads import shipped
    pack = derive.pack
    if getattr(pack, "resources", None) is None:
        return pack
    return pack._replace(resources=shipped(derive.airport, pack.objects, pack.resources,
                                           _law_of(derive)))


def start(task: _t.Callable, payload_: dict, extra: tuple = (), *, what: str,
          out: _t.Callable[[str], None], stall_s: float
          ) -> "tuple[_t.Any, _t.Any, _t.Any] | str":
    """Ship ``payload_`` and start ``task((spec, *extra))`` in ONE isolated
    pool worker: ``(pool, pending, shared)``, or why it could not start
    (everything it took released)."""
    try:
        shared = _pool.share_object(payload_)
    except Exception as exc:                       # no shared memory: serial
        return f"{type(exc).__name__}: {exc}"
    pool = _pool.WorkPool(workers=1, isolate=True, out=out, stall_s=stall_s)
    pending = pool.begin(task, [(shared.spec, *extra)], what=what, unit="derive")
    if pending is None:
        why = pool.reason
        pool.close()
        shared.close()
        return why or "the worker did not start"
    return pool, pending, shared


def worker_deriver(p: _t.Mapping[str, _t.Any]):
    """IN THE WORKER: ``(the build's Deriver rebuilt from the payload, its
    cache)`` — ``classify``'s side state installed first."""
    from .front_cache import FrontCache, install_classify_side_state
    from .prefix import Deriver
    install_classify_side_state(p["side"])
    airport = p["derive_airport"]
    fc = None if p["cache"] is None else FrontCache.in_worker(p["cache"], airport, p["law"])
    if fc is not None:
        airport = fc.airport(airport)
    deriver = Deriver(airport, p["law"], p["inputs"], p["pack"], cache=fc,
                      common=p["common"], **p["kw"])
    deriver.runs = p["runs"]
    if getattr(p["pack"], "resources", None) is not None:
        from ..planar.pack_reads import adopt
        adopt(airport, p["pack"].objects, p["pack"].resources, _law_of(deriver))
    return deriver, fc


def answer(deriver, fc, **extra: _t.Any) -> dict:
    """IN THE WORKER: what crosses back — the run's record without its
    airport and hold (rebuilt by :func:`install`), the flat-site verdict
    and the cache's stage report."""
    rec = deriver.last
    stages = fc.finish().get("stages", {}) if fc is not None else {}
    return {"flat_site": rec.airport.flat_site, "stages": stages,
            "record": _dc.replace(rec, airport=None, hold=None), **extra}


def install(derive, res: _t.Mapping[str, _t.Any]) -> tuple:
    """The worker's prefix run as ``derive``'s own next run: its run count,
    ``last`` (airport with the worker's flat-site verdict, hold re-bound)
    and its cache report; returns ``(pm, cs, strips, hold)``."""
    from ..constraints.no_step import hold_pass
    airport = _dc.replace(derive.airport, flat_site=res["flat_site"])
    rec = _dc.replace(res["record"], airport=airport)
    derive.runs += 1
    derive.last = _dc.replace(rec, hold=hold_pass(rec.pm, derive.law, airport))
    if derive.cache is not None and derive.cache.active:
        derive.cache.report["stages"].update(res["stages"])
    return derive.last.derived()


def worker_clock(derive) -> str:
    """The worker's prefix run as a phrase for the HIT line: its seconds,
    and the planar stage's (``PrefixRecord.wall``) — a clock, never a
    product."""
    wall = dict(getattr(derive.last, "wall", None) or {})
    return (f"the worker's prefix {sum(wall.values()):.1f} s "
            f"(planar {wall.get('planar', 0.0):.1f} s)")
