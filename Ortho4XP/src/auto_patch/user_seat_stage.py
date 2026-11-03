"""HAND-SET OBJECT SEATS IN THE OBJECT STAGE (issue #1703).

The seats a user gave pack objects in the patch editor
(``auto_patch_v2.airport.user_seats``, beside the patch) are a layer of
the pack DSF's write, recorded in its provenance like the 3D forest
upgrade: ``dsf_write.write_pack(seats=)``.

TWO WRITERS.

* A build that places the airport (its auto patch is in the mesh): the
  placement write carries :func:`file_seats` (``object_stage``).
* A build that uses the airport's EDITED patch (RULINGS 2026-10-15d (5):
  the object stage does not run, objects keep their last seat).  Owner on
  #1703, 2026-11-03: "yes, apply only the objects you set by hand" —
  :func:`seat_stage` writes the pack DSF with every recorded edit as it
  is (each airport's last placement, the omission and the forest upgrade
  the user accepted) and the hand-set seats over them: no restore, no
  cut, no split, no other row re-seated.  Nothing is written when the DSF
  already carries exactly these seats, so a pack with none is never
  touched.

Nothing here raises into the build: a failed write is one log line.
"""
from __future__ import annotations

import os
import traceback
import typing as _t

__all__ = ["file_seats", "say_seated", "seat_stage"]


def file_seats(patch_dir: str, icao: str, plan_key: str = ""
               ) -> dict[str, dict] | None:
    """``{ICAO: {row: UserSeat}}`` from the seats file for
    ``write_pack(seats=)`` (``{ICAO: {}}`` with none: an Automatic clears
    the DSF's); ``None`` — keep what the DSF records — for a companion
    pack's plan (``ICAO~k``: the editor seats the airport's own pack) or
    an unreadable file."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import user_seats as _us
    icao = str(icao).upper()
    if plan_key and plan_key.upper() != icao:
        return None
    try:
        return {icao: _us.read(patch_dir, icao)}
    except (OSError, ValueError) as exc:
        UI.vprint(0, f"  [v2 placement] {icao}: hand-set object elevations "
                     f"unreadable ({exc}); the pack keeps the ones it has")
        return None


def say_seated(icao: str, result: _t.Any) -> None:
    """The log line of a write that placed hand-set seats."""
    import O4_UI_Utils as UI
    n = len(getattr(result, "hand_seated", ()) or ())
    if n:
        UI.vprint(1, f"  [v2 placement] {icao}: {n} object(s) at the elevation "
                     f"set by hand")


def seat_stage(source: _t.Any, tile: _t.Any, patch_dir: str, *,
               writes: bool) -> bool:
    """The edited-patch build's write of ``source``'s (a rebake plan or
    screen: ``icao``, ``pack_root``) hand-set seats; ``True`` when the
    pack DSF was written.  Only when a manual patch covers the airport —
    every other reason its auto patch is not in the mesh places nothing."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import user_seats as _us
    from auto_patch_v2.airport.file_hash import sha256_file
    from auto_patch_v2.model.placement import BACKUP_SUFFIX

    from .object_stage import pack_dump
    from .selection import manual_patch_files_for
    icao = str(source.icao).upper()
    if not manual_patch_files_for(patch_dir, icao):
        return False
    seats = file_seats(patch_dir, icao)
    if seats is None:
        return False
    pd = pack_dump(source.pack_root, tile.lat, tile.lon, read_only=not writes)
    if pd is None:
        return False
    backup = pd.dsf_path + BACKUP_SUFFIX
    sha = sha256_file(backup) if os.path.isfile(backup) else ""
    entry = _bs.dsf_entry(_bs.read_record(pd.dsf_path), os.path.basename(pd.dsf_path))
    if _us.recorded(entry, sha).get(icao, {}) == seats[icao]:
        return False
    if not writes:
        UI.vprint(1, f"  [v2 placement] {icao}: MEASURE ONLY — "
                     f"{len(seats[icao])} hand-set object elevation(s); nothing written")
        return False
    try:
        res = _write(source.pack_root, pd, entry, sha, seats)
    except Exception as exc:
        UI.vprint(0, f"  [v2 placement] {icao}: the hand-set object elevations "
                     f"could not be written ({exc}); the pack is as it was")
        UI.vprint(2, traceback.format_exc())
        return False
    for note in res.notes:
        UI.vprint(0, f'  [v2 placement] PACK UPDATED: "{pd.pack_name}" — {note}')
    UI.vprint(0, f"  [v2 placement] {icao}: your edited patch is used — "
                 f"{len(res.hand_seated)} object(s) placed at the elevation set by "
                 f"hand, every other object as it was")
    return True


def _write(pack_root: str, pd: _t.Any, entry: _t.Mapping, sha: str,
           seats: _t.Mapping) -> _t.Any:
    """The pack DSF with every recorded edit and ``seats`` (``write_pack``
    with an ICAO-less plan: each airport's recorded edits re-applied, none
    re-recorded); the dump cache refreshed as the object stage does."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import dsf as _dsf2
    from auto_patch_v2.airport import dsf_write as _dw
    from auto_patch_v2.airport import pack_art as _pa
    from auto_patch_v2.airport import pack_journal as _pj
    from auto_patch_v2.model.placement import BACKUP_SUFFIX, PlacementPlan, Provenance

    from . import dsf_reader as _DSFR
    from .object_stage import _engine_version
    plan = PlacementPlan("", pd.pack_name, pack_root, pd.dsf_path,
                         pd.dsf_path + BACKUP_SUFFIX,
                         Provenance("", _engine_version(), "", {}))
    _pj.snapshot(pack_root, pd.dsf_path)          # a no-op outside a build (#598)
    res = _dw.write_pack(pack_root, plan, _DSFR._dsftool_path() or "DSFTool",
                         allow_live_install=True, engine_version=_engine_version(),
                         omit=_pa.recorded(entry, sha) if sha else (), seats=seats)
    _DSFR.ensure_dsf_text_path(pd.dsf_path, _dsf2.mod_cache_dir(
        FNAMES.airport_mod_cache_root(), pd.pack_name))
    return res
