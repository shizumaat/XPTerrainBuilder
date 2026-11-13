"""What X-Plane draws on each tile of the World pack, for the Build map and
the Library (#2024, owner 2026-11-12T15:46Z):

    "Would be good to be able to see which tiles are fully downloaded,
    which have mesh and placeholders, and which truly have nothing."

ONE reader (:func:`iter_world`), streamed by the engine's ``scan``
(``ScanBatch.world``), gives every tile the World pack or the Convert
journal knows a :class:`WorldTile`:

* ``state`` (:data:`STATES`) -- :data:`FULL`: a mesh (ours, adopted or
  another tool's) whose every texture is at full width (its on-demand
  index rows all upgraded to ``O4_DDS_Tiers.FULL_WIDTH``, or, with no
  index rows, its own DDS in the pack); :data:`MESH_LOWRES`: such a mesh
  whose imagery streams in flight (``sharp`` = the fraction of its
  textures at full width); :data:`DRAPE`: our photo over X-Plane's own
  mesh; :data:`PLACEHOLDER`: the World pack holds the tile but nothing is
  built (X-Plane's default scenery for now); :data:`NOTHING`: no DSF (a
  journal record only).  A tile neither holds is not listed: nothing;
* ``origin`` -- ``O4_Tile_Info.ORIGIN_HERE`` / ``ORIGIN_ADOPTED`` /
  ``ORIGIN_OTHER`` for a mesh (``ORIGIN_HERE`` when the DSF's
  ``sim/creation_agent`` is ours, a rebuild newer than any adopt record,
  #2047; else the journal's ``adopted`` or the adopted stamp of its
  on-demand copy; else another tool's),
  ``ORIGIN_HERE`` for a drape, ``""`` for a placeholder;
* ``source`` (:data:`SOURCES`) and ``volume`` -- where the tile's own
  files live now: :data:`SOURCE_ORIGINALS` (its folder in the Convert
  work folder's ``originals/``), :data:`SOURCE_LEAN` (an on-demand copy
  in ``lean/``; ``volume`` names the drive its full imagery is on, if
  any), :data:`SOURCE_DRIVE` (only on another drive, ``volume``), or
  ``""``;
* ``dsf`` -- the tile's DSF in the World pack (``""`` for a journal
  record with none): what "Show in Finder" reveals for a tile the pack
  holds (#2027);
* ``provider`` -- the photo provider that draws a real tile (#2018,
  ``O4_World_Imagery_Record``: its record, else its DDS names), ``""``
  for a placeholder or none.

Cost (owner's World pack, 18,259 DSFs, 2026-11-12): two directory levels
listed, the head of each small file read (placeholders), one property
read per real tile, ONE grouped index query, one journal read.  Nothing
is written.

No tile or airport is named here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

import O4_DSF_Header as DSFH
import O4_Imagery_OnDemand_Index as INDEX
import O4_Tile_Build_Log as TLOG
import O4_Tile_Info as TINFO
import O4_Tile_Volume as TVOL
import O4_World_Imagery_Record as IREC
import O4_World_Pack as WP

__all__ = ["FULL", "MESH_LOWRES", "DRAPE", "PLACEHOLDER", "NOTHING", "STATES",
           "SOURCE_ORIGINALS", "SOURCE_LEAN", "SOURCE_DRIVE", "SOURCES",
           "WorldTile", "iter_world", "read_world", "read_tile",
           "journal_record"]

FULL = "full"
MESH_LOWRES = "mesh_lowres"
DRAPE = "drape"
PLACEHOLDER = "placeholder"
NOTHING = "nothing"
#: In the legend's order.
STATES = (FULL, MESH_LOWRES, DRAPE, PLACEHOLDER, NOTHING)

SOURCE_ORIGINALS = "originals"
SOURCE_LEAN = "lean"
SOURCE_DRIVE = "drive"
SOURCES = (SOURCE_ORIGINALS, SOURCE_LEAN, SOURCE_DRIVE)

_PREFIX = "zOrtho4XP_"
_LEAN_DIR = "lean"


@dataclass(frozen=True)
class WorldTile:
    """One tile's World state (the module docstring)."""

    state: str
    origin: str = ""
    sharp: float = 0.0
    source: str = ""
    volume: str = ""
    dsf: str = ""
    provider: str = ""

    def wire(self, key: Tuple[int, int]) -> list:
        """``[lat, lon, state, origin, sharp, source, volume, dsf,
        provider]``: one ``ScanBatch.world`` row (positional, like
        ``installed``; a reader of the first eight is unchanged)."""
        return [key[0], key[1], self.state, self.origin,
                round(self.sharp, 3), self.source, self.volume, self.dsf,
                self.provider]

    def fields(self) -> dict:
        """The Library row's ``world`` dict."""
        return {"state": self.state, "origin": self.origin,
                "sharp": round(self.sharp, 3), "source": self.source,
                "volume": self.volume, "dsf": self.dsf,
                "provider": self.provider}


def _journal(scenery_dir: str) -> dict:
    """``{(lat, lon): record}`` of the Convert journal (``world_migrate``)."""
    from .world_migrate import Journal, work_dir_for
    out = {}
    for name, record in Journal(work_dir_for(scenery_dir)).records.items():
        if not name.startswith(_PREFIX) or not isinstance(record, dict):
            continue
        try:
            out[WP.parse_tile(name[len(_PREFIX):])] = record
        except ValueError:
            continue
    return out


def _is_dir(path: Optional[str]) -> bool:
    return bool(path) and os.path.isdir(path)


def _source(record: Optional[dict], home_volume: str) -> Tuple[str, str]:
    """``(source, volume)`` of a journal record (module docstring)."""
    if not record:
        return "", ""
    if _is_dir(record.get("original")):
        return SOURCE_ORIGINALS, ""
    full = record.get("link_target") or record.get("source") or ""
    volume = TVOL.volume_name(full) if full else ""
    if volume == home_volume:
        volume = ""
    config = record.get("config_dir") or ""
    if _is_dir(config) and os.path.basename(os.path.dirname(config)) == _LEAN_DIR:
        return SOURCE_LEAN, volume
    return (SOURCE_DRIVE, volume) if volume else ("", "")


def _origin(record: Optional[dict], agent: str) -> str:
    """Built here, adopted, or another tool's (module docstring).  The
    DSF is the newest word: a mesh of ours is ours whatever an older adopt
    record says (#2047, ``world_adopt_supersede``)."""
    if agent.startswith(TLOG.BUILDER_TOOL):
        return TINFO.ORIGIN_HERE
    if record and (record.get("adopted")
                   or (_is_dir(record.get("config_dir"))
                       and TINFO.adopted_record(record["config_dir"]))):
        return TINFO.ORIGIN_ADOPTED
    return TINFO.ORIGIN_OTHER


def _has_textures(pack: str, key: Tuple[int, int]) -> bool:
    try:
        with os.scandir(os.path.join(pack, "textures", WP.tile_name(*key))) as it:
            return any(True for _ in it)
    except OSError:
        return False


def _mesh_state(pack: str, key, sharpness: dict) -> Tuple[str, float]:
    """FULL or MESH_LOWRES, and the fraction sharp, of a mesh tile."""
    count, full = sharpness.get(WP.tile_name(*key), (0, 0))
    if count:
        return (FULL, 1.0) if full >= count else (MESH_LOWRES, full / count)
    return (FULL, 1.0) if _has_textures(pack, key) else (MESH_LOWRES, 0.0)


def _tile(pack: str, key, path: str, size: int, record: Optional[dict],
          sharpness: dict, home_volume: str) -> WorldTile:
    source, volume = _source(record, home_volume)
    if WP.is_placeholder(path, size):
        return WorldTile(PLACEHOLDER, "", 0.0, source, volume, path)
    agent = (DSFH.dsf_properties(path) or {}).get("sim/creation_agent", "")
    provider = str(IREC.read(pack, *key).get("provider") or "")
    if WP.kind_of_agent(agent) == DRAPE:
        return WorldTile(DRAPE, TINFO.ORIGIN_HERE, 0.0, source, volume, path,
                         provider)
    state, sharp = _mesh_state(pack, key, sharpness)
    return WorldTile(state, _origin(record, agent), sharp, source, volume, path,
                     provider)


def iter_world(scenery_dir: str, *, index_path: Optional[str] = None
               ) -> Iterator[Tuple[int, int, Tuple[int, int], WorldTile]]:
    """``(done, total, key, WorldTile)`` for every tile of the World pack
    in ``scenery_dir`` and every journal tile with no DSF (state
    :data:`NOTHING`).  Nothing at all when the pack is not the app's
    (``world_commands.managed``).  ``index_path`` -- the on-demand index
    (default: the data root's)."""
    from . import world_commands as WORLD
    if not scenery_dir or not WORLD.managed(scenery_dir):
        return
    pack = WORLD.pack_dir(scenery_dir)
    journal = _journal(scenery_dir)
    sharpness = INDEX.tile_sharpness(index_path)
    home_volume = TVOL.volume_name(scenery_dir)
    dsfs = list(WP.pack_dsfs(pack))
    held = {key for key, _path, _size in dsfs}
    left = sorted(key for key in journal if key not in held)
    total = len(dsfs) + len(left)
    done = 0
    for key, path, size in dsfs:
        done += 1
        yield done, total, key, _tile(pack, key, path, size, journal.get(key),
                                      sharpness, home_volume)
    for key in left:
        done += 1
        source, volume = _source(journal[key], home_volume)
        yield done, total, key, WorldTile(NOTHING, "", 0.0, source, volume)


def journal_record(scenery_dir: str, key: Tuple[int, int]) -> Optional[dict]:
    """The Convert journal's record of one tile, or None."""
    return _journal(scenery_dir).get((int(key[0]), int(key[1])))


def read_tile(scenery_dir: str, key: Tuple[int, int]) -> Optional[WorldTile]:
    """One tile's :class:`WorldTile` as :func:`iter_world` reads it, the
    on-demand index unread (a mesh with its own textures reads
    :data:`FULL`, without them :data:`MESH_LOWRES`); None when the pack
    holds no DSF there or is not the app's (a flight's endpoints,
    ``flight_adopted``)."""
    from . import world_commands as WORLD
    if not scenery_dir or not WORLD.managed(scenery_dir):
        return None
    key = (int(key[0]), int(key[1]))
    pack = WORLD.pack_dir(scenery_dir)
    path = os.path.join(pack, WP.dsf_relpath(*key))
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    return _tile(pack, key, path, size, journal_record(scenery_dir, key), {},
                 TVOL.volume_name(scenery_dir))


def read_world(scenery_dir: str, *, index_path: Optional[str] = None) -> dict:
    """``{(lat, lon): WorldTile}`` of :func:`iter_world` at once (the
    Library's rows when no scan has run)."""
    return {key: tile for _d, _t, key, tile in
            iter_world(scenery_dir, index_path=index_path)}
