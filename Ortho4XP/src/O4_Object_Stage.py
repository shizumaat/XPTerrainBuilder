"""THE OBJECT STAGE AS A STEP OF ITS OWN (#1699 phase 1).

The object stage fits the custom airport packs' objects to the ground the
mesh was built on: it reads the tile's rebake plans beside the patches
(``Patches/<tile>/o4_v2_rebake_<ICAO>.json``) and the mesh on disk, and
rewrites each pack's tile DSF in place — the ``.anchor_bak`` backups, the
three-way hash check and the no-stacking re-apply are the stage's own
(``auto_patch.object_stage.rebake_after_mesh``).  It reads nothing the
mesh step holds in memory, so it runs the same wherever the mesh came
from:

* at the end of the mesh step (``O4_Mesh_Utils.build_mesh`` /
  ``sort_mesh``) — a normal tile build, unchanged;
* on its own, over a mesh a tile bundle laid down (``tile_bundle.
  importer``): the bundle carries the plan, never the changed pack, and
  the user's app applies the plan to its own copy of the pack.

Never raises, and never fails SILENTLY (#2186): an airport whose objects
the stage did not fit — or the whole stage, when it failed — is a
DEGRADED row beside the tile (``O4_Unpatched_Airports.record_degraded``,
source :data:`SOURCE`, code ``pack_objects_not_fitted``), restated whole on
every run, which the tile's final ``BuildDone`` names as a warning in both
apps; and a reused mesh step runs the stage again over a tile whose last
stage did not finish (``O4_Step_Reuse.object_stage_stale``,
:func:`failed_last_run`).
"""
from __future__ import annotations

import O4_UI_Utils as UI

__all__ = ["run", "SOURCE", "failed_last_run"]

#: The ``record_degraded`` source this stage restates.
SOURCE = "object-stage"


def run(tile, beside: bool = False) -> dict:
    """The object stage for ``tile`` against the mesh in its build
    directory: ``rebake_after_mesh``'s counts, ``{}`` when it failed.
    What it did not fit is published as the tile's warnings (see the
    module docstring).  ``beside``: run on a thread of its own beside
    the tile's later steps (``O4_Object_Stage_Beside``), whose file
    witness then records this thread's opens only.  Lazy import: the
    long-running GUI caches ``auto_patch`` modules."""
    failed: list = []
    counts: dict = {}
    try:
        if beside:
            from auto_patch_v2.airport import file_witness
            file_witness.confine_to_thread()
        from auto_patch import object_stage
        counts = object_stage.rebake_after_mesh(tile, failed=failed)
    except Exception as exception:
        UI.vprint(1, "auto_patch post-mesh object re-anchor failed:",
                  exception)
        failed.append({"code": "pack_objects_not_fitted",
                       "detail": "%s" % (exception,)})
    _publish(tile, failed)
    return counts


def _publish(tile, failed: list) -> None:
    """Restate the stage's rows (an empty list clears an earlier run's)
    and say each one in the log.  Never fatal."""
    try:
        import O4_Unpatched_Airports as UNPATCHED
        UNPATCHED.record_degraded(tile, SOURCE, failed)
    except Exception as exception:                   # pragma: no cover
        UI.vprint(1, "   Object stage: its outcome could not be recorded:",
                  exception)
    for row in failed:
        UI.lvprint(0, "   Object stage: objects of %s NOT fitted to the "
                   "mesh (%s); the pack is left as it was."
                   % (row.get("airport") or "the tile's airports",
                      row.get("detail") or "no detail"))


def failed_last_run(tile) -> str | None:
    """Why the stage must run again over a reused mesh: the tile's last
    run left objects unfitted (its rows stand), else None.  Never
    raises."""
    try:
        import O4_Unpatched_Airports as UNPATCHED
        rows = [r for r in UNPATCHED.read_degraded(tile)
                if r.get("code") == "pack_objects_not_fitted"]
    except Exception:
        return None
    if not rows:
        return None
    named = sorted({r["airport"] for r in rows if r.get("airport")})
    return "its last run did not fit the objects of %s" % (
        ", ".join(named) or "the tile's airports")
