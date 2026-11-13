"""STAGE 1'S RIBBON-FREE DERIVE, RUN AHEAD BESIDE THE MAIN PASS (issue
#2044).

The build derives stage 1's map (``pipeline/stage_one_map.
stage_one_problem``: its own prefix on the classification without ribbons)
AFTER the main pass's prefix has finished.  But the derive reads only two
things of the main pass: the classification (known before it starts) and
the FULL map's decks and deck anchors (``model/stage_one.from_full``, deck
redesign §1) — and those are final once the target channels have run
(``constraints/runway_chord`` derives the anchors; nothing after it
touches them).  The main pass's shapes, constraint generators and jetway
strips that follow (KDEN 1.0.509: 87 s) are work stage 1 never reads.

So the moment the main pass's channels are done (``run_prefix``'s
``after_channels``), ONE pool worker runs stage 1's derive on the
ribbon-free classification, under the same three blocks the build's own
call runs it in (no door pads, no group levels, the full map's decks and
anchors), while the build finishes its main pass here.  When the build
reaches stage 1 it binds the finished map (:meth:`Ahead.bind`): the decks,
the anchors and the anchors' vertices must be EXACTLY what the worker was
handed (a digest of both) — then the worker's run is the build's own
(``derive_ahead.install``); else, or with no answer, the derive runs here
as it always did.  The fallback IS the serial path, so the output cannot
change; only the clock does.  The plumbing is ``pipeline/derive_ahead``'s,
shared with the pad roads' speculation (``pipeline/late_speculate``)."""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

from ..airport import pool as _pool
from ..airport import stage_cache as _store
from . import derive_ahead as _ahead

__all__ = ["FullView", "full_view", "start", "Ahead"]

#: the longest the build waits on the worker's derive (seconds)
STALL_S = 1800.0


@_dc.dataclass(frozen=True)
class FullView:
    """What stage 1's derive reads of the FULL map (``model/stage_one.
    full_map``'s readers: ``planar/build`` the decks, ``constraints/
    deck_anchor._from_full`` the anchors and their vertices)."""

    decks: tuple
    deck_anchors: tuple
    vertices: dict


def full_view(pm) -> FullView:
    """``pm``'s decks, deck anchors and the anchors' vertices."""
    anchors = tuple(getattr(pm, "deck_anchors", ()) or ())
    return FullView(tuple(getattr(pm, "decks", ()) or ()), anchors,
                    {a.v: pm.vertices[a.v] for a in anchors})


def start(cl, derive, pm_channels, out: _t.Callable[[str], None]) -> "Ahead | None":
    """Start stage 1's derive of ``cl`` in a worker, ``pm_channels`` the main
    pass's map after its target channels, or ``None`` (said through ``out``
    unless ``cl`` has no stage-1 map of its own)."""
    from .stage_one_map import stage_one_classification
    split = stage_one_classification(cl)
    if split is None:
        return None
    why = _ahead.may_start("build")
    if why:
        out(f"stage 1's ribbon-free derive not run ahead (#2044): {why}")
        return None
    view = full_view(pm_channels)
    # the classification's digest is the BUILD's: the canonical digest
    # follows object identity, and the worker's copy is an unpickled one
    cl_digest = derive.cache.digest(split[0]) if derive.cache is not None else None
    got = _ahead.start(_derive_stage_one, _ahead.payload(derive, derive.runs, cl0=split[0],
                                                         cl_digest=cl_digest, full=view),
                       what="stage 1's ribbon-free derive (ahead)", out=out, stall_s=STALL_S)
    if isinstance(got, str):
        out(f"stage 1's ribbon-free derive not run ahead (#2044): {got}")
        return None
    pool, pending, shared = got
    out(f"stage 1's ribbon-free derive run ahead beside the main pass (#2044): worker pid "
        f"{pool.pids()}, payload {shared.nbytes / 1e6:.0f} MB")
    return Ahead(derive, split, _store.content_digest(view), pool, pending, shared, out)


def _derive_stage_one(_state, task) -> dict:
    """THE WORKER: the build's prefix on the ribbon-free classification,
    under the blocks ``stage_one_problem`` runs it in."""
    (spec,) = task
    p = _pool.shared_object(spec)
    from ..constraints.door_pad import stage_one as _no_door_pads
    from ..model.stage_one import from_full
    from ..planar.group_low import stage_one as _no_group_levels
    deriver, fc = _ahead.worker_deriver(p)
    with _no_door_pads(), _no_group_levels(), from_full(p["full"]):
        deriver(p["cl0"], p["cl_digest"])
    return _ahead.answer(deriver, fc)


class Ahead:
    """The build's ``derive`` with stage 1's run computed ahead in a worker
    (module doc).  :meth:`bind` the finished main map first; called on the
    ribbon-free classification it returns the worker's ``(pm, cs, strips,
    hold)`` when the map agrees, else derives here.  ``split`` is
    ``stage_one_classification``'s answer, for ``stage_one_problem``;
    :meth:`close` releases the worker."""

    def __init__(self, derive, split: tuple, view_digest: str, pool, pending, shared,
                 out) -> None:
        self.derive, self.split, self.view_digest = derive, split, view_digest
        self.pool, self.pending, self.shared, self.out = pool, pending, shared, out
        #: why the worker's answer will not be taken (``""``: it may be)
        self.refused = ""
        #: ``"hit"``, ``"miss"`` or ``"no answer"`` once called
        self.outcome = ""

    @property
    def last(self):
        return self.derive.last

    def bind(self, pm_full) -> "Ahead":
        """The finished main map: its decks and anchors must be the ones the
        worker was handed."""
        if _store.content_digest(full_view(pm_full)) != self.view_digest:
            self.refused = "the main pass moved a deck or an anchor after its channels"
        return self

    def __call__(self, cl0) -> tuple:
        if self.pending is None:                   # answered once already
            return self.derive(cl0)
        if cl0 is not self.split[0]:
            self.refused = self.refused or "asked for another classification"
        got = None if self.refused else self._take()
        self.close()
        if got is None:
            self.outcome = self.outcome or "miss"
            self.out(f"stage 1's ribbon-free derive ahead {self.outcome.upper()} (#2044): "
                     f"{self.refused or 'no answer'} — derived here")
            return self.derive(cl0)
        return got

    def _take(self) -> tuple | None:
        t = time.perf_counter()
        try:
            res = self.pending.collect()
        except Exception as exc:                   # the worker's own error: serial
            self.refused = f"the worker raised {type(exc).__name__}: {exc}"
            res = None
        waited = time.perf_counter() - t
        self.out(self.pool.line())
        if res is None:
            self.outcome = "no answer"
            return None
        derived = _ahead.install(self.derive, res[0])
        self.outcome = "hit"
        self.out(f"stage 1's ribbon-free derive ahead HIT (#2044): the worker's prefix run "
                 f"{self.derive.runs} is stage 1's (waited {waited:.1f} s)")
        return derived

    def close(self) -> None:
        """Release the worker and the shared block (idempotent)."""
        self.pool.close()
        if self.shared is not None:
            self.shared.close()
        self.pending = self.shared = None
