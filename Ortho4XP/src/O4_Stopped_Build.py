"""What a tile is left with when its build is STOPPED, in one place.

Owner RULINGS 2026-10-12h (3) and decision 2026-10-12 (#598): a stopped
build activates nothing — the scenery built before stays, loadable and
unchanged — and puts back every scenery-pack file it rewrote.  A Stop is
a cancel, never a failure: the tile's row says what it is left with
(``TileState.detail``), no failure is named.

The engine session, the parallel orchestrator and the imagery step all
end a stopped tile through :func:`settle`; a completed build ends through
:func:`complete`.  Both are idempotent and never raise.
"""

from __future__ import annotations

import os

import O4_File_Names as FNAMES

__all__ = ["PREVIOUS_ACTIVE", "NO_SCENERY", "scenery_file", "settle",
           "complete"]

#: the row's second line for a stopped tile (both apps show it verbatim)
PREVIOUS_ACTIVE = "Stopped — the previous scenery is still active."
NO_SCENERY = "Stopped — this tile has no scenery yet."


def scenery_file(build_dir: str, lat: int, lon: int) -> str:
    """The file X-Plane reads for this tile."""
    return os.path.join(build_dir, "Earth nav data",
                        FNAMES.long_latlon(lat, lon) + ".dsf")


def settle(build_dir: str, lat: int, lon: int) -> str:
    """End a stopped build of this tile: put the scenery packs it rewrote
    back as they were, and return the sentence for its row — what the
    tile is left with, then one sentence per pack that could not be put
    back."""
    unproven: list = []
    try:
        from auto_patch import engine_v2
        unproven = engine_v2.restore_stopped_build(build_dir, lat, lon)
    except Exception as exc:                       # the row is still owed
        unproven = [f"The scenery packs changed by this build could not be "
                    f"checked ({exc})."]
    try:
        active = os.path.isfile(scenery_file(build_dir, lat, lon))
    except (TypeError, ValueError):
        active = False
    return " ".join([PREVIOUS_ACTIVE if active else NO_SCENERY] + unproven)


def complete(build_dir: str, lat: int, lon: int) -> None:
    """The build completed: the pack files it rewrote stand."""
    try:
        from auto_patch import engine_v2
        engine_v2.discard_pack_journal(build_dir, lat, lon)
    except Exception:
        pass
