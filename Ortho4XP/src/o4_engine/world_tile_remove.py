"""ENGINE COMMAND ``world_tile_remove``: the tile pane's "Remove from World
Pack…" (owner 2026-11-12T20:23Z, lane ltilepane).

A real tile of the World pack (full, mesh or drape, ``world_state``) goes
back to a placeholder: its package is written FIRST
(``package_first``, owner 2026-11-11T16:45Z) from the tile's rebuild
inputs, then ``world_commands.world_tile_set`` puts the placeholder over
its DSF and removes the pack's own terrain and texture folders when
X-Plane cannot hold them.  The Convert work folder's ``originals/`` and
files on other drives are never touched: the pack's folders hold hard
links (``O4_World_Pack._place_dir``), and a link is unlinked, never
followed.  A tile that cannot be packaged is still removed and the
reply's ``package`` says why (the ``package_first`` rule).

Refused without ``confirm`` (its sentence is the apps' confirmation) and
for a tile the World pack does not hold as a real tile.  Run on the
Library worker (``library.start``): it replies ``{"status": "started"}``
and ``LibraryReady`` completes it.

No tile or airport is named here.
"""
from __future__ import annotations

import os

import O4_World_Pack as WP

__all__ = ["world_tile_remove", "COMMANDS", "REFUSED_WHILE_BUILDING"]


def _held(scenery_dir: str, lat: int, lon: int) -> str:
    """The real tile's DSF in the World pack, or raise ``ValueError``."""
    from . import world_commands as WORLD
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if not WORLD.managed(scenery_dir):
        raise ValueError("The World pack is not installed.")
    path = os.path.join(WORLD.pack_dir(scenery_dir), WP.dsf_relpath(lat, lon))
    if not os.path.isfile(path) or WP.is_placeholder(path):
        raise ValueError("Tile %s is not built in the World pack; there is "
                         "nothing to remove." % WP.tile_name(lat, lon))
    return path


def _check(kwargs: dict) -> None:
    """The read loop's refusal (``library.start``)."""
    lat, lon = int(kwargs.get("lat")), int(kwargs.get("lon"))
    _held(kwargs.get("scenery_dir", ""), lat, lon)
    if not kwargs.get("confirm"):
        import O4_World_State_Text as TEXT
        raise ValueError("%s %s Send confirm=true to remove it."
                         % (TEXT.REMOVE_TITLE.format(tile=WP.tile_name(lat, lon)),
                            TEXT.REMOVE_MESSAGE))


def world_tile_remove(lat, lon, scenery_dir: str = "", confirm: bool = False,
                      **_ignored) -> dict:
    """The tile back to a placeholder, its package first (module doc).

    :returns: ``{"tile", "dsf", "folders_removed", "package": {"action",
        "path", "bytes", "why"}}``
    """
    lat, lon = int(lat), int(lon)
    _check({"lat": lat, "lon": lon, "scenery_dir": scenery_dir,
           "confirm": confirm})
    from . import package_first as FIRST
    from . import world_commands as WORLD
    package = FIRST.Pass().tile(lat, lon, built=True) or {}
    done = WORLD.world_tile_set(lat, lon, scenery_dir=scenery_dir)
    return {**done, "package": package}


#: What :func:`library.start` runs, and its read-loop check.
COMMANDS = {"world_tile_remove": (world_tile_remove, _check)}
REFUSED_WHILE_BUILDING = {"world_tile_remove": "removing a tile"}
