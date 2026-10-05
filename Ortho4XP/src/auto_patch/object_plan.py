"""THE OBJECT PLAN BESIDE THE PATCH — the tile build's half of "the rebake
plan leaves the patch build" (owner RULINGS 2026-10-04x (1), issue #362).

The v2 patch build no longer computes ``o4_v2_rebake_<ICAO>.json``: it
writes a SCREEN SIDECAR (``auto_patch_v2.airport.rebake_screen``) and the
post-mesh object stage builds the plan from that and the partition the
patch build cached.  This module is the three things the tile build does
with the pair, in ``Patches/<tile>/``:

* :func:`place` — put the sidecar (or, from a build that kept no partition
  cache, the plan itself) beside the patch;
* :func:`from_screen` — the plan for the object stage: built once, written
  beside the patch, read back on later runs, NEVER served stale;
* :func:`unservable` — the freshness gate's question: can the plan still
  be built?  A cold partition sends the airport back through its patch
  build; the object stage never re-partitions.

``engine_v2.rebake_after_mesh`` and ``driver._auto_patch_is_current`` are
the only callers.
"""
from __future__ import annotations

import os
import re
import time

__all__ = ["SCREEN_NAME_RE", "place", "unservable", "from_screen"]

#: The sidecar's own file name in the patch directory
#: (``rebake_screen.SCREEN_FILENAME``).  ``engine_v2._PLAN_NAME_RE`` does
#: not match it: a sidecar is a plan NOT YET BUILT, never a plan.
SCREEN_NAME_RE = re.compile(r"^o4_v2_rebake_[A-Za-z0-9]{2,8}\.screen\.json$")


def place(task: dict, src_plan, icao: str, src_screen=None) -> str | None:
    """Copy what the pipeline wrote for the object stage beside the patch
    (``Patches/<tile>/``): the SCREEN SIDECAR, or — from a build that kept
    no partition cache — the plan itself.  Returns the path placed.

    ONE OF THE TWO STANDS.  A plan beside a sidecar is, by this function,
    the plan OF that sidecar: placing a new sidecar removes the plan an
    earlier build's object stage made, and placing an inline plan removes
    an earlier build's sidecar."""
    import shutil
    screen = src_screen is not None and os.path.isfile(str(src_screen))
    if not screen and (src_plan is None or not os.path.isfile(str(src_plan))):
        return None
    from auto_patch_v2.airport.rebake_screen import SCREEN_FILENAME
    from auto_patch_v2.model.rebake import PLAN_FILENAME
    patch_dir = os.path.dirname(task["auto_patch_file"])
    plan_dest = os.path.join(patch_dir, PLAN_FILENAME.format(icao=icao))
    screen_dest = os.path.join(patch_dir, SCREEN_FILENAME.format(icao=icao))
    src, dest, gone = ((src_screen, screen_dest, plan_dest) if screen
                       else (src_plan, plan_dest, screen_dest))
    shutil.copyfile(str(src), dest + ".tmp")
    os.replace(dest + ".tmp", dest)
    if os.path.isfile(gone):
        os.remove(gone)
    return dest


def unservable(patch_dir: str, icao: str) -> str | None:
    """Why the object stage could NEVER build ``icao``'s plan from what
    stands beside its patch, or ``None``.

    THE COLD-PARTITION RULING (lane ``rebake362``): the plan is built
    after the mesh from the partition the PATCH build cached.  When that
    cache file is gone and no plan was built yet, the object stage does
    not re-partition (minutes of pack reading inside the tile's object
    step, against a DEM the post-mesh hook does not hold): the patch is
    NOT CURRENT, so its build runs again, re-reads the pack where that
    cost is named, and writes a fresh sidecar."""
    from auto_patch_v2.airport import rebake_screen as _rs
    from auto_patch_v2.model.rebake import PLAN_FILENAME
    screen = os.path.join(patch_dir, _rs.SCREEN_FILENAME.format(icao=icao))
    if not os.path.isfile(screen) or os.path.isfile(
            os.path.join(patch_dir, PLAN_FILENAME.format(icao=icao))):
        return None
    return _rs.unservable(screen)


def from_screen(screen, plan_path: str, patch_dir: str, law, UI):
    """THE REBAKE PLAN for the object stage, from the patch build's
    ``screen`` record and the partition it cached.  Returns the plan AS
    READ BACK from the JSON at ``plan_path`` — the object the placement
    path has always been handed — or ``None`` after saying why (the
    airport's placement is skipped).

    NEVER SERVED STALE: the record is held against the patch in this
    patch dir, the law and the code on EVERY call, whether or not the plan
    is already built.  A plan standing beside its sidecar was built from
    it (:func:`place`) and is read, not rebuilt."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import rebake_screen as _rs
    from auto_patch_v2.model.rebake import RebakePlan
    icao = screen.icao
    why = _rs.stale_reason(screen, law, os.path.join(patch_dir, icao + "_auto.patch.osm"))
    if why:
        UI.vprint(0, f"  [v2 rebake] {icao}: placement SKIPPED — the object plan's "
                     f"screen record is STALE ({why}); rebuild the airport's patch")
        return None
    if os.path.isfile(plan_path):
        with open(plan_path) as fh:
            return RebakePlan.from_json(fh.read())
    UI.vprint(1, f"  [v2 rebake] {icao}: building the object plan from the "
                 f"cached partition ({os.path.basename(screen.partition_path)})")
    # the extension is KEPT only under this run's own mod-cache root: a
    # patch dir carried over from another tree names another tree's cache
    root = FNAMES.airport_mod_cache_root()
    keep = bool(root) and os.path.abspath(screen.partition_path).startswith(
        os.path.abspath(root).rstrip(os.sep) + os.sep)
    t0 = time.time()
    try:
        text = _rs.build_plan(screen, law, keep_extension=keep).to_json()
    except _rs.StaleScreen as exc:
        UI.vprint(0, f"  [v2 rebake] {icao}: placement SKIPPED — the object "
                     f"plan cannot be built ({exc}); rebuild the airport's patch")
        return None
    with open(plan_path + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(plan_path + ".tmp", plan_path)
    plan_ = RebakePlan.from_json(text)
    UI.vprint(1, "  [v2 rebake] " + _rs.plan_line(icao, plan_, time.time() - t0)
              + f"  -> {plan_path}")
    return plan_
