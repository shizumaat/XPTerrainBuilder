"""THE REWRITE AND THE UNDO of a user's choice for an airport pack that
every write re-applies: the X-Plane 12 3D trees (#1360, ``forest_stage``),
"Optimise pack" (#1707, ``optimise_stage``) and the hidden draped photos
(#1916, ``drape_stage``).

* :func:`rewrite_dsf` — the pack DSF written again from its pristine
  backup with everything of ours as recorded (every airport's placement
  edits, the accepted omission #433, the other recorded choice) and this
  choice's new value (``dsf_write.write_pack``'s ``forests=`` /
  ``optimise=``).
* :func:`undo_recorded` — every DSF of the pack whose record carries the
  choice gets its pristine file back byte for byte when nothing else of
  ours is in it (:func:`_others_recorded`), else is written again without
  it.
"""
from __future__ import annotations

import os
import shutil
import typing as _t

from .pack_choice import relative

__all__ = ["rewrite_dsf", "undo_recorded"]


def rewrite_dsf(pack_root: str, pack_name: str, dsf: str,
                **choice: _t.Any) -> str:
    """The pack DSF written with ``choice`` (``forests=``, ``optimise=`` or
    ``drapes=``)
    and everything else of ours as recorded; returns the backup path."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport import dsf_write as _dw
    from auto_patch_v2.airport import pack_art as _pa
    from auto_patch_v2.airport import pack_journal as _pj
    from auto_patch_v2.airport.file_hash import sha256_file
    from auto_patch_v2.model.placement import BACKUP_SUFFIX, PlacementPlan, Provenance

    from . import dsf_reader as _DSFR
    from .object_stage import _engine_version
    backup = dsf + BACKUP_SUFFIX
    omit = (_pa.recorded(_bs.dsf_entry(_bs.read_record(dsf),
                                       os.path.basename(dsf)),
                         sha256_file(backup))
            if os.path.isfile(backup) else ())
    plan = PlacementPlan("", pack_name, pack_root, dsf, backup,
                         Provenance("", _engine_version(), "", {}))
    _pj.snapshot(pack_root, dsf)          # a no-op outside a build (#598)
    _dw.write_pack(pack_root, plan, _DSFR._dsftool_path() or "DSFTool",
                   allow_live_install=True, engine_version=_engine_version(),
                   omit=omit, **choice)
    _DSFR.ensure_dsf_text_path(dsf, _dsf2.mod_cache_dir(
        FNAMES.airport_mod_cache_root(), pack_name))
    return backup


def _others_recorded(entry: _t.Mapping[str, _t.Any], record_key: str) -> bool:
    """Whether a DSF's record holds anything of ours besides its
    ``record_key`` choice: an airport's seating, an accepted omission, or
    the other recorded choice."""
    from auto_patch_v2.airport import pack_art as _pa
    from auto_patch_v2.airport import pack_drapes as _pd
    from auto_patch_v2.airport import pack_forests as _pf
    from auto_patch_v2.airport import pack_optimise as _po
    sha = entry.get("backup_sha256") or ""
    if entry.get("airports") or _pa.recorded(entry, sha):
        return True
    return any(m.recorded(entry, sha) for m in (_pf, _po, _pd)
               if m.RECORD_KEY != record_key)


def undo_recorded(pack_root: str, lat: int | None, lon: int | None,
                  record_key: str,
                  rewrite: _t.Callable[[str], _t.Any]) -> list[str]:
    """Take the ``record_key`` choice out of the pack's DSFs that carry it
    (only the tile's with ``lat``/``lon``); returns the files rewritten
    (pack-relative).  A DSF holding nothing else of ours gets its pristine
    file back byte for byte and its record entry dropped; one that does
    is handed to ``rewrite(dsf)`` (a write without the choice)."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import backup_state as _bs

    from . import object_rebake as _OR
    only = None
    if lat is not None and lon is not None:
        only = "%+03d%+04d.dsf" % (int(lat), int(lon))
    done: list[str] = []
    for dsf, entry in _OR.recorded_dsfs(pack_root, record_key):
        if only is not None and os.path.basename(dsf) != only:
            continue
        verdict = _bs.classify_dsf(dsf)
        if verdict.state is not _bs.State.OURS or not verdict.backup:
            continue                    # never a file we cannot prove ours
        if not _others_recorded(entry, record_key):
            shutil.copy2(verdict.backup, dsf)
            _bs.invalidate_memo()
            _bs.drop_dsf_entry(dsf)
            UI.vprint(0, f"  [pack] {os.path.basename(os.path.normpath(pack_root))}: "
                         f"{relative(pack_root, dsf)} is the original again")
        else:
            rewrite(dsf)
        done.append(relative(pack_root, dsf))
    return done
