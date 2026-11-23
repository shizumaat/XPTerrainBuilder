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
shared with the build's other run-ahead derives.

STARTED AT CLASSIFY'S END (#2206, fastest-pipeline spec item 5;
:func:`start_early`).  Stage 1's classification is known before the main
pass's planar stage, and the full map's decks are final at its structures
step (``planar/build``: :func:`model.stage_one.full_decks`), its anchors once
its channels have run.  So the worker starts before the main pass's planar
stage and reads the full map through a :class:`_LazyFull`: its first read of
the decks waits for the build to hand them (with the pack readings the main
pass made, the very ones the serial derive is handed), its first read of the
anchors for those.  Its planar stage, flat site and road profile run beside
the main pass's arrangement and channels.  The digest check is unchanged:
the finished map's decks and anchors must be the ones handed, else (or with
no hand-over, a worker that raised or waited past :data:`STALL_S`) stage 1
is derived here."""
from __future__ import annotations

import dataclasses as _dc
import os
import pickle
import shutil
import tempfile
import time
import typing as _t

from ..airport import pool as _pool
from ..airport import stage_cache as _store
from . import derive_ahead as _ahead

__all__ = ["start", "start_early"]

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
    split = stage_one_classification(cl, pm_channels)
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


def start_early(cl, derive, out: _t.Callable[[str], None]) -> "Ahead | None":
    """Start stage 1's derive of ``cl`` in a worker BEFORE the main pass's
    planar stage (module doc, #2206 item 5), or ``None``: ``cl`` has no
    stage-1 classification of its own without the full map (a generated
    deck's no-bridge airside, which :func:`start` decides after the
    channels), or no worker may start (said through ``out``).  The build
    hands the full map with :meth:`Ahead.hand_decks` / :meth:`Ahead.
    hand_anchors`."""
    from .stage_one_map import stage_one_classification
    split = stage_one_classification(cl)
    if split is None:
        return None
    why = _ahead.may_start("build")
    if why:
        out(f"stage 1's ribbon-free derive not run ahead (#2044): {why}")
        return None
    folder = tempfile.mkdtemp(prefix="o4_stage1_ahead_")
    cl_digest = derive.cache.digest(split[0]) if derive.cache is not None else None
    got = _ahead.start(_derive_stage_one, _ahead.payload(
        derive, derive.runs, cl0=split[0], cl_digest=cl_digest, full=_LazyFull(folder, STALL_S)),
        what="stage 1's ribbon-free derive (ahead)", out=out, stall_s=STALL_S)
    if isinstance(got, str):
        shutil.rmtree(folder, ignore_errors=True)
        out(f"stage 1's ribbon-free derive not run ahead (#2044): {got}")
        return None
    pool, pending, shared = got
    out(f"stage 1's ribbon-free derive run ahead from classify's end (#2206 item 5): "
        f"worker pid {pool.pids()}, payload {shared.nbytes / 1e6:.0f} MB")
    return Ahead(derive, split, None, pool, pending, shared, out, folder=folder)


def _hand_name(name: str) -> str:
    """A hand-over file's name: ``o4_stage``-prefixed, so the stage cache's
    file witness skips it (``airport/file_witness``).  It is gone when the
    worker's run ends, and a record witnessing it is refused on the next
    build (#2205)."""
    return f"o4_stage1_hand_{name}.pkl"


class _LazyFull:
    """IN THE WORKER: the full map as the build hands it (:func:`start_early`)
    — ``decks``, ``deck_anchors`` and ``vertices`` (:class:`FullView`'s),
    each read waiting for its hand-over file, at most ``stall_s``; the
    build's abort, or no file by then, raises (the build derives here).
    ``on_decks(placed)``: the worker's hook for the pack readings handed with
    the decks, called once, before the decks are read."""

    def __init__(self, folder: str, stall_s: float) -> None:
        self.folder, self.stall_s = folder, float(stall_s)
        self.on_decks: _t.Callable[[dict], None] | None = None
        self._got: dict[str, dict] = {}

    def __getstate__(self) -> dict:
        return {"folder": self.folder, "stall_s": self.stall_s}

    def __setstate__(self, st: dict) -> None:
        self.__init__(st["folder"], st["stall_s"])

    def _wait(self, name: str) -> dict:
        if name not in self._got:
            path = os.path.join(self.folder, _hand_name(name))
            end = time.monotonic() + self.stall_s
            while not os.path.exists(path):
                if os.path.exists(os.path.join(self.folder, "abort")) or time.monotonic() > end:
                    raise RuntimeError(f"the build handed no {name}")
                time.sleep(0.02)
            with open(path, "rb") as f:
                got = pickle.load(f)
            if name == "decks" and self.on_decks is not None:
                self.on_decks(got.get("placed") or {})
            self._got[name] = got
        return self._got[name]

    @property
    def decks(self) -> tuple:
        return self._wait("decks")["decks"]

    @property
    def deck_anchors(self) -> tuple:
        return self._wait("anchors")["deck_anchors"]

    @property
    def vertices(self) -> dict:
        return self._wait("anchors")["vertices"]


def _derive_stage_one(_state, task) -> dict:
    """THE WORKER: the build's prefix on the ribbon-free classification,
    under the blocks ``stage_one_problem`` runs it in."""
    (spec,) = task
    p = _pool.shared_object(spec)
    from ..constraints.door_pad import stage_one as _no_door_pads
    from ..model.stage_one import from_full
    from ..planar.group_low import stage_one as _no_group_levels
    deriver, fc = _ahead.worker_deriver(p)
    if isinstance(p["full"], _LazyFull):
        p["full"].on_decks = lambda placed: _ahead.adopt_reads(deriver, placed)
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

    def __init__(self, derive, split: tuple, view_digest: "str | None", pool, pending,
                 shared, out, folder: "str | None" = None) -> None:
        self.derive, self.split, self.view_digest = derive, split, view_digest
        self.pool, self.pending, self.shared, self.out = pool, pending, shared, out
        #: why the worker's answer will not be taken (``""``: it may be)
        self.refused = ""
        #: ``"hit"``, ``"miss"`` or ``"no answer"`` once called
        self.outcome = ""
        #: :func:`start_early`'s hand-over folder, and the decks handed
        self.folder, self._decks = folder, None

    def _hand(self, name: str, obj: dict) -> None:
        tmp = os.path.join(self.folder, _hand_name(name) + ".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(obj, f, protocol=5)
        os.replace(tmp, os.path.join(self.folder, _hand_name(name)))

    def hand_decks(self, decks) -> None:
        """The full map's decks, final (``model.stage_one.full_decks``), and
        the pack readings made so far — once; a no-op for :func:`start`'s."""
        if self.folder is None or self._decks is not None or self.pending is None:
            return
        self._decks = tuple(decks)
        try:
            self._hand("decks", {"decks": self._decks,
                                 "placed": _ahead.shipped_reads(self.derive)})
        except Exception as exc:                   # the worker waits, then raises
            self.refused = f"the decks were not handed ({type(exc).__name__}: {exc})"

    def hand_anchors(self, pm_channels) -> None:
        """The full map after its channels: its deck anchors and their
        vertices (and its decks, when the planar stage handed none — a served
        planar record); the view the finished map is checked against."""
        if self.folder is None or self.pending is None:
            return
        self.hand_decks(getattr(pm_channels, "decks", ()) or ())
        view = _dc.replace(full_view(pm_channels), decks=self._decks)
        try:
            self._hand("anchors", {"deck_anchors": view.deck_anchors,
                                   "vertices": view.vertices})
            self.view_digest = _store.content_digest(view)
        except Exception as exc:
            self.refused = f"the anchors were not handed ({type(exc).__name__}: {exc})"

    def rebind(self, airport) -> None:
        """The airport the serial derive would have been handed (the main
        pass's, with its flat-site verdict): the build's later derives take
        it.  The worker started without that verdict, and the planar stage
        reads it only through ``law.inset_class.ground_class``, so a verdict
        naming another ground class, or any other field changed, refuses the
        worker's answer."""
        from ..law.inset_class import ground_class
        a, law = self.derive.airport, self.derive.law
        if a is airport:
            return
        if not all(getattr(a, f.name) is getattr(airport, f.name)
                   for f in _dc.fields(airport) if f.name != "flat_site"):
            self.refused = self.refused or "the main pass changed the airport"
        elif ground_class(a, law) != ground_class(airport, law):
            self.refused = self.refused or "the flat-site verdict names another ground class"
        self.derive.airport = airport

    @property
    def last(self):
        return self.derive.last

    def bind(self, pm_full) -> "Ahead":
        """The finished main map: its decks and anchors must be the ones the
        worker was handed."""
        if self.view_digest is None:
            self.refused = self.refused or "the main pass handed no decks and anchors"
        elif _store.content_digest(full_view(pm_full)) != self.view_digest:
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
                 f"{self.derive.runs} is stage 1's (waited {waited:.1f} s; "
                 f"{_ahead.worker_clock(self.derive)})")
        return derived

    def close(self) -> None:
        """Release the worker, the shared block and the hand-over folder
        (idempotent)."""
        if self.folder is not None and self.pending is not None:
            try:                                   # a worker still waiting stops
                open(os.path.join(self.folder, "abort"), "wb").close()
            except OSError:
                pass
        self.pool.close()
        if self.shared is not None:
            self.shared.close()
        self.pending = self.shared = None
        if self.folder is not None:
            shutil.rmtree(self.folder, ignore_errors=True)
