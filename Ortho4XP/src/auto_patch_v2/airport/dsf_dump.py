"""THE DSF DECODE — ``DSFTool --dsf2text``, atomic (#560), with the
crash retry (#568).

The READ side of a pack DSF, apart from the write half
(``airport/dsf_write``: edit → encode → verify → write) so that the
patch build, which reads pack DSFs but never writes one, does not key its
code on the writer (#1901): a change to the pack writer then re-runs the
object stage only, never the terrain solve.  ``dsf_write`` re-exports
:func:`dump` under its old name.
"""
from __future__ import annotations

import os
import tempfile
import time
import uuid

import O4_DSFTool as _dsftool
from O4_DSFTool import DsfToolError

from . import dsf_commands as _cmds

__all__ = ["dump", "DsfToolError"]

#: The one launcher (``O4_DSFTool.run``), shared with the write half and
#: the overlay step (#591).
_run = _dsftool.run


#: A ``<dump>.<pid>.<token>.partial`` older than this is the litter of a
#: process that was killed mid-dump; the next dump of that file removes it.
_PARTIAL_DUMP_STALE_S = 3600.0


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


#: Waits between attempts to rename a finished dump onto its name when the
#: rename is refused (about 2 s in all).
_LAND_RETRY_WAITS_S = (0.05, 0.1, 0.2, 0.4, 0.6, 0.65)


def _land_dump(partial: str, text_out: str, started: float) -> None:
    """Rename the finished ``partial`` onto ``text_out``.

    ON WINDOWS THE RENAME CAN BE REFUSED (``PermissionError``): another
    worker is renaming its own dump of the same DSF onto the name at this
    instant, or a reader has the old dump open (#560, PR #569 — six
    workers dump one pack DSF at once).  If a whole dump has landed there
    since this dump began (``started``), another writer won: it is the
    same text, so ours is dropped and theirs is used.  Otherwise the
    rename is tried again for about two seconds, then :class:`DsfToolError`
    names the refusal.  The caller removes ``partial`` on every path.
    """
    refusal: OSError | None = None
    for wait in (0.0,) + _LAND_RETRY_WAITS_S:
        if wait:
            time.sleep(wait)
        try:
            os.replace(partial, text_out)
            return
        except PermissionError as error:
            refusal = error
        try:
            landed = os.stat(text_out)
            # 2 s: the coarsest file-time step of a supported file system
            if landed.st_size > 0 and landed.st_mtime >= started - 2.0:
                return
        except OSError:
            pass
    raise DsfToolError(
        f"the finished text dump could not be moved onto {text_out}: "
        f"{refusal} — another program has that file open") from refusal


def _sweep_stale_partials(text_out: str) -> None:
    """Remove the ``.partial`` files a KILLED dump of ``text_out`` left."""
    folder, prefix = os.path.split(text_out)
    try:
        names = os.listdir(folder or ".")
    except OSError:
        return
    for name in names:
        if name.startswith(prefix + ".") and name.endswith(".partial"):
            path = os.path.join(folder, name)
            try:
                if time.time() - os.path.getmtime(path) > _PARTIAL_DUMP_STALE_S:
                    os.remove(path)
            except OSError:
                pass


def _dump_pool_selected(dsf_path: str, partial: str, text_out: str,
                        tool: str, timeout: float | None) -> bool:
    """The retry after a DSFTool CRASH (#568): dump a temp copy of the DSF
    whose command stream selects a pool first
    (:func:`dsf_commands.select_pool_first`).  ``False`` when the DSF does
    not have that trait — the crash is then another one and stands.  The
    DSF itself is never written; the copy lives in the system temp dir."""
    try:
        with open(dsf_path, "rb") as fh:
            repaired = _cmds.select_pool_first(fh.read())
    except OSError:
        return False
    if repaired is None:
        return False
    with tempfile.TemporaryDirectory(prefix="dsf_pool_select_") as folder:
        copy = os.path.join(folder, os.path.basename(dsf_path))
        with open(copy, "wb") as fh:
            fh.write(repaired)
        _run([tool, "--dsf2text", copy, partial], writes=partial,
             declares=text_out, timeout=timeout)
    return True


def dump(dsf_path: str, text_out: str, tool: str, *,
         timeout: float | None = None) -> str:
    """``DSFTool --dsf2text`` into ``text_out``; returns it.

    ATOMIC (#560): DSFTool writes a ``.partial`` file BESIDE ``text_out``
    and that file is renamed onto it only after DSFTool exited 0 and wrote
    something.  DSFTool creates its output before it reads the DSF, so a
    crash left a 0-byte file under the final name — measured 2026-10-11:
    DSFTool 2.4.0-b1 dies with SIGSEGV on one stock Global Airports tile
    and every build of that tile found the empty dump.  A failed, killed or
    timed-out run now leaves NOTHING under ``text_out`` (an older good
    dump there is untouched), and two processes dumping one DSF each
    rename a complete file — the last one wins, both are whole.  The
    ``.partial`` name ends in neither ``.text`` nor ``.dsf``, so no reader
    globs it.  Raises :class:`DsfToolError` naming the real cause.

    A CRASH is retried once on a temp copy with a pool selected first
    (#568, :func:`_dump_pool_selected`): the text is the one DSFTool would
    have written for the DSF itself, every row and every property, and
    only its ``# file:`` comment names the copy.
    """
    if not tool or not os.path.isfile(tool):
        raise DsfToolError(f"DSFTool binary required, got {tool!r}")
    _sweep_stale_partials(text_out)
    started = time.time()
    partial = f"{text_out}.{os.getpid()}.{uuid.uuid4().hex[:8]}.partial"
    try:
        try:
            _run([tool, "--dsf2text", dsf_path, partial], writes=partial,
                 declares=text_out, timeout=timeout)
        except DsfToolError as error:
            if not (error.crashed and _dump_pool_selected(
                    dsf_path, partial, text_out, tool, timeout)):
                raise
        if not os.path.isfile(partial) or os.path.getsize(partial) == 0:
            raise DsfToolError(
                f"{tool} --dsf2text exited 0 but wrote no text for {dsf_path}")
        _land_dump(partial, text_out, started)
    finally:
        _remove_quietly(partial)
    return text_out
