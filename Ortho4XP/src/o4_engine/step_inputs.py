"""A MISSING CACHE FILE NEVER FAILS A TILE (owner 2026-11-18T13:05Z: "Any
cache file should not fail, it should just be rebuilt shouldn't it?").

A build step reads the intermediate files the step before it wrote: the
mesh step the vector step's ``.node`` / ``.poly`` / ``.alt``, the masks and
imagery steps the mesh step's ``.mesh``.  Those are cache: when one is
absent -- deleted, moved to a storage tier, never written -- the step that
needs it does not fail the tile.  The step detects the absence itself
(its "could not find" check, or the ``FileNotFoundError`` of an input that
vanished WHILE it ran, the +53+010 incident); :func:`run_fed` then

* lays the input back from a storage tier (``recall``), or, when no tier
  holds it, runs the PRODUCING step again (its record dropped, then
  written again when it succeeds), with one log line naming the file;
* drops the failure the step recorded (``discard``) and runs the step
  once more.

Decided here, per step, never per file in the step code (a step's start
already lays back what a tier holds, ``session._recall_from_tier``).  Only a step's
own inputs from an earlier step count: any other missing file still fails
as before.  No tile or airport is named here.
"""
from __future__ import annotations

import os
import typing as _t

import O4_File_Names as FNAMES
import O4_Step_Reuse as REUSE
import O4_UI_Utils as UI

__all__ = ["PRODUCER", "required_inputs", "missing_inputs", "run_fed"]

#: the step whose outputs a step reads
PRODUCER = {"mesh": "vector", "masks": "mesh", "imagery": "mesh"}


def required_inputs(tile, step: str) -> list:
    """The files ``step`` reads that its producer wrote (empty: none)."""
    if step == "mesh":
        files = [FNAMES.input_node_file(tile), FNAMES.alt_file(tile)]
        if not getattr(tile, "iterate", 0):
            files.append(FNAMES.input_poly_file(tile))
        return files
    if step in ("masks", "imagery"):
        return [FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)]
    return []


def missing_inputs(tile, step: str) -> list:
    """:func:`required_inputs` not on disk now."""
    return [f for f in required_inputs(tile, step) if not os.path.isfile(f)]


def _noun(step: str) -> str:
    from .session import STEP_FAILURE_NOUNS
    return STEP_FAILURE_NOUNS.get(step, step)


def _rebuild_producer(run, tile, step: str, missing: list, recall,
                      discard) -> bool:
    producer = PRODUCER[step]
    UI.vprint(0, "   %s step: its input %s is missing; building the %s "
                 "step again." % (_noun(step).capitalize(),
                                  os.path.basename(missing[0]),
                                  _noun(producer)))
    REUSE.forget_from(tile, producer)
    if run_fed(run, tile, producer, recall, discard) != 1 or UI.red_flag:
        return False
    REUSE.record(tile, producer)
    return True


def _ours(error: FileNotFoundError, tile, step: str) -> bool:
    named = os.path.abspath(str(error.filename or ""))
    return named in {os.path.abspath(f) for f in required_inputs(tile, step)}


def run_fed(run: _t.Callable[[str], int], tile, step: str,
            recall: _t.Callable[[], None],
            discard: _t.Callable[[], None] = lambda: None,
            _depth: int = 0) -> int:
    """``run(step)``; when it fails for want of an input its producer
    wrote (module doc), that input is laid back (``recall``) or its
    producer run again, the failure the step recorded dropped
    (``discard``), and the step run once more.  ``run``'s result; 0 when
    a producer it needed failed."""
    try:
        result = run(step)
        vanished = False
    except FileNotFoundError as error:
        if _depth or UI.red_flag or not _ours(error, tile, step):
            raise
        result, vanished = 0, True
    if result == 1 or _depth or UI.red_flag or step not in PRODUCER:
        return result
    missing = missing_inputs(tile, step)
    if not missing and not vanished:
        return result                   # failed for another cause
    discard()
    if missing:
        recall()
        missing = missing_inputs(tile, step)
    if missing:
        if not _rebuild_producer(run, tile, step, missing, recall, discard):
            return 0
    else:
        UI.vprint(0, "   %s step: an input it read vanished while it ran; "
                     "running it again." % (_noun(step).capitalize(),))
    return run_fed(run, tile, step, recall, discard, _depth + 1)
