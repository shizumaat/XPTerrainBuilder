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

Never raises: a failure is one log line and the tile goes on, as it
always has at the end of the mesh step.
"""
from __future__ import annotations

import O4_UI_Utils as UI

__all__ = ["run"]


def run(tile) -> dict:
    """The object stage for ``tile`` against the mesh in its build
    directory: ``rebake_after_mesh``'s counts, ``{}`` when it failed.
    Lazy import: the long-running GUI caches ``auto_patch`` modules."""
    try:
        from auto_patch import object_stage
        return object_stage.rebake_after_mesh(tile)
    except Exception as exception:
        UI.vprint(1, "auto_patch post-mesh object re-anchor failed:",
                  exception)
        return {}
