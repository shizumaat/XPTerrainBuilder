"""THE SIBLING PACKS' DECK RIDERS in the object stage (issue #1252;
``auto_patch_v2.airport.sibling_riders``).

WHERE.  Inside ``object_stage._place_objects``, for the airport pack's own
plan only (a companion's plan, ``ICAO~k``, re-seats no deck a sibling
stands on here): the frames are the plan's, read right after it is built.
:func:`plans` is the measurement (a lane build stops there and prints it);
:func:`write` runs after the airport pack itself was written, and never
when it was not — a sibling moved with a garage that stayed put is torn
geometry.

A pack this airport's earlier build wrote and whose rows are all as
authored now is written again with none, which puts its pristine rows
back.

Nothing here raises into the build: a failed pack is one log line and the
next pack goes on.
"""
from __future__ import annotations

import os
import traceback
import typing as _t

__all__ = ["plans", "write"]


def _say(msg: str, level: int = 1) -> None:
    import O4_UI_Utils as UI
    UI.vprint(level, msg)


def plans(plan: _t.Any, dump: _t.Any, surface: _t.Callable, tile: _t.Any,
          contact_m: float) -> list:
    """``[sibling PlacementPlan]`` to write for the airport ``plan``: every
    sibling with a deck rider or a free row inside the airport
    (``sibling_riders``), and every one this airport wrote before."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import frame_riders as _dr
    from auto_patch_v2.airport import sibling_riders as _sr
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    from auto_patch_v2.airport.unpatched_pack import seated_airports

    from . import dsf_reader as _DSFR
    if contact_m <= 0.0:
        return []
    out = []
    try:
        roots = _sr.candidates(plan.pack_root, tile.lat, tile.lon)
        frames = (_dr.frame_moves(dump, plan.pack_root, plan.splits,
                                  plan.msl_seats, plan.conversions, surface)
                  if roots else [])
        region = _sr.airport_region(plan.pack_root, plan.icao) if roots else None
        over = (_dr.over_objects(dump, plan.pack_root)
                if region is not None else None)
    except Exception as exc:
        _say(f"  [v2 placement] {plan.icao}: sibling packs not read ({exc})")
        _say(traceback.format_exc(), 2)
        return []
    for root in roots:
        name = os.path.basename(os.path.normpath(root))
        try:
            dsf_path = _dsf.dsf_path_in_pack(root, tile.lat, tile.lon)
            before = plan.icao in seated_airports(dsf_path)
            if not frames and region is None and not before:
                continue
            cache = _dsf.mod_cache_dir(FNAMES.airport_mod_cache_root(), name)
            text = _DSFR.ensure_dsf_text_path(pristine_dsf_path(dsf_path), cache)
            if not text:
                _say(f"  [v2 placement] {plan.icao}: sibling {name}: no DSF "
                     "text dump; skipped")
                continue
            sdump = _dsf.read_dump(text)
            sp = _sr.sibling_plan(plan, frames, root, sdump, dsf_path, contact_m,
                                  region, over)
            if sp.msl_seats or sp.conversions or before:
                out.append(sp)
                _say(f"  [v2 placement] {plan.icao}: sibling {name}: "
                     f"{len(sp.msl_seats)} row(s) on the airport's re-seated "
                     f"decks moved with them"
                     + (_moves(sp, sdump) if sp.msl_seats else "")
                     + f"; {len(sp.conversions)} free row(s) inside the "
                       f"airport seated on the new ground")
        except Exception as exc:
            _say(f"  [v2 placement] {plan.icao}: sibling {name} failed ({exc})")
            _say(traceback.format_exc(), 2)
    return out


def _moves(sp: _t.Any, dump: _t.Any) -> str:
    rows = dump.placements
    d = sorted(m.elevation - float(rows[m.index].elevation) for m in sp.msl_seats)
    return f" (by {d[0]:+.2f} .. {d[-1]:+.2f} m, median {d[len(d) // 2]:+.2f} m)"


def write(siblings: _t.Sequence, patch_dir: str, tool: str, *,
          engine_version: str = "", law_digest: str = "") -> int:
    """Write every sibling plan through the airport pack's own write
    (``placement_write.apply_plan``); the number written."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import placement_write as _pw
    from auto_patch_v2.airport import sibling_riders as _sr
    from auto_patch_v2.airport.backup_state import BackupUnproven

    from . import dsf_reader as _DSFR
    done = 0
    for k, sp in enumerate(siblings, start=1):
        cache = _dsf.mod_cache_dir(FNAMES.airport_mod_cache_root(), sp.pack_name)
        try:
            res = _pw.apply_plan(
                sp, (), tool, patch_dir=patch_dir, allow_live_install=True,
                refresh_dump=lambda p, _c=cache: _DSFR.ensure_dsf_text_path(p, _c),
                engine_version=engine_version, law_digest=law_digest,
                plan_key=_sr.RIDER_KEY.format(icao=sp.icao, k=k))
        except BackupUnproven as exc:
            _say(f'  [v2 placement] PACK NOT TOUCHED: "{sp.pack_name}" — {exc}', 0)
            continue
        except Exception as exc:
            _say(f"  [v2 placement] {sp.icao}: sibling {sp.pack_name} not "
                 f"written ({exc})", 0)
            _say(traceback.format_exc(), 2)
            continue
        done += 1
        if res.dsf is not None:
            for note in res.dsf.notes:
                _say(f'  [v2 placement] PACK UPDATED: "{sp.pack_name}" — {note}', 0)
    return done
