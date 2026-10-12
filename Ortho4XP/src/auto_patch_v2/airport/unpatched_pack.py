"""THE PACK OF AN AIRPORT LEFT WITHOUT A PATCH goes back to its original.

Owner RULINGS 2026-10-12d (completes 12a, issue #564).  An earlier build
re-seated the pack's objects for the graded surface of that airport's
patch — MSL / AGL rows converted to on-ground, placements split into
bodies.  This build could not make the patch, the tile carries ungraded
terrain there, and the pack must be as authored again.

Nothing here is a second restore or a second writer.  What an airport
did to a pack DSF is one row of the record beside it
(``o4_placement_provenance.json`` -> ``dsfs[<dsf>].airports[<ICAO>]``,
``dsf_write.write_pack``); undoing it is one of two existing acts:

* the airport is the only one recorded for the DSF — the backup goes
  back over the DSF, the bodies its write minted go, the entry is
  dropped.  The UI restore's rule (``object_rebake.restore_detail``):
  only a file ``backup_state`` proves is OURS is overwritten;
  When the record carries an art omission the user accepted (#433) the
  bare copy would put back definitions X-Plane cannot load, so the DSF
  is written from the pristine dump with that omission and no airport's
  edits instead; the entry stays, naming the omission and no airport;
* other airports are recorded too (one pack DSF can serve two airports,
  #25) — the DSF is written again from the pristine dump with THEIR
  recorded edits and without this airport's (``write_pack(drop=)``), so
  their seating is kept whether or not they are written later; a
  recorded omission is passed through the same write.

A restore that cannot be proven writes nothing and says why.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import shutil

from ..model.placement import BACKUP_SUFFIX, PlacementPlan, Provenance
from . import backup_state as _bs
from . import dsf_write as _dw
from . import pack_art as _pa
from .file_hash import sha256_file

__all__ = ["NONE", "RESTORED", "RECOMPOSED", "UNPROVEN", "Outcome",
           "seated_airports", "restore_airport"]

#: the airport never re-seated this DSF (or the file is not ours): no-op
NONE = "none"
#: the DSF is the pristine file again
RESTORED = "restored"
#: the DSF was rebuilt without this airport, the others' seating kept
RECOMPOSED = "recomposed"
#: nothing was written; ``Outcome.reason`` says why
UNPROVEN = "unproven"


@_dc.dataclass(frozen=True)
class Outcome:
    """What :func:`restore_airport` did to one pack DSF."""

    state: str
    dsf_path: str
    #: the airports whose seating the DSF still carries
    kept: tuple[str, ...] = ()
    #: the split bodies removed from the pack
    bodies_removed: tuple[str, ...] = ()
    #: :data:`UNPROVEN` only — one sentence for the user
    reason: str = ""


def seated_airports(dsf_path: str) -> tuple[str, ...]:
    """The airports the record says re-seated this DSF, sorted.  An entry
    from before the per-airport map names its one airport at the record's
    top level, and only when that level describes THIS file."""
    record = _bs.read_record(dsf_path)
    base = os.path.basename(dsf_path)
    airports = _bs.dsf_entry(record, base).get("airports")
    if isinstance(airports, dict):
        return tuple(sorted(str(icao) for icao in airports))
    if record.get("dsf") == base and record.get("icao"):
        return (str(record["icao"]),)
    return ()


def restore_airport(pack_root: str, dsf_path: str, icao: str, tool: str, *,
                    allow_live_install: bool = False,
                    engine_version: str = "",
                    work_dir: str | None = None) -> Outcome:
    """Undo what ``icao``'s earlier build did to this pack DSF.

    ``tool`` (DSFTool) is run only when another airport's seating must be
    kept.  Refuses a pack under a live X-Plane install without
    ``allow_live_install``, exactly as ``write_pack`` does (§3.5)."""
    seated = seated_airports(dsf_path)
    if icao not in seated:
        return Outcome(NONE, dsf_path, seated)
    if _dw.live_install_roots(dsf_path) and not allow_live_install:
        raise PermissionError(
            f"REFUSING to restore inside a live X-Plane installation: "
            f"{dsf_path!r} (spec §3.5 — a lane writes a COPY of the pack)")
    name = os.path.basename(dsf_path)
    verdict = _bs.classify_dsf(dsf_path)
    State = _bs.State
    if verdict.state in (State.UNPROVEN, State.ORIGINAL_LOST):
        return Outcome(UNPROVEN, dsf_path, seated,
                       reason=_dw._stand_down_line(verdict))
    if verdict.state not in (State.OURS, State.PRISTINE):
        # REPLACED / LIVE_MISSING / NO_BACKUP: the installed file is the
        # user's own (or gone) — it carries nothing of ours to undo, and a
        # file we cannot prove is ours never loses bytes
        return Outcome(NONE, dsf_path, seated)
    kept = tuple(a for a in seated if a != icao)
    # THE ART THE USER ACCEPTED TO BUILD WITHOUT STAYS OUT (#433; master
    # ruling on 12d): "as authored" is the placements and their seating,
    # never definitions that are not installed — X-Plane refuses to load
    # a DSF that declares them.
    omit = _pa.recorded(
        _bs.dsf_entry(_bs.read_record(dsf_path), name),
        sha256_file(verdict.backup)) if verdict.backup else ()
    if not kept and not omit:
        if verdict.state is State.OURS:
            shutil.copy2(verdict.backup, dsf_path)
            _bs.invalidate_memo()
        removed = _dw.remove_cut_files(
            _dw.written_body_files(pack_root, dsf_path))
        _bs.drop_dsf_entry(dsf_path)
        return Outcome(RESTORED, dsf_path, (), removed)
    plan = PlacementPlan("", os.path.basename(os.path.normpath(pack_root)),
                         pack_root, dsf_path, dsf_path + BACKUP_SUFFIX,
                         Provenance("", engine_version, "", {}))
    try:
        result = _dw.write_pack(pack_root, plan, tool, drop=(icao,),
                                omit=omit,
                                allow_live_install=allow_live_install,
                                engine_version=engine_version,
                                work_dir=work_dir)
    except (_dw.BackupUnproven, OSError, RuntimeError, ValueError) as exc:
        return Outcome(UNPROVEN, dsf_path, seated, reason=(
            f"{name} could not be rebuilt without this airport's object "
            f"placements ({exc})"))
    return Outcome(RECOMPOSED if result.composed_airports else RESTORED,
                   dsf_path, tuple(result.composed_airports),
                   tuple(result.orphaned_bodies))
