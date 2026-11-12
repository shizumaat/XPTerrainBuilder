"""Headless scanner for built Ortho4XP tiles.

This module ports the tile-detection logic of
``O4_GUI_Utils.OsInterface._preview_existing_tiles_inner`` without any
tkinter / UI dependency.  It is consumed by the new Qt front-end for its
map overlays and tile-info pane, but has no knowledge of any UI toolkit.

A "build directory" is the folder that holds a tile's ``Earth nav data``
tree (the ``.dsf``), its mesh/data files, its ``textures`` folder and the
per-tile ``XPTerrainBuilder_<short_latlon>.cfg`` (an Ortho4XP tile config
beside it is ignored — owner RULINGS 2026-10-26c).  Two on-disk layouts
exist:

* *per-tile* (``grouped=False``) — ``working_dir`` is the parent of many
  ``*XP_<short_latlon>`` sub-directories, one build dir per tile.
* *grouped* (``grouped=True``) — ``working_dir`` **is** a single build dir
  that holds several tiles' ``.dsf`` files under one ``Earth nav data``.

The scanner never executes or ``eval``s configuration files; it parses at
most three keys line-wise, exactly mirroring the legacy detection code.
"""

from __future__ import annotations

import glob
import os
import sys
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

import O4_Config_Names as CN
import O4_Custom_Scenery as PACKS
import O4_File_Names as FNAMES
import O4_Text_Files as TEXT
import O4_Tile_Build_Log as TILELOG
import O4_Tile_Volume as TVOL


@dataclass
class TileInfo:
    """Metadata describing one built (or partially built) Ortho4XP tile."""

    lat: int
    lon: int
    build_dir: str            # absolute path of the tile's build directory
    dir_name: str             # basename of the build directory
    dsf_present: bool
    provider: str = ""        # default_website from cfg, "" if unknown
    zl: Optional[int] = None  # default_zl from cfg
    has_zones: bool = False   # non-trivial zone_list in cfg
    # cover_airports_with_highres from cfg ("" or "False" = off; "True",
    # "ICAO" or "Existing" = airports upgraded to cover_zl).
    high_zl_airports: str = ""
    cover_zl: Optional[int] = None  # airport-cover zoomlevel from cfg
    custom_dem: str = ""      # pinned elevation source from cfg, "" if unset
    # The imagery the tile's textures carry (#1334): the dominant provider
    # among ``textures/`` file names and its most common ZL, "" / None
    # when no name parses.  :func:`effective_imagery` picks cfg or this.
    detected_provider: str = ""
    detected_zl: Optional[int] = None
    mesh_date: Optional[float] = None     # unix mtime of newest dsf/mesh
    imagery_date: Optional[float] = None  # unix mtime of newest texture
    size_bytes: Optional[int] = None      # None until compute_size()
    # The newest row of build_logs/build_record.json (#1226), None for a
    # tile built before logging; ``built_by`` is its "Built by" line —
    # for a tile without a record, filled from the DSF only when the
    # tile is asked for alone (:func:`with_built_by`), never by a scan.
    last_build: Optional[dict] = None
    built_by: str = ""
    # Where the folder really is (#1987): ``build_dir`` with its links
    # resolved; the drive it needs when that is not the one holding
    # its parent folder ("" = none), and whether that folder is
    # reachable now.  ``O4_Tile_Volume``.
    resolved_dir: str = ""
    volume: str = ""
    volume_mounted: bool = True
    # Who built it (#1958): ORIGIN_HERE for this app (a build record row,
    # a step record or a stamped tile cfg, :func:`built_here`), else
    # ORIGIN_OTHER — "some ortho" another tool made.  The maps style the
    # two apart.
    origin: str = ""
    # Imagery on demand (#1992): the tile was built with low-res
    # placeholder imagery, and its "always full resolution" pin — both
    # from its imagery record (``O4_Tile_Utils.imagery_manifest_path``).
    on_demand: bool = False
    pinned: bool = False
    # What the build stood its airports on (owner 2026-11-12T21:55Z:
    # "the tile details like what imagery was used, detail, ground shaped
    # dates etc."): the elevation each airport's inset came from, grouped
    # ("HRDEM 1 m: CYBW, CYYC"), and the airports the newest build graded
    # with their packs; "" when unknown.
    airport_elevation: str = ""
    airports: str = ""


#: :attr:`TileInfo.origin` of a tile this app built, and of another's.
ORIGIN_HERE = "xptb"
ORIGIN_OTHER = "other"
#: ... and of a tile another tool built that Convert existing tiles
#: ADOPTED (``o4_engine.world_adopt``): its mesh kept, packaged and
#: offloaded as one of ours.
ORIGIN_ADOPTED = "adopted"
#: The adopted tile's stamp, in its folder (written by ``world_adopt``).
ADOPTED_STAMP = ".xptb_adopted.json"


##############################################################################
# Internal helpers
##############################################################################
def _cfg_candidates(build_dir: str, lat: int, lon: int) -> list[str]:
    """Return the config paths to try: this app's own tile config only.

    Ortho4XP's ``Ortho4XP_+XX+YYY.cfg`` and its older generic
    ``Ortho4XP.cfg`` are ignored (owner RULINGS 2026-10-26c): a tile an
    old Ortho4XP built shows no provider from its config, and the library
    reads the imagery from the texture names instead.
    """
    return [CN.tile_cfg_path(build_dir, lat, lon)]


def _parse_cfg(
    cfg_path: str,
) -> tuple[str, Optional[int], bool, str, str, Optional[int]]:
    """Parse the keys of interest from a tile config file.

    Returns ``(provider, zl, has_zones, custom_dem, high_zl_airports,
    cover_zl)``.  ``provider`` is ``""`` when the ``default_website`` line
    is absent, ``zl`` is ``None`` when ``default_zl`` is missing or
    non-integer, ``has_zones`` mirrors the legacy ``len(line[10:]) > 3``
    test on the ``zone_list`` line, ``custom_dem`` is the tile's pinned
    elevation source (``""`` when unset) for the info pane's elevation
    row, and the last two carry the airport high-ZL cover setting
    (``cover_airports_with_highres`` / ``cover_zl``) for the info pane's
    zoom-level row.

    Only these keys are inspected; the file is never executed.  Legacy
    configs (old Ortho4XP ones, read here only for a scenery pack's
    imagery — ``O4_Custom_Scenery``) quote string values
    (``default_website='Arc'``) — quotes are stripped, matching
    ``O4_Settings_Model._strip_legacy_quotes``.
    """
    def _unquote(value: str) -> str:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            return value[1:-1]
        return value

    provider = ""
    zl: Optional[int] = None
    has_zones = False
    custom_dem = ""
    high_zl_airports = ""
    cover_zl: Optional[int] = None
    try:
        with TEXT.open_supplied(cfg_path, legacy_ansi=True) as f:
            for line in f.readlines():
                if line[:15] == "default_website":
                    provider = _unquote(line.strip().split("=", 1)[1].strip())
                elif line[:10] == "default_zl":
                    try:
                        zl = int(line.strip().split("=", 1)[1])
                    except (ValueError, IndexError):
                        zl = None
                elif line[:10] == "custom_dem":
                    custom_dem = _unquote(line.strip().split("=", 1)[1].strip())
                elif line[:9] == "zone_list" and len(line[10:]) > 3:
                    has_zones = True
                elif line[:27] == "cover_airports_with_highres":
                    high_zl_airports = _unquote(
                        line.strip().split("=", 1)[1].strip())
                elif line[:9] == "cover_zl=":
                    try:
                        cover_zl = int(line.strip().split("=", 1)[1])
                    except (ValueError, IndexError):
                        cover_zl = None
    except OSError:
        pass
    return provider, zl, has_zones, custom_dem, high_zl_airports, cover_zl


def _mesh_date(build_dir: str, lat: int, lon: int) -> Optional[float]:
    """Newest mtime among the tile's ``.dsf`` and ``Data*.mesh`` files
    (the mesh in the tile's rebuild cache, or the folder's own)."""
    candidates = glob.glob(
        os.path.join(build_dir, "Earth nav data", "**", "*.dsf"),
        recursive=True,
    )
    candidates += glob.glob(os.path.join(build_dir, "Data*.mesh"))
    candidates.append(FNAMES.mesh_file(build_dir, lat, lon))
    mtimes = []
    for path in candidates:
        try:
            mtimes.append(os.path.getmtime(path))
        except OSError:
            pass
    return max(mtimes) if mtimes else None


def _imagery_date(build_dir: str) -> Optional[float]:
    """Newest mtime among files directly under ``<build_dir>/textures/``."""
    tex_dir = os.path.join(build_dir, "textures")
    if not os.path.isdir(tex_dir):
        return None
    # One stat per file (``scandir``'s entry type is free): a tile holds
    # hundreds of textures and a Custom Scenery of 2,500 tiles held ~850,000,
    # where isfile + getmtime stat'ed each twice (29 s of a 42 s scan).
    mtimes = []
    try:
        entries = list(os.scandir(tex_dir))
    except OSError:
        return None
    for entry in entries:
        try:
            if entry.is_file():
                mtimes.append(entry.stat().st_mtime)
        except OSError:
            pass
    return max(mtimes) if mtimes else None


def _detected_imagery(build_dir: str) -> Tuple[str, Optional[int]]:
    """``(provider, zl)`` read from the names under ``<build_dir>/textures/``
    (``O4_Custom_Scenery.imagery_from_file_names``), or ``("", None)``."""
    try:
        names = os.listdir(os.path.join(build_dir, "textures"))
    except OSError:
        return "", None
    found = PACKS.imagery_from_file_names(names)
    if found is None:
        return "", None
    return _current_provider(found[0]), found[1]


def _current_provider(code: str) -> str:
    """A retired provider's replacement (its ``.lay``'s ``replaced_by``,
    e.g. NZ -> LINZ, #1339), read from the imagery registry when this
    process has loaded it; else ``code``."""
    imagery = sys.modules.get("O4_Imagery_Utils")
    provider = getattr(imagery, "providers_dict", {}).get(code) if imagery else None
    replacement = str((provider or {}).get("replaced_by") or "").strip()
    return replacement or code


#: Where a tile's imagery came from: its cfg, or its texture names.
SOURCE_CONFIG = "config"
SOURCE_DETECTED = "detected"


def effective_imagery(info) -> Optional[Tuple[str, Optional[int], str]]:
    """``(provider, zl, source)`` a built tile was made with, or None (#1334).

    The cfg wins when it names a provider (its ZL, else the detected ZL of
    that same provider); otherwise the textures' detected provider and ZL.
    ``source`` is :data:`SOURCE_CONFIG` or :data:`SOURCE_DETECTED`.  Read
    by adoption, the mismatch warning and "Rebuild tile" in both apps; the
    Mac's ``TileImageryChoice.resolve`` is this rule, pinned to the same
    fixture (``Fixtures/Imagery/tile_imagery.json``).  ``info`` is a
    :class:`TileInfo` or its JSON dict.
    """
    def field(name, default):
        if isinstance(info, dict):
            return info.get(name, default)
        return getattr(info, name, default)

    provider = str(field("provider", "") or "")
    zl = field("zl", None)
    detected = str(field("detected_provider", "") or "")
    detected_zl = field("detected_zl", None)
    if provider:
        if zl is None and detected == provider:
            zl = detected_zl
        return provider, zl, SOURCE_CONFIG
    if detected:
        return detected, detected_zl, SOURCE_DETECTED
    return None


def built_here(build_dir: str, lat: int, lon: int,
               last_build: Optional[dict] = None) -> bool:
    """Whether this app built the tile: its build record names this app,
    or it has this app's step record, or its tile cfg carries the stamp
    this app writes.  A folder with none of them was built by another
    tool (the Library lists it read-only)."""
    if ((last_build or {}).get("builder") or {}).get("tool") == \
            TILELOG.BUILDER_TOOL:
        return True
    if os.path.isfile(FNAMES.step_record_file(build_dir, lat, lon)):
        return True
    import O4_Cfg_Vars as CFGVARS
    try:
        with TEXT.open_supplied(CN.tile_cfg_path(build_dir, lat, lon)) as handle:
            for line in handle:
                if line.split("=", 1)[0].strip() == CFGVARS.cfg_stamp_key:
                    return True
    except OSError:
        pass
    return False


def adopted_record(build_dir: str) -> dict:
    """The :data:`ADOPTED_STAMP` of ``build_dir`` (``{}`` when it has
    none or it does not read)."""
    import json
    try:
        with open(os.path.join(build_dir, ADOPTED_STAMP),
                  encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return {}
    return record if isinstance(record, dict) else {}


def ours(build_dir: str, lat: int, lon: int,
         last_build: Optional[dict] = None) -> bool:
    """This app built the tile (:func:`built_here`) or adopted it
    (:func:`adopted_record`): ours to package and offload."""
    return (built_here(build_dir, lat, lon, last_build)
            or bool(adopted_record(build_dir)))


def origin_of(build_dir: str, lat: int, lon: int,
              last_build: Optional[dict] = None) -> str:
    """:data:`ORIGIN_HERE`, :data:`ORIGIN_ADOPTED` or :data:`ORIGIN_OTHER`."""
    if built_here(build_dir, lat, lon, last_build):
        return ORIGIN_HERE
    return ORIGIN_ADOPTED if adopted_record(build_dir) else ORIGIN_OTHER


def _build_tile_info(
    build_dir: str, lat: int, lon: int, dir_name: str
) -> Optional[TileInfo]:
    """Assemble a :class:`TileInfo` for one build directory, or ``None``.

    A tile is reported when its ``.dsf`` exists (``dsf_present=True``) or,
    failing that, when a tile config file or its imagery record exists
    (``dsf_present=False``: a tile the World pack draws keeps only its
    records here, ``o4_engine.world_records``).  When none is present
    ``None`` is returned so the caller skips it.
    """
    dsf_path = os.path.join(
        build_dir, "Earth nav data", FNAMES.long_latlon(lat, lon) + ".dsf"
    )
    dsf_present = os.path.isfile(dsf_path)

    # THE TILE'S ONE-TIME HAND-OVER (owner RULINGS 2026-10-26c): a scan is
    # a first touch like any other, so the info pane reads the same file
    # the build will — and every scanned tile gets its earlier backup back.
    CN.adopt_tile_cfg(build_dir, lat, lon)

    cfg_path = next(
        (p for p in _cfg_candidates(build_dir, lat, lon) if os.path.isfile(p)),
        None,
    )

    if (not dsf_present and cfg_path is None
            and not os.path.isfile(imagery_record_path(build_dir, lat, lon))):
        return None

    provider, zl, has_zones, custom_dem, high_zl_airports, cover_zl = (
        "", None, False, "", "", None)
    if cfg_path is not None:
        (provider, zl, has_zones, custom_dem,
         high_zl_airports, cover_zl) = _parse_cfg(cfg_path)
    last_build = TILELOG.last_build(build_dir, lat, lon)

    detected_provider, detected_zl = _detected_imagery(build_dir)
    if not detected_provider:
        detected_provider, detected_zl = _recorded_imagery(build_dir, lat, lon)
    resolved_dir, volume, mounted = TVOL.tile_volume(build_dir)
    mesh_date = _mesh_date(build_dir, lat, lon)
    imagery_date = _imagery_date(build_dir)
    if mesh_date is None or imagery_date is None:
        recorded = _recorded_dates(build_dir, lat, lon)
        mesh_date = recorded[0] if mesh_date is None else mesh_date
        imagery_date = recorded[1] if imagery_date is None else imagery_date
    return TileInfo(
        lat=lat,
        lon=lon,
        build_dir=os.path.abspath(build_dir),
        dir_name=dir_name,
        dsf_present=dsf_present,
        provider=provider,
        zl=zl,
        has_zones=has_zones,
        high_zl_airports=high_zl_airports,
        cover_zl=cover_zl,
        custom_dem=custom_dem,
        detected_provider=detected_provider,
        detected_zl=detected_zl,
        mesh_date=mesh_date,
        imagery_date=imagery_date,
        size_bytes=None,
        last_build=last_build,
        built_by=TILELOG.built_by_text(last_build),
        resolved_dir=resolved_dir,
        volume=volume,
        volume_mounted=mounted,
        origin=origin_of(build_dir, lat, lon, last_build),
        airport_elevation=_airport_elevation_text(build_dir),
        airports=_airports_text(last_build),
        **_on_demand_flags(build_dir, lat, lon),
    )


def imagery_record_path(build_dir: str, lat: int, lon: int) -> str:
    """The tile's imagery record (``O4_Tile_Utils.imagery_manifest_path``
    for a tile object): beside its cfg, named for the tile."""
    return os.path.join(build_dir, "Ortho4XP_%s_imagery.json"
                        % FNAMES.short_latlon(lat, lon))


def read_imagery_record(build_dir: str, lat: int, lon: int) -> dict:
    """The tile's imagery record as a dict, ``{}`` when it has none or it
    cannot be read."""
    import json
    try:
        with open(imagery_record_path(build_dir, lat, lon),
                  encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return {}
    return record if isinstance(record, dict) else {}


def _on_demand_flags(build_dir: str, lat: int, lon: int) -> dict:
    """``{"on_demand", "pinned"}`` from the tile's imagery record (#1992)."""
    record = read_imagery_record(build_dir, lat, lon)
    return {"on_demand": bool(record.get("on_demand")),
            "pinned": bool(record.get("pinned"))}


def _recorded_imagery(build_dir: str, lat: int, lon: int
                      ) -> Tuple[str, Optional[int]]:
    """``(provider, zl)`` the imagery record names, for a folder with no
    textures to read them from (a tile the World pack draws); ``("",
    None)`` when it names none."""
    record = read_imagery_record(build_dir, lat, lon)
    provider = record.get("provider")
    zl = record.get("zoomlevel")
    if not isinstance(provider, str) or not provider:
        return "", None
    return (_current_provider(provider),
            zl if isinstance(zl, int) and not isinstance(zl, bool) else None)


def _recorded_dates(build_dir: str, lat: int, lon: int
                    ) -> Tuple[Optional[float], Optional[float]]:
    """``(mesh date, imagery date)`` from the imagery record, for a folder
    that keeps a tile's records without its mesh or textures (a tile the
    World pack draws, ``o4_engine.world_records``): the mesh's date the
    record names, and the record's own date."""
    record = read_imagery_record(build_dir, lat, lon)
    if not record:
        return None, None
    mesh = record.get("mesh")
    mesh_date = (float(mesh[1]) if isinstance(mesh, list) and len(mesh) > 1
                 and isinstance(mesh[1], (int, float)) else None)
    try:
        written = os.path.getmtime(imagery_record_path(build_dir, lat, lon))
    except OSError:
        written = None
    return mesh_date, written


def _resolution(metres) -> str:
    if not isinstance(metres, (int, float)):
        return ""
    return "%g m" % (round(metres, 1) if metres < 10 else round(metres))


def _airport_elevation_text(build_dir: str) -> str:
    """The elevation the tile's airports were built on, grouped by source
    (``O4_Unpatched_Airports.read_inset_sources``): ``"HRDEM 1 m: A, B;
    COPERNICUSGLO30 30 m: C"`` -- ``""`` when the build recorded none."""
    import types

    import O4_Unpatched_Airports as UNPATCHED
    groups: dict = {}
    for row in UNPATCHED.read_inset_sources(
            types.SimpleNamespace(build_dir=build_dir)):
        if isinstance(row, dict) and row.get("icao"):
            head = " ".join(part for part in (
                str(row.get("provider") or "?"),
                _resolution(row.get("resolution_m"))) if part)
            groups.setdefault(head, []).append(str(row["icao"]))
    return "; ".join("%s: %s" % (head, ", ".join(sorted(names)))
                     for head, names in groups.items())


def _airports_text(last_build: Optional[dict]) -> str:
    """The airports the build graded, each with its custom pack:
    ``"HEAZ, HECA (HECA Cairo pack)"``; ``""`` when the record has none."""
    airports = (last_build or {}).get("airports")
    if not isinstance(airports, dict):
        return ""
    words = []
    for icao in sorted(airports):
        fact = airports[icao] if isinstance(airports[icao], dict) else {}
        pack = fact.get("pack") if fact.get("custom") else ""
        words.append("%s (%s)" % (icao, pack) if pack else str(icao))
    return ", ".join(words)


def _offline_tile_info(
    build_dir: str, lat: int, lon: int, dir_name: str
) -> Optional[TileInfo]:
    """A tile whose folder is a link onto a drive that is not connected
    (#1987), or ``None`` when ``build_dir`` is not such a link.  Nothing
    in it can be read, so it is reported as the built tile it was
    linked as, with only its location filled in — the maps still draw it
    (brown, "Requires <drive>") instead of forgetting it."""
    if not os.path.islink(build_dir):
        return None
    resolved_dir, volume, mounted = TVOL.tile_volume(build_dir)
    if not volume or mounted:
        return None
    return TileInfo(
        lat=lat, lon=lon, build_dir=os.path.abspath(build_dir),
        dir_name=dir_name, dsf_present=True,
        resolved_dir=resolved_dir, volume=volume, volume_mounted=False,
    )


def with_built_by(info: Optional[TileInfo]) -> Optional[TileInfo]:
    """``info`` with its "Built by" line, read from the tile's DSF when it
    has no build record (one selected tile: never call it in a scan)."""
    if info is not None and not info.built_by and info.dsf_present:
        info.built_by = TILELOG.built_by_text(
            agent=TILELOG.dsf_creation_agent(
                FNAMES.dsf_file(info.build_dir, info.lat, info.lon)))
    return info


def iter_scan_tiles(
    working_dir: str,
) -> "Iterator[tuple[int, int, Optional[tuple[int, int]], Optional[TileInfo]]]":
    """Incremental form of :func:`scan_tiles` (per-tile mode) for live UIs.

    Yields ``(done, total, key, info)`` after EVERY directory entry
    examined — ``done`` counts entries processed so far, ``total`` is the
    entry count, and ``key``/``info`` carry the ``(lat, lon)`` and
    :class:`TileInfo` when that entry produced a new tile (``None``/``None``
    otherwise), so a consumer can both drive a progress bar and surface
    tiles as they are read.  Acceptance, "sorted, first wins" duplicate
    handling, and symlink traversal are identical to
    ``scan_tiles(working_dir)`` — that function is this generator drained.
    """
    try:
        # sorted: "first wins" for duplicate lat/lon must be deterministic
        # across filesystems (raw listdir order is creation-dependent on
        # APFS and arbitrary elsewhere; the duplicate-latlon test pins the
        # sorted-first winner).
        names = sorted(os.listdir(working_dir))
    except OSError:
        return
    total = len(names)
    seen: set[tuple[int, int]] = set()
    for done, dir_name in enumerate(names, start=1):
        key: Optional[tuple[int, int]] = None
        info: Optional[TileInfo] = None
        if "XP_" in dir_name:
            try:
                lat = int(dir_name.split("XP_")[1][:3])
                lon = int(dir_name.split("XP_")[1][3:7])
            except (ValueError, IndexError):
                lat = None
            # Enlarged directory-name acceptance can yield more than one dir
            # for the same (lat, lon); keep the first encountered, like the
            # legacy.
            if lat is not None and (lat, lon) not in seen:
                build_dir = os.path.join(working_dir, dir_name)
                if os.path.isdir(build_dir):
                    built = _build_tile_info(build_dir, lat, lon, dir_name)
                else:
                    built = _offline_tile_info(build_dir, lat, lon, dir_name)
                if built is not None:
                    seen.add((lat, lon))
                    key, info = (lat, lon), built
        yield done, total, key, info


def _scan_per_tile(working_dir: str) -> dict[tuple[int, int], TileInfo]:
    """Scan a parent directory of per-tile ``*XP_*`` build directories."""
    tiles: dict[tuple[int, int], TileInfo] = {}
    for _done, _total, key, info in iter_scan_tiles(working_dir):
        if key is not None:
            tiles[key] = info
    return tiles


def _scan_grouped(working_dir: str) -> dict[tuple[int, int], TileInfo]:
    """Scan a single grouped build directory holding several tiles."""
    tiles: dict[tuple[int, int], TileInfo] = {}
    end_dir = os.path.join(working_dir, "Earth nav data")
    if not os.path.isdir(end_dir):
        return tiles
    dir_name = os.path.basename(os.path.normpath(working_dir))
    for sub in os.listdir(end_dir):
        sub_path = os.path.join(end_dir, sub)
        if not os.path.isdir(sub_path):
            continue
        for file_name in os.listdir(sub_path):
            if not file_name.endswith(".dsf"):
                continue
            try:
                lat = int(file_name[0:3])
                lon = int(file_name[3:7])
            except ValueError:
                continue
            if (lat, lon) in tiles:
                continue
            info = _build_tile_info(working_dir, lat, lon, dir_name)
            if info is not None:
                tiles[(lat, lon)] = info
    return tiles


##############################################################################
# Public API
##############################################################################
def scan_tiles(
    working_dir: str, grouped: bool = False
) -> dict[tuple[int, int], TileInfo]:
    """Scan ``working_dir`` for built tiles, keyed by ``(lat, lon)``.

    When ``grouped`` is ``False`` (the default) ``working_dir`` is treated
    as the parent of many per-tile ``*XP_<short_latlon>`` build directories.
    When ``grouped`` is ``True`` ``working_dir`` is itself a single build
    directory whose ``Earth nav data`` tree holds several tiles' ``.dsf``
    files.
    """
    if grouped:
        return _scan_grouped(working_dir)
    return _scan_per_tile(working_dir)


def tile_info(
    lat: int, lon: int, working_dir: str, grouped: bool = False
) -> Optional[TileInfo]:
    """Return the :class:`TileInfo` for a single tile, or ``None``.

    In grouped mode ``working_dir`` is the build directory itself.  In
    per-tile mode the expected build directory is derived from
    :func:`O4_File_Names.build_dir` (default ``zOrtho4XP_<short_latlon>``
    naming); if that exact directory is absent the whole ``working_dir`` is
    scanned for any ``*XP_*`` directory matching ``(lat, lon)``.
    """
    if grouped:
        dir_name = os.path.basename(os.path.normpath(working_dir))
        return _build_tile_info(working_dir, lat, lon, dir_name)

    # Per-tile: FNAMES.build_dir treats a trailing-slash custom dir as the
    # parent of per-tile dirs and returns "<working_dir>/zOrtho4XP_<short>".
    custom = working_dir
    if not custom.endswith(("/", "\\")):
        custom = custom + "/"
    expected = FNAMES.build_dir(lat, lon, custom)
    if os.path.isdir(expected):
        info = _build_tile_info(
            expected, lat, lon, os.path.basename(os.path.normpath(expected))
        )
        if info is not None:
            return info

    # Fall back to a full scan (handles non-default directory names).
    return scan_tiles(working_dir, grouped=False).get((lat, lon))


def tree_size(path: str) -> int:
    """Sum the byte size of every file under ``path`` (0 when absent).

    Symlinks are not followed: a linked folder is somebody else's bytes.
    """
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.stat(os.path.join(root, name),
                                 follow_symlinks=False).st_size
            except OSError:
                pass
    return total


def compute_size(info: TileInfo) -> int:
    """Sum the byte size of every file under ``info.build_dir``.

    Symlinks are not followed.  The result is stored on ``info.size_bytes``
    and also returned.
    """
    info.size_bytes = tree_size(info.build_dir)
    return info.size_bytes
