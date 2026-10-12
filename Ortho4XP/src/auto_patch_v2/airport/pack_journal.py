"""THE PACK FILES A BUILD REWRITES, kept as they were until it completes.

Owner decision 2026-10-12 (#598): "A build stopped should restore any
modifications made to scenery packs."  The object stage re-seats a pack's
objects at the END of the mesh step; the masks and imagery steps follow,
and a build stopped anywhere in them leaves the tile's PREVIOUS scenery
active (RULINGS 2026-10-12h (3)) — over packs already seated for the
ground of the build that never finished.

The state to put back is the one from BEFORE THIS BUILD, which is not the
pristine pack: the previous completed build's seating is what matches the
scenery X-Plane still loads.  It cannot be recomposed — the stopped build
replaced the airport's recorded edits with its own and deleted the split
bodies the previous DSF names — so the stage copies each file aside
before its first write (:func:`snapshot`, called by the three writers:
``placement_write.apply_plan``, ``unpatched_pack.restore_airport``, the
engine's art-only write).  A stopped build, or the next build of a tile
whose last one was killed, puts the copies back (:func:`replay`); a
completed build throws them away (:func:`discard`).

Nothing here composes or encodes a DSF.  A file is overwritten only when
it is the bytes saved, or ``backup_state`` proves it is this app's own
write (the UI restore's rule); anything else is left and NAMED.

The journal lives under the tile's build directory:
``pack_journal_<tile>/journal.json`` plus the copies.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import shutil
import typing as _t

from . import backup_state as _bs
from . import dsf_write as _dw
from .file_hash import sha256_file

__all__ = ["RESTORED", "UNPROVEN", "Replayed", "path_for", "begin", "end",
           "snapshot", "pending", "replay", "discard"]

#: the pack's files are as they were before the build
RESTORED = "restored"
#: nothing was written over the DSF; ``Replayed.reason`` says why
UNPROVEN = "unproven"

_INDEX = "journal.json"
#: the journal directory of the object stage running in this process
_active: str | None = None


@_dc.dataclass(frozen=True)
class Replayed:
    """What :func:`replay` did about one pack DSF."""

    state: str
    pack_root: str
    dsf_path: str
    #: :data:`UNPROVEN` only — one sentence for the user
    reason: str = ""


def path_for(build_dir: str, tile_name: str) -> str:
    """The journal directory of one tile's build."""
    return os.path.join(build_dir, "pack_journal_" + tile_name)


def begin(build_dir: str, tile_name: str) -> str:
    """Open the journal for the object stage about to run.  Nothing is
    created until the first :func:`snapshot`."""
    global _active
    _active = path_for(build_dir, tile_name)
    return _active


def end() -> None:
    """The object stage is over: later writes (a user command) are not a
    build's and are not journalled."""
    global _active
    _active = None


def _read(journal: str) -> list:
    try:
        with open(os.path.join(journal, _INDEX), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return []
    entries = doc.get("entries") if isinstance(doc, dict) else None
    return [e for e in entries or [] if isinstance(e, dict)]


def _write(journal: str, entries: list) -> None:
    tmp = os.path.join(journal, _INDEX + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"entries": entries}, fh, indent=1, sort_keys=True)
    os.replace(tmp, os.path.join(journal, _INDEX))


def snapshot(pack_root: str, dsf_path: str,
             new_bodies: _t.Iterable[str] = ()) -> None:
    """Keep this pack DSF, its record and its split bodies as they are
    NOW — once per DSF per build, before the caller's first write.  The
    index names the copies only after they are whole.  A no-op outside a
    build's object stage.

    ``new_bodies`` are the body files the caller is about to write (every
    call adds its own): the record names them only once the DSF write has
    got that far, and a build killed before it must still remove them."""
    journal = _active
    if not journal or not os.path.isfile(dsf_path):
        return
    dsf_path = os.path.abspath(dsf_path)
    entries = _read(journal)
    new_bodies = [os.path.abspath(p) for p in new_bodies]
    for known in entries:
        if known.get("dsf") == dsf_path:
            if new_bodies:
                known["minted"] = sorted(set(known.get("minted") or [])
                                         | set(new_bodies))
                _write(journal, entries)
            return
    os.makedirs(journal, exist_ok=True)
    n = len(entries)
    entry = {"pack_root": os.path.abspath(pack_root), "dsf": dsf_path,
             "dsf_copy": f"{n}.dsf", "record_copy": None, "bodies": [],
             "minted": sorted(new_bodies)}
    shutil.copy2(dsf_path, os.path.join(journal, entry["dsf_copy"]))
    record = _bs.record_path_for(dsf_path)
    if os.path.isfile(record):
        entry["record_copy"] = f"{n}.record.json"
        shutil.copy2(record, os.path.join(journal, entry["record_copy"]))
    for k, body in enumerate(_dw.written_body_files(pack_root, dsf_path)):
        if os.path.isfile(body):
            shutil.copy2(body, os.path.join(journal, f"{n}.b{k}.obj"))
            entry["bodies"].append([os.path.abspath(body), f"{n}.b{k}.obj"])
    _write(journal, entries + [entry])


def pending(build_dir: str, tile_name: str) -> bool:
    """Whether a build of this tile rewrote a pack and did not complete."""
    return bool(_read(path_for(build_dir, tile_name)))


def discard(build_dir: str, tile_name: str) -> None:
    """The build completed: its pack writes stand."""
    shutil.rmtree(path_for(build_dir, tile_name), ignore_errors=True)


def _put_back(journal: str, entry: dict) -> str:
    """One DSF's files as saved; ``""`` or why the DSF was left."""
    dsf_path, pack_root = entry["dsf"], entry["pack_root"]
    saved = os.path.join(journal, str(entry.get("dsf_copy")))
    if not os.path.isfile(dsf_path):
        return ""                 # the pack's file is gone: nothing of ours
    if not os.path.isfile(saved):
        return "the copy kept before the build is missing."
    same = sha256_file(dsf_path) == sha256_file(saved)
    if not same:
        verdict = _bs.classify_dsf(dsf_path)
        if verdict.state not in (_bs.State.OURS, _bs.State.PRISTINE):
            return (f"{os.path.basename(dsf_path)} is no longer the file "
                    f"this build wrote.")
    minted = set(_dw.written_body_files(pack_root, dsf_path)) | {
        str(p) for p in entry.get("minted") or []}
    before = set()
    # the bodies the previous DSF names FIRST, then the DSF, then the
    # bodies only the stopped build's DSF named: no moment at which the
    # DSF in place names a missing file
    for body, copy in entry.get("bodies") or []:
        os.makedirs(os.path.dirname(body), exist_ok=True)
        shutil.copyfile(os.path.join(journal, copy), body)
        before.add(body)
    if not same:
        # a NEW mtime on purpose: the readers' text dump of this DSF is
        # keyed on it and was refreshed for the stopped build's file
        shutil.copyfile(saved, dsf_path + ".o4tmp")
        os.replace(dsf_path + ".o4tmp", dsf_path)
    _dw.remove_cut_files(sorted(minted - before))
    record = None
    if entry.get("record_copy"):
        with open(os.path.join(journal, entry["record_copy"]), "rb") as fh:
            record = fh.read()
    _bs.restore_record(dsf_path, record)
    return ""


def replay(build_dir: str, tile_name: str, *,
           allow_live_install: bool = False) -> tuple[Replayed, ...]:
    """Put every journalled pack file back and drop the journal.  Refuses
    a pack under a live X-Plane install without ``allow_live_install``,
    as every pack writer does (§3.5).  Never raises for one DSF: a file
    that cannot be put back is reported :data:`UNPROVEN`."""
    journal = path_for(build_dir, tile_name)
    out = []
    for entry in _read(journal):
        dsf_path = str(entry.get("dsf") or "")
        pack_root = str(entry.get("pack_root") or "")
        if _dw.live_install_roots(dsf_path) and not allow_live_install:
            raise PermissionError(
                f"REFUSING to restore inside a live X-Plane installation: "
                f"{dsf_path!r} (spec §3.5 — a lane writes a COPY of the pack)")
        try:
            reason = _put_back(journal, entry)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            reason = f"{exc}."
        out.append(Replayed(UNPROVEN if reason else RESTORED, pack_root,
                            dsf_path, reason))
    _bs.invalidate_memo()
    discard(build_dir, tile_name)
    return tuple(out)
