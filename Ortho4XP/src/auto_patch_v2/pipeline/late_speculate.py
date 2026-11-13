"""THE PAD ROADS' DERIVE BESIDE THE GAP STAGE, SPECULATIVELY (cold-patch
300 s spec §3.1 C4b; issue #412).

``late_stage.run_last_stages`` solves the gap pieces first, then the pad
roads against them (13a (1)): two derives in sequence, the second on a
classification the roads cut mints from the gap stage's solved levels — the
pads' medians (``pad_road_exit``) and the ramp feet's run-outs
(``ramp_runout``).  The pads are CONSTANTS of the gap stage
(``stage_one_map.late_fixed``), so the same cut read off the MAIN base is
the gap stage's own whenever no level it reads moved.

So the moment the gap pieces are cut, ONE pool worker cuts the pad roads off
the main base and runs the build's own prefix on that classification
(:func:`speculate`), beside the gap stage's derive and solve here.  When the
roads pass comes, its real cut is digested (``stage_cache.
canonical_digest``) and compared with the worker's: EQUAL, the worker's
derive is the roads pass's (:class:`Speculated`); DIFFERENT — or no answer,
or no pool — the derive runs here as it always did.  The fallback IS the
serial path, so the output cannot change; only the clock does.

The worker writes the prefix's records through the build's own cache,
rebuilt from :meth:`~pipeline.front_cache.FrontCache.worker_state`, so a
later build is served exactly as after a serial one.  It posts its cut's
digest the moment it has it, so a miss is known without waiting for the
derive."""
from __future__ import annotations

import time
import typing as _t
from multiprocessing import shared_memory as _shm

from ..airport import pool as _pool
from ..airport import stage_cache as _store
from . import derive_ahead as _ahead

__all__ = ["speculate", "Speculated"]

#: the longest the roads pass waits on the worker's derive (seconds)
STALL_S = 1800.0
#: the digest post: one flag byte, then the 32 bytes of the sha256
_POST = 33


def speculate(derive, cl_all, airport, law, base_solution: _t.Mapping[str, _t.Any], *,
              rules=None, out: _t.Callable[[str], None] = print) -> "Speculated | None":
    """Start the roads pass's cut and derive in a worker (module doc), or
    ``None`` (said through ``out``) when no worker can take it: the derive
    is not the build's :class:`~pipeline.prefix.Deriver`, the pool's
    budget is one, the machine has no room for a second build
    (``derive_ahead.may_start``), or the payload will not ship."""
    from .prefix import Deriver
    if not isinstance(derive, Deriver):
        return None
    why = _ahead.may_start("build")
    if why:
        out(f"LAST STAGE pad roads' derive not speculated (C4b): {why}")
        return None
    if rules is None:
        from ..classify.rules import load_rules
        rules = load_rules()
    # the gap stage's derive is this derive's next run: the roads pass's
    # is the one after it
    payload = _ahead.payload(derive, derive.runs + 1, cl=cl_all, airport=_ahead.raw_airport(
        airport), base={"pm": base_solution["pm"], "z": base_solution["z"]}, rules=rules)
    post = None
    try:
        post = _shm.SharedMemory(create=True, size=_POST)
        post.buf[:_POST] = bytes(_POST)
    except Exception as exc:                       # no shared memory: serial
        out(f"LAST STAGE pad roads' derive not speculated (C4b): {type(exc).__name__}: {exc}")
        _release(post, None)
        return None
    got = _ahead.start(_derive_roads, payload, (post.name,),
                       what="the pad roads' derive (speculative)", out=out, stall_s=STALL_S)
    if isinstance(got, str):
        out(f"LAST STAGE pad roads' derive not speculated (C4b): {got}")
        _release(post, None)
        return None
    pool, pending, shared = got
    out(f"LAST STAGE pad roads' cut and derive speculated off the main base (C4b): "
        f"worker pid {pool.pids()}, payload {shared.nbytes / 1e6:.0f} MB")
    return Speculated(derive, pool, pending, shared, post, out)


def _release(post, shared) -> None:
    if shared is not None:
        shared.close()
    if post is not None:
        for step in (post.close, post.unlink):
            try:
                step()
            except Exception:
                pass


def _derive_roads(_state, task) -> dict:
    """THE WORKER: the roads cut off the main base, its digest posted, then
    the build's prefix on it through the build's records."""
    spec, post_name = task
    p = _pool.shared_object(spec)
    from .late_stage import late_cut
    deriver, fc = _ahead.worker_deriver(p)
    cut = late_cut(p["cl"], p["airport"], p["law"], p["base"], rules=p["rules"],
                   out=lambda _m: None, roads_only=True)
    digest = _store.content_digest(cut.cl)
    _post(post_name, digest)
    deriver(cut.cl)
    return _ahead.answer(deriver, fc, digest=digest)


def _post(name: str, digest: str) -> None:
    try:
        blk = _shm.SharedMemory(name=name, track=False)
    except TypeError:                                  # an interpreter before 3.13
        blk = _shm.SharedMemory(name=name)
    try:
        blk.buf[1:_POST] = bytes.fromhex(digest)
        blk.buf[0] = 1
    finally:
        blk.close()


class Speculated:
    """``derive`` with the roads pass's derive computed ahead in a worker
    (module doc).  Called on the roads pass's real cut classification it
    returns the worker's ``(pm, cs, strips, hold)`` when the digests agree,
    else derives here; ``last`` is ``derive.last`` either way (the late
    solve's record is keyed on it).  :meth:`close` releases the worker."""

    def __init__(self, derive, pool, pending, shared, post, out) -> None:
        self.derive, self.pool, self.pending = derive, pool, pending
        self.shared, self.post, self.out = shared, post, out
        #: ``"hit"``, ``"miss"`` or ``"no answer"`` once called
        self.outcome = ""

    @property
    def last(self):
        return self.derive.last

    def __call__(self, cl) -> tuple:
        if self.post is None:                      # answered once already
            return self.derive(cl)
        got = self._take(_store.content_digest(cl))
        self.close()
        return self.derive(cl) if got is None else got

    def _posted(self) -> str | None:
        buf = self.post.buf
        return bytes(buf[1:_POST]).hex() if buf[0] else None

    def _take(self, digest: str) -> tuple | None:
        say = self.out
        posted = self._posted()
        if posted is not None and posted != digest:
            self.outcome = "miss"
            say("LAST STAGE pad roads' derive speculation MISSED (C4b): the gap stage moved "
                "a level the roads cut reads — derived here")
            return None
        t = time.perf_counter()
        try:
            res = self.pending.collect()
        except Exception as exc:                   # the worker's own error: serial
            say(f"LAST STAGE pad roads' derive speculation: the worker raised "
                f"{type(exc).__name__}: {exc} — derived here")
            res = None
        waited = time.perf_counter() - t
        say(self.pool.line())
        if res is None or res[0]["digest"] != digest:
            self.outcome = "no answer" if res is None else "miss"
            say(f"LAST STAGE pad roads' derive speculation {self.outcome.upper()} (C4b) "
                f"after {waited:.1f} s — derived here")
            return None
        return self._install(res[0], waited)

    def _install(self, res: dict, waited: float) -> tuple:
        """The worker's prefix run as this derive's own next run."""
        derived = _ahead.install(self.derive, res)
        self.outcome = "hit"
        self.out(f"LAST STAGE pad roads' derive speculation HIT (C4b): the worker's "
                 f"prefix run {self.derive.runs} is the roads pass's (waited {waited:.1f} s; "
                 f"{_ahead.worker_clock(self.derive)})")
        return derived

    def close(self) -> None:
        """Release the worker and the shared blocks (idempotent)."""
        self.pool.close()
        _release(self.post, self.shared)
        self.post = self.shared = None
