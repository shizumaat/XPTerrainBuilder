"""A full build of ours supersedes a tile's adopt record (#2047, owner
2026-11-13T13:44Z: a tile rebuilt by us "still says 'adopted' ... expected
it to go away").

Convert adopts a tile another tool built (``world_adopt.finish``): the
Convert journal's record says ``adopted``, the tile's folders carry the
adopted stamp (``O4_Tile_Info.ADOPTED_STAMP``) and its adopted package is
written (``<World>/XPTerrainBuilder_packages/<tile>_adopted.xptb``).  When
one of our full builds later swaps into the World pack, the pack draws OUR
mesh, so:

* :func:`supersede` -- at the swap (``world_publish._after_swap``): the
  journal record reads ``adopted: False`` with ``superseded`` (when) and
  ``superseded_by`` (the DSF's creation agent); the build folder's adopted
  stamp gets the same two fields, so ``O4_Tile_Info.adopted_record`` reads
  it as none.  The adopted PACKAGE and the stamp of the Convert copy
  (``lean/``) are kept: they are the tile's history and what Undo of
  Convert restores (RULINGS 2026-11-12h; ``flight_adopted``: "the adopted
  package kept for Undo").  The journal is not written while a Convert /
  Free space / rechoose run holds it (``world_migrate.active``):
  :func:`correct` catches the tile at the next start.
* :func:`correct` -- at the apps' start (``world_commands.world_onboard``):
  every journal record still ``adopted`` whose World pack DSF is ours
  (``sim/creation_agent`` starts with ``O4_Tile_Build_Log.BUILDER_TOOL``)
  is superseded as above.  Idempotent: a superseded record is no longer
  ``adopted``; the journal is backed up
  (``journal.json.<stamp>-before-supersede``, ``world_home``'s backup)
  before the first write of a run, and the run is one line of ``logs/world_pack.log``.

``world_state`` reads the DSF first (the newest word on the tile): a mesh
of ours is ``ORIGIN_HERE`` whatever the journal still says.

No tile or airport is named here.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import O4_Tile_Build_Log as TLOG
import O4_Tile_Info as TINFO
import O4_World_Pack as WP

__all__ = ["ours", "supersede", "correct"]

_PREFIX = "zOrtho4XP_"


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ours(dsf: str) -> str:
    """The creation agent of ``dsf`` when this app built it, else ``""``."""
    agent = TLOG.dsf_creation_agent(dsf)
    return agent if agent.startswith(TLOG.BUILDER_TOOL) else ""


def _mark_stamp(build_dir: str, fields: dict) -> bool:
    """Add ``fields`` to the build folder's adopted stamp, if it has one
    not yet superseded."""
    record = TINFO.adopted_record(build_dir) if build_dir else {}
    if not record:
        return False
    path = os.path.join(build_dir, TINFO.ADOPTED_STAMP)
    with open(path + ".part", "w", encoding="utf-8", newline="\n") as handle:
        json.dump({**record, **fields}, handle, indent=1, sort_keys=True)
    os.replace(path + ".part", path)
    return True


def _journal(scenery_dir: str):
    from .world_migrate import Journal, work_dir_for
    return Journal(work_dir_for(scenery_dir))


def supersede(scenery_dir: str, build_dir: str, lat: int, lon: int,
              journal=None) -> Dict[str, Any]:
    """Our full build of ``(lat, lon)`` is in the World pack: retire its
    adopt record (module docstring).  ``{"journal": bool, "stamp": bool}``
    -- what was changed; nothing when the pack's DSF is not ours."""
    from . import world_commands as WORLD
    from . import world_migrate as MIGRATE
    out = {"journal": False, "stamp": False}
    if not scenery_dir or not WORLD.managed(scenery_dir):
        return out
    agent = ours(os.path.join(WORLD.pack_dir(scenery_dir),
                              WP.dsf_relpath(lat, lon)))
    if not agent:
        return out
    fields = {"superseded": _utc(), "superseded_by": agent}
    out["stamp"] = _mark_stamp(build_dir, fields)
    if journal is None:
        if MIGRATE.active():            # its own Journal holds the file
            return out
        journal = _journal(scenery_dir)
    name = _PREFIX + WP.tile_name(lat, lon)
    if (journal.get(name) or {}).get("adopted"):
        journal.set(name, adopted=False, **fields)
        out["journal"] = True
    return out


def _build_dir(lat: int, lon: int) -> str:
    import O4_File_Names as FNAMES
    return FNAMES.build_dir(lat, lon, "")


def correct(scenery_dir: str, *, dry_run: bool = False,
            build_dir_of=_build_dir) -> Dict[str, Any]:
    """Supersede every journal record still ``adopted`` whose World pack
    DSF is ours (module docstring).  ``{"tiles": [names], "backup"}``;
    ``dry_run`` lists them and writes nothing."""
    from . import world_commands as WORLD
    from . import world_home as HOME
    from . import world_migrate as MIGRATE
    out: Dict[str, Any] = {"tiles": [], "backup": None}
    if not scenery_dir or not WORLD.managed(scenery_dir) or MIGRATE.active():
        return out
    pack = WORLD.pack_dir(scenery_dir)
    journal = _journal(scenery_dir)
    for name, record in sorted(journal.records.items()):
        if not (isinstance(record, dict) and record.get("adopted")
                and name.startswith(_PREFIX)):
            continue
        try:
            lat, lon = WP.parse_tile(name[len(_PREFIX):])
        except ValueError:
            continue
        if not ours(os.path.join(pack, WP.dsf_relpath(lat, lon))):
            continue
        out["tiles"].append(name)
        if dry_run:
            continue
        if out["backup"] is None:
            out["backup"] = HOME._backup(journal.path, "supersede") or ""
        try:
            supersede(scenery_dir, build_dir_of(lat, lon), lat, lon,
                      journal=journal)
        except OSError as error:        # logged; the next start retries
            out.setdefault("errors", []).append(f"{name}: {error}"[:200])
    if out["tiles"] and not dry_run:
        WORLD.write_log({"adopt_superseded": out["tiles"],
                         "errors": out.get("errors", [])[:5]})
    return out
