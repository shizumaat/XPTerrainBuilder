"""THE PACK HEALTH CHECK in the object stage (issue #1978).

Owner (2026-11-09): known vendor defects that hurt the sim are checked
"when we process a package" and repaired — automatically (health, not
taste), always reported, the vendor original kept.  The classes and the
repair are ``auto_patch_v2.airport.pack_health``; the repair is applied
by every write of the pack DSF (``dsf_write.write_pack``), so a later
placement write never undoes it.

This step makes sure the write HAPPENS for a pack that needs it: right
after the pack's adjustments and "Optimise pack" steps, for every pack
the object stage is about to read, a tile DSF whose pristine dump has a
defect and whose live file does not already carry the repair is written
again (``pack_rewrite.rewrite_dsf``, everything else of ours as
recorded).  A measure-only or lane build only reports.  Every repair is
one build-log line; the pack row counts them
(``object_rebake.modified_packs``' ``repaired``).

Nothing here raises into the build.
"""
from __future__ import annotations

import os
import traceback

from . import pack_rewrite as _PR

__all__ = ["health_stage"]


def _check(pack_root: str, lat: int, lon: int, *, read_only: bool):
    """``(pack dump, found, current)`` for the pack's tile DSF — ``found``
    is the number of defects in its pristine dump, ``current`` whether the
    live file already carries their repair — or ``None`` when there is
    nothing to judge (``object_stage.pack_dump``)."""
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import pack_health as _ph
    from auto_patch_v2.airport.file_hash import sha256_file

    from .object_stage import pack_dump

    pd = pack_dump(pack_root, lat, lon, read_only=read_only)
    if pd is None:
        return None
    with open(pd.dump_path, encoding="utf-8", errors="surrogateescape") as fh:
        text = fh.read()
    polys = _ph.stacked_polygons.scan(text.splitlines())
    lights = _ph.objects.broken_objects(pack_root, text)
    found = polys.dropped + sum(len(f) for f in lights.values())
    current = False
    if found and os.path.isfile(pd.pristine) and pd.pristine != pd.dsf_path:
        entry = _bs.dsf_entry(_bs.read_record(pd.dsf_path),
                              os.path.basename(pd.dsf_path))
        current = (bool(_ph.recorded(entry, sha256_file(pd.pristine)))
                   and _bs.classify_dsf(pd.dsf_path).state is _bs.State.OURS)
    return pd, found, current


def _say_repaired(pd) -> None:
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import pack_health as _ph
    base = os.path.basename(pd.dsf_path)
    row = _bs.dsf_entry(_bs.read_record(pd.dsf_path), base).get(_ph.RECORD_KEY)
    for line in _ph.log_lines(pd.pack_name, base, row or {}):
        UI.vprint(0, line)
    UI.vprint(0, f"  [pack health] {pd.pack_name}: the original is kept as "
                 f"{base}.anchor_bak; Restore originals puts it back")


def health_stage(plan_, tile, *, writes: bool) -> str:
    """The health check of ONE airport's pack, ahead of its placement
    write.  Returns ``""`` (nothing found), ``"current"``, ``"found"``
    (reported, not written: a measure-only build), ``"repaired"`` or
    ``"failed"``.  Never raises."""
    import O4_UI_Utils as UI
    pack_root = getattr(plan_, "pack_root", "") or ""
    try:
        got = _check(pack_root, tile.lat, tile.lon, read_only=not writes)
    except Exception as exc:
        UI.vprint(1, f"  [pack health] check skipped ({exc})")
        UI.vprint(2, traceback.format_exc())
        return ""
    if got is None or not got[1]:
        return ""
    pd, found, current = got
    if current:
        UI.vprint(1, f"  [pack health] {pd.pack_name}: {found} vendor "
                     f"defect(s) found, already repaired")
        return "current"
    if not writes:
        UI.vprint(0, f"  [pack health] {pd.pack_name}: {found} vendor "
                     f"defect(s) found in "
                     f"{os.path.basename(pd.dsf_path)} — not repaired "
                     f"(this build does not write the pack)")
        return "found"
    try:
        _PR.rewrite_dsf(pack_root, pd.pack_name, pd.dsf_path)
    except Exception as exc:
        UI.vprint(0, f"  [pack health] {pd.pack_name}: {found} vendor "
                     f"defect(s) could not be repaired ({exc}); the pack is "
                     f"as it was")
        UI.vprint(2, traceback.format_exc())
        return "failed"
    _say_repaired(pd)
    return "repaired"
