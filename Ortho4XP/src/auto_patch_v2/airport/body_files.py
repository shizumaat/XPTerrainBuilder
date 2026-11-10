"""THE BODY FILES THIS WRITER MINTED IN A PACK — which ``__b<k>.obj``
split bodies the previous write of a DSF made (its placement record,
11m, per DSF §12a (2), per airport #25), and the ONE guarded remover
that unlinks them (a file without this writer's ``CUT_MARK`` is never
touched).

Read by the write half before it writes again (``airport/dsf_write``,
``placement_write``), and by the restores (``object_rebake``'s UI
restore #26, ``unpatched_pack``, ``torn_pack``, ``pack_journal``) —
apart from the writer, so a restore does not key the patch build's code
on it (#1901).  ``dsf_write`` re-exports the public names.
"""
from __future__ import annotations

import os
import typing as _t

from ..model.placement import CUT_MARK
from .backup_state import dsf_entry, read_record

__all__ = ["remove_cut_files", "written_body_files"]


def remove_cut_files(paths: _t.Iterable[str]) -> tuple[str, ...]:
    """Unlink the given body files — each confirmed to carry this writer's
    ``CUT_MARK`` first, so a corrupt or hand-edited record can never
    delete an authored object.  ONE implementation for the restore step
    (11m), the shared-DSF orphan removal (#25) and the UI restore (#26).
    Returns what went."""
    removed: list[str] = []
    for path in paths:
        try:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                if CUT_MARK not in fh.read(4096):
                    continue
            os.remove(path)
        except OSError:
            continue
        removed.append(path)
    return tuple(sorted(removed))


def _body_paths(pack_root: str, rows: _t.Any) -> tuple[str, ...]:
    """Record-relative body names -> absolute paths inside the pack (a
    name that escapes the pack is dropped)."""
    if not isinstance(rows, list):
        return ()
    out: list[str] = []
    root = os.path.abspath(pack_root)
    for rel in rows:
        if not isinstance(rel, str) or not rel:
            continue
        p = os.path.abspath(os.path.join(root, *rel.replace("\\", "/").split("/")))
        if p.startswith(root + os.sep):
            out.append(p)
    return tuple(out)


def written_body_files(pack_root: str, dsf_path: str,
                       icao: str = "") -> tuple[str, ...]:
    """The body files the PREVIOUS write of this DSF made, as absolute
    paths, from ``o4_placement_provenance.json`` beside it (11m).

    PER AIRPORT (#25).  One pack DSF can serve TWO airports (TNCM + TFFG
    on +18-064); each is written in turn, and the restore step before
    the second write must remove only the SECOND airport's previous
    bodies — the first's are still referenced by the DSF the second
    write composes.  With ``icao`` and an ``airports`` map in the entry,
    that airport's list (nothing when it has none); without ``icao``
    the entry's whole list (every airport's — the UI restore's frame).
    An entry from before the map holds ONE airport's list, which is the
    previous write's whatever its ICAO: it is returned either way, so a
    pack written up to this version cleans up exactly as it did.

    The restore step removes exactly these before writing again — a plan
    that cuts fewer bodies than the last one would otherwise leave the
    surplus ``__b<k>.obj`` in the pack forever.  A pack with no
    provenance, or provenance from before this key existed, names
    nothing and NOTHING is removed.

    PER DSF (§12a (2)).  The record lands in the 10°x10° ``Earth nav
    data/<bucket>/`` folder, which may hold SEVERAL of a pack's DSFs; the
    version-1 record held one DSF's ``body_files`` at the top level, so
    writing DSF B removed DSF A's bodies while A's live DSF still
    referenced them.  A version-1 record is honoured only when its
    ``dsf`` field names THIS file — otherwise it names nothing, which is
    11m's own rule (no record ⇒ remove nothing)."""
    entry = dsf_entry(read_record(dsf_path), os.path.basename(dsf_path))
    airports = entry.get("airports")
    if icao and isinstance(airports, dict):
        a = airports.get(icao)
        return _body_paths(pack_root, (a or {}).get("body_files") or [])
    return _body_paths(pack_root, entry.get("body_files") or [])
