"""A TORN PACK — a DSF naming split bodies that are not in the pack — is
put back on its original before anything else is written.

A pack whose live DSF names ``objects/<name>__b<k>_<hash>.obj`` bodies
that are gone does not load in X-Plane at all: every object of the pack
vanishes (PAKT 1.0.465: 156 of 161 bodies missing since a write on
2026-10-25 removed the previous bodies and then failed before its DSF
was moved into place; KLAX 1.0.464: 165 of 195).  The record beside the
DSF (``o4_placement_provenance.json``) says, per airport, which bodies
the live write names; an airport row with a missing body cannot be
re-applied either (``dsf_write._refuse_missing_bodies`` refuses it, and
with it every later write that composes the row — the 3D-tree upgrade
included).

:func:`repair` is the one rule, general to every pack:

* when the live DSF is this app's own rewrite (``backup_state`` row D4)
  and one of the bodies its record names is missing, the original —
  ``<dsf>.anchor_bak``, ``dsf_write``'s one backup — is copied back over
  it, atomically: the pack loads again, as installed;
* every airport row that names a missing body leaves the record, and
  that row's surviving bodies (``CUT_MARK``-checked) go with it, so the
  next write re-plans the airport from the original instead of
  re-applying a row whose art is gone.

A live DSF that IS the original (row D3) beside such a stale row only
loses the row.  Nothing happens to a pack whose bodies are all there.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import shutil
import typing as _t

from . import backup_state as _bs
from . import dsf_write as _dw

__all__ = ["Repaired", "missing_bodies", "repair"]


@_dc.dataclass(frozen=True)
class Repaired:
    """What :func:`repair` did to one DSF."""

    dsf_path: str
    #: the original was copied back over the live DSF
    restored_original: bool
    #: the airport rows dropped from the record
    airports: tuple[str, ...]
    #: pack-relative names of the bodies that were missing
    missing: tuple[str, ...]
    #: the surviving bodies of the dropped rows that were removed
    removed: tuple[str, ...]

    def line(self) -> str:
        """One sentence for the build log."""
        what = ("restored its original DSF and " if self.restored_original
                else "")
        return (f"{os.path.basename(self.dsf_path)} named {len(self.missing)} "
                f"object file(s) missing from the pack; {what}dropped the "
                f"seating of {', '.join(self.airports) or 'the last write'} "
                f"so it is placed again from the original")


def _rows(entry: _t.Mapping) -> dict[str, list[str]]:
    """``{airport: body names}`` the entry records; a pre-map entry is one
    row under ``""``."""
    airports = entry.get("airports")
    if isinstance(airports, dict):
        return {str(k): [b for b in (v or {}).get("body_files") or []
                         if isinstance(b, str)]
                for k, v in airports.items() if isinstance(v, dict)}
    names = [b for b in entry.get("body_files") or [] if isinstance(b, str)]
    return {"": names} if names else {}


def missing_bodies(pack_root: str, dsf_path: str) -> dict[str, list[str]]:
    """``{airport: [missing body names]}`` for every airport row of this
    DSF's record that names a body file the pack does not hold."""
    entry = _bs.dsf_entry(_bs.read_record(dsf_path), os.path.basename(dsf_path))
    out: dict[str, list[str]] = {}
    for icao, names in _rows(entry).items():
        gone = [n for n in names
                if not any(os.path.isfile(p)
                           for p in _dw._body_paths(pack_root, [n]))]
        if gone:
            out[icao] = gone
    return out


def repair(pack_root: str, dsf_path: str) -> Repaired | None:
    """Mend a torn pack (module doc); ``None`` when it is not torn."""
    if not os.path.isfile(dsf_path):
        return None
    torn = missing_bodies(pack_root, dsf_path)
    if not torn:
        return None
    verdict = _bs.classify_dsf(dsf_path)
    restored = False
    if verdict.state is _bs.State.OURS and verdict.backup \
            and os.path.isfile(verdict.backup):
        tmp = dsf_path + ".o4tmp"
        shutil.copyfile(verdict.backup, tmp)
        os.replace(tmp, dsf_path)
        restored = True
        _bs.invalidate_memo()
    elif verdict.state is not _bs.State.PRISTINE:
        return None          # not provably ours: never touch the user's file
    entry = _bs.dsf_entry(_bs.read_record(dsf_path), os.path.basename(dsf_path))
    rows = _rows(entry)
    kept = {k: v for k, v in rows.items() if k not in torn}
    still = {b for names in kept.values() for b in names}
    dropped = sorted({b for k in torn for b in rows[k]} - still)
    removed = _dw.remove_cut_files(_dw._body_paths(pack_root, dropped))
    fields: dict[str, _t.Any] = {"body_files": sorted(still)}
    if isinstance(entry.get("airports"), dict):
        fields["airports"] = {k: v for k, v in entry["airports"].items()
                              if k not in torn}
    _bs.update_dsf_entry(dsf_path, fields)
    missing = sorted({b for names in torn.values() for b in names})
    return Repaired(dsf_path, restored, tuple(sorted(k for k in torn if k)),
                    tuple(missing), removed)
