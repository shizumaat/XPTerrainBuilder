"""The flight's scenery reloads with the World pack (spec
flight-manager-and-world-20261110 §7.5 rules S5, S6 (a) and (b); lanes
F1b, F2): the staged tiles go in over the ones X-Plane loaded, X-Plane
reloads once, and the names the new tiles no longer use are removed only
after X-Plane's log shows the reload read the new DSF.

:class:`MergeReload` is the flight manager's ``ground_reload(tiles)``
callable (both reloads: on the ground before departure, and the one in
the air for the destination or a diversion airport):

* the call merges each staged tile in (``O4_World_Pack.swap_in(merge=
  True)``: file by file, every old name kept), registers it with the
  on-demand index, sends X-Plane's reload and remembers each tile's
  ``stale`` names with the latest load the witness had of the tile;
* :meth:`MergeReload.sweep` (each flight tick, with the witness's latest
  load of every World tile) removes a tile's stale names once a NEWER
  load of it is in ``Log.txt`` (``O4_World_Pack._remove_stale``) -- rule
  S5: never remove a name a loaded tile may still open.
"""
from __future__ import annotations

import os
import shutil
from typing import Callable, Dict, List, Optional, Tuple

import O4_World_Pack as WP

from . import world_commands as WORLD

__all__ = ["MergeReload"]

Tile = Tuple[int, int]


class MergeReload:
    """See the module.  ``witness()`` -> ``{tile: load stamp}`` (the
    latest ``DsfLoad.t_s`` of each World tile), ``send()`` -> bool (X-Plane
    took the reload command)."""

    def __init__(self, scenery_dir: str,
                 build_dir_of: Callable[[int, int], str],
                 send: Callable[[], bool],
                 witness: Callable[[], Dict[Tile, float]]) -> None:
        self.scenery_dir, self.build_dir_of = scenery_dir, build_dir_of
        self.send, self.witness = send, witness
        #: ``{tile: (stale names, the load stamp before the reload)}``.
        self.pending: Dict[Tile, Tuple[List[str], Optional[float]]] = {}

    def __call__(self, tiles) -> bool:
        from . import world_publish as PUBLISH
        pack = WORLD.pack_dir(self.scenery_dir)
        before = self.witness() or {}
        for lat, lon in tiles:
            staged = os.path.join(WORLD.staging_root(), WP.tile_name(lat, lon))
            if not os.path.isfile(os.path.join(staged, WP.dsf_relpath(lat, lon))):
                continue
            done = WP.swap_in(pack, staged, lat, lon, merge=True)
            shutil.rmtree(staged, ignore_errors=True)
            PUBLISH._after_swap(self.scenery_dir, self.build_dir_of(lat, lon),
                                lat, lon)
            if done["stale"]:
                old = self.pending.get((lat, lon), ([], None))[0]
                self.pending[(lat, lon)] = (sorted(set(old) | set(done["stale"])),
                                            before.get((lat, lon)))
            WORLD.write_log({"swap_in": done["tile"], "merge": True,
                             "stale": len(done["stale"]), "from": "flight"})
        sent = bool(self.send())
        WORLD.write_log({"flight_reload": sent, "tiles": len(tiles)})
        return sent

    def sweep(self, stamps: Optional[Dict[Tile, float]]) -> int:
        """Remove the stale names of every tile X-Plane has loaded again
        since its reload; the count of names removed."""
        if not self.pending or not stamps:
            return 0
        pack = WORLD.pack_dir(self.scenery_dir)
        removed = 0
        for tile, (stale, before) in sorted(self.pending.items()):
            after = stamps.get(tile)
            if after is None or (before is not None and after <= before):
                continue
            count = WP._remove_stale(pack, stale)
            removed += count
            del self.pending[tile]
            WORLD.write_log({"stale_removed": WP.tile_name(*tile),
                             "names": count})
        return removed
