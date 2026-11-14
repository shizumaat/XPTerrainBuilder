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

A recorded 3D forest upgrade (#1360) or "Optimise pack" recipe (#1707)
is the user's choice, not the airport's seating: like an omission it
keeps the DSF from the bare copy, and the write re-applies it.

GUEST ROWS BELONG TO THE TILE THAT WROTE THEM (#1884 round 2 B1).  A
tile's build writes the bodies of its placements that stand on another
tile of the pack as rows of THAT tile's DSF, recorded there under
``LOWS@+47+012`` (``dsf.guest_key``).  That key is another airport row
of the neighbour's DSF: restoring the neighbour's own ``LOWS`` keeps it
(the neighbour's build being left without a patch takes nothing the home
tile placed); restoring ``LOWS`` on the HOME tile takes ``LOWS@<home>``
out of every other DSF of the pack in the same transaction, so a
placement is never drawn by both.  A guest row a write cannot re-apply
(``dsf_write.WriteResult.stale_guests``) takes its home DSF back to the
original for that airport (:func:`restore_stale_guests`): rigid as
authored, never missing.

Every entry here holds the pack's write lock (``pack_lock``).

A restore that cannot be proven writes nothing and says why.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import shutil
import typing as _t

from ..model.placement import BACKUP_SUFFIX, PlacementPlan, Provenance
from . import backup_state as _bs
from . import dsf as _dsf
from . import dsf_write as _dw
from . import pack_art as _pa
from . import pack_forests as _pf
from . import pack_journal as _pj
from . import pack_lock as _lock
from . import tile_route as _route
from . import user_seats as _us
from . import pack_optimise as _po
from .file_hash import sha256_file

__all__ = ["NONE", "RESTORED", "RECOMPOSED", "UNPROVEN", "Outcome",
           "seated_airports", "restore_airport", "restore_stale_guests"]

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
    #: #1884 round 2 B1: the other DSFs of the pack that carried this
    #: tile's guest rows of the airport, each taken out (module doc)
    neighbours: tuple["Outcome", ...] = ()


def seated_airports(dsf_path: str) -> tuple[str, ...]:
    """The record keys that re-seated this DSF, sorted: airports, and
    another tile's GUEST rows by their own key (``LOWS@+47+012``, module
    doc — never folded into ``LOWS``).  An entry from before the
    per-airport map names its one airport at the record's top level, and
    only when that level describes THIS file."""
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
    """Undo what ``icao``'s earlier build did to this pack DSF, and take
    this tile's guest rows of ``icao`` out of every other DSF of the pack
    (module doc), under the pack's write lock.

    ``tool`` (DSFTool) is run only when another airport's seating must be
    kept.  Refuses a pack under a live X-Plane install without
    ``allow_live_install``, exactly as ``write_pack`` does (§3.5)."""
    with _lock.hold(pack_root, allow_live_install=allow_live_install):
        return _restore_with_guests(
            pack_root, dsf_path, icao, tool,
            allow_live_install=allow_live_install,
            engine_version=engine_version, work_dir=work_dir)


def restore_stale_guests(pack_root: str, keys: _t.Sequence[str], tool: str,
                         *, allow_live_install: bool = False,
                         engine_version: str = "") -> list[Outcome]:
    """Each guest key a write could not re-apply (``LOWS@+47+012``) takes
    its HOME DSF back to the original for its airport (module doc), said
    at verbosity 0.  Called by ``dsf_write.write_pack`` inside the write
    that dropped them, under the lock its caller holds."""
    out = []
    for key in keys:
        icao = _dsf.owner_of(key)
        home = _route.tile_of_key(key)
        if home is None or icao == key:
            continue
        home_dsf = _dsf.dsf_path_in_pack(pack_root, home[0], home[1])
        if not os.path.isfile(home_dsf):
            continue
        got = _restore_with_guests(pack_root, home_dsf, icao, tool,
                                   allow_live_install=allow_live_install,
                                   engine_version=engine_version)
        out.append(got)
        _say(f"  [v2 placement] {icao}: its rows written by the "
             f"{_dsf.on_tile('', home)[1:]} build in a neighbour DSF could "
             f"not be re-applied; {os.path.basename(home_dsf)} "
             + (f"could not be put back either ({got.reason})"
                if got.state == UNPROVEN else
                "is back to its original for this airport (its objects as "
                "authored)"))
    return out


def _say(text: str) -> None:
    """One verbosity-0 line (the engine's log; nothing without it)."""
    try:
        import O4_UI_Utils as _ui
    except ImportError:
        return
    _ui.vprint(0, text)


def _restore_with_guests(pack_root: str, dsf_path: str, icao: str,
                         tool: str, **kw: _t.Any) -> Outcome:
    """:func:`restore_airport`'s work, unlocked: the neighbours' guest
    rows of ``icao`` from this tile go FIRST (no moment at which both
    tiles draw a placement), then this DSF, in one transaction."""
    tile = _route.tile_of_dsf(dsf_path)
    key = _dsf.guest_key(icao, tile) if tile is not None and \
        _dsf.owner_of(icao) == icao else ""
    others = [p for p in (_route.guest_dsfs(pack_root, key) if key else [])
              if os.path.abspath(p) != os.path.abspath(dsf_path)]
    if not others:
        return _restore_one(pack_root, dsf_path, icao, tool, **kw)
    with _pj.transaction(pack_root, dsf_path):
        for other in others:
            _pj.snapshot(pack_root, other)
        neighbours = tuple(_restore_one(pack_root, other, key, tool, **kw)
                           for other in others)
        own = _restore_one(pack_root, dsf_path, icao, tool, **kw)
    return _dc.replace(own, neighbours=neighbours)


def _restore_one(pack_root: str, dsf_path: str, icao: str, tool: str, *,
                 allow_live_install: bool = False,
                 engine_version: str = "",
                 work_dir: str | None = None) -> Outcome:
    """One DSF without ``icao``'s rows (an airport or a guest key)."""
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
    # #598: the pack as it is NOW, kept until this build completes
    _pj.snapshot(pack_root, dsf_path)
    # THE ART THE USER ACCEPTED TO BUILD WITHOUT STAYS OUT (#433; master
    # ruling on 12d): "as authored" is the placements and their seating,
    # never definitions that are not installed — X-Plane refuses to load
    # a DSF that declares them.
    entry = _bs.dsf_entry(_bs.read_record(dsf_path), name)
    pristine_sha = sha256_file(verdict.backup) if verdict.backup else ""
    omit = (_pa.recorded(entry, pristine_sha, pack_root)
            if verdict.backup else ())
    # ... and so does the 3D forest upgrade the user accepted (#1360): the
    # write below re-applies it from the record
    forests = _pf.recorded(entry, pristine_sha) if verdict.backup else {}
    # ... and another airport's hand-set object seats (#1703)
    hand = (_us.merged(_us.recorded(entry, pristine_sha), None, drop=(icao,))
            if verdict.backup else {})
    optimise = _po.recorded(entry, pristine_sha) if verdict.backup else {}
    if not kept and not omit and not forests and not hand and not optimise:
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
