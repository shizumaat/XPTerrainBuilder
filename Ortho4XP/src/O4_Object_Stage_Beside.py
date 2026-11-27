"""The object stage BESIDE the tile's masks and imagery steps (#1264).

The mesh step ends with the object stage (``O4_Object_Stage.run``): it fits
the custom airport packs' objects to the mesh just written, 100-230 s on a
pack tile, mostly waiting on the airports' plans computed in worker
processes.  Nothing the masks and imagery steps read is written by it (the
pack DSFs, the pack journal, the mod cache and the tile's degraded rows are
read only after those steps; the record the mesh step hands on leaves its
pack DSFs out, ``O4_Step_Reuse``), so where the build goes on to the
imagery step the stage runs in a thread beside them and is JOINED where its
outputs are first needed:

* the imagery step joins it before its completion block (activation,
  cleaning, the pack journal's discard: ``O4_Tile_Utils.build_tile``);
* a step that is neither masks nor imagery of the same tile, a failed or
  stopped step, and the end of the tile's build in this process join it
  first (``o4_engine.session``), so a Stop puts the packs back only once
  the stage has finished writing them;
* a worker process ends only after it (``o4_engine.jsonl``, within the
  shutdown grace).

Only a caller that knows the imagery step follows turns it on
(:func:`want`): the session's in-process walk, a worker child told so by
its parent, ``tools/profile_tile_build.py --objects-beside``.  Everywhere
else (the Qt per-step Mesh button, a tile bundle's import, the harness) the
stage runs inline at the end of the mesh step, as before.

The mesh step's record (``O4_Step_Reuse.record``) is cut WITHOUT the
stage's pack DSFs and code while the stage runs (a build that dies before
the join runs the stage again over the reused mesh), and re-cut at the
join when nothing stopped the build.

The thread holds no machine slot (``O4_Step_Overlap.beside``,
``needs_core=False``): its planning ahead takes slots of its own
(``slot_gated_pool``), and its own Python shares the step process's
interpreter lock.  Its file-witness windows record only its own thread's
opens (``O4_Object_Stage.run(tile, beside=True)``).
"""
from __future__ import annotations

import operator
import threading

import O4_Step_Overlap as OVERLAP
import O4_UI_Utils as UI

__all__ = ["RUNS_BESIDE", "want", "run", "pending", "recut_when_done",
           "before_step", "join"]

#: the steps of the same tile that run while its object stage does
RUNS_BESIDE = ("masks", "imagery")

#: the tiles whose mesh step may leave its object stage running
_WANTED: set = set()
#: this process's running stages: tile key -> _Job
_JOBS: dict = {}
_GUARD = threading.Lock()


#: a tile's key in both tables: its (lat, lon)
_key = operator.attrgetter("lat", "lon")


class _Job:
    """One tile's stage in its thread."""

    def __init__(self, tile) -> None:
        import O4_Object_Stage as OBJECT_STAGE
        self.tile = tile
        self.recut = None
        self.handle = OVERLAP.beside(OBJECT_STAGE.run, tile, True,
                                     what="object stage", needs_core=False)


def want(tile, on: bool) -> None:
    """Whether ``tile``'s next mesh step may leave its object stage
    running beside the steps after it (the caller knows the imagery step
    follows, which joins it).  That mesh step takes the answer."""
    with _GUARD:
        if on:
            _WANTED.add(_key(tile))
        else:
            _WANTED.discard(_key(tile))


def run(tile) -> None:
    """The end of the mesh step: the object stage, started beside when
    :func:`want` said so, else run here.  Never raises (as
    ``O4_Object_Stage.run``)."""
    import O4_Object_Stage as OBJECT_STAGE
    join()                          # never two at once, never another tile's
    with _GUARD:                    # one mesh step's: taken here
        beside = _key(tile) in _WANTED
        _WANTED.discard(_key(tile))
    if not beside:
        OBJECT_STAGE.run(tile)
        return
    UI.vprint(1, "   Object stage: running beside the masks and imagery "
                 "steps (#1264).")
    job = _Job(tile)
    with _GUARD:
        _JOBS[_key(tile)] = job


def pending(tile=None) -> bool:
    """``tile``'s object stage (any, when ``None``) still runs beside."""
    with _GUARD:
        return bool(_JOBS) if tile is None else _key(tile) in _JOBS


def recut_when_done(tile, recut) -> None:
    """The mesh step's record was cut while the stage ran: ``recut()``
    cuts it again when the stage is joined (see the module doc)."""
    with _GUARD:
        job = _JOBS.get(_key(tile))
        if job is not None:
            job.recut = recut


def before_step(tile, step: str) -> None:
    """``step`` of ``tile`` starts: every stage it may not run beside is
    joined first."""
    with _GUARD:
        others = [k for k in _JOBS
                  if k != _key(tile) or step not in RUNS_BESIDE]
    for key in others:
        _join_one(key)


def join(tile=None) -> None:
    """Wait for ``tile``'s stage (every stage when ``None``) and, when the
    mesh step's record was cut while it ran and no Stop came, re-cut it.
    Never raises."""
    with _GUARD:
        keys = list(_JOBS) if tile is None else [_key(tile)]
    for key in keys:
        _join_one(key)


def _join_one(key) -> None:
    with _GUARD:
        job = _JOBS.get(key)
    if job is None:
        return
    try:
        job.handle.result()
    except Exception as error:                    # pragma: no cover
        UI.vprint(1, "   Object stage beside the steps failed:", error)
    with _GUARD:
        _JOBS.pop(key, None)
    if job.recut is not None and not UI.red_flag:
        job.recut()
