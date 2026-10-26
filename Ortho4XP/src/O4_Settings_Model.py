"""Headless, exec-free settings model for the Qt settings window.

This module is the single source of truth about *which* Ortho4XP settings
the new settings window exposes, how they are grouped, and how their values
are read from / written to the flat ``key=value`` config files
(``XPTerrainBuilder.cfg`` and the per-tile ``XPTerrainBuilder_+XX+YYY.cfg``;
Ortho4XP's own files are never touched — :mod:`O4_Config_Names`).

It deliberately contains **no GUI-toolkit imports**, no ``exec``/``eval``
(``ast.literal_eval`` is used only to validate list-typed values in
:func:`coerce`), and no prints.  All type/default/allowed-value/hint
metadata is sourced from the registry in :mod:`O4_Cfg_Vars`; this module
only adds presentation grouping (categories, labels, advanced flags) and
the "preference" pseudo-settings that live outside the registry.

The heavy :mod:`O4_Config_Utils` module (which has import side effects,
including creating the global config file) is imported *lazily* inside
:func:`apply_runtime` only.
"""

from __future__ import annotations

import ast
import os
import shutil
from dataclasses import dataclass

import O4_Cfg_Vars
import O4_Config_Names as CN
import O4_File_Names as FNAMES
import O4_Text_Files as TEXT


@dataclass(frozen=True)
class Setting:
    """A single user-facing setting.

    :param name: cfg var name, or pref key when ``scope == "pref"``.
    :param label: human-readable label.
    :param scope: one of ``"app"``, ``"tile"`` or ``"pref"``.
    :param category: category key (see :data:`CATEGORIES`).
    :param advanced: whether the setting belongs to the Expert section
        (collapsed by default; the field keeps its historic name).
    :param vtype: value type — ``bool``, ``int``, ``float``, ``str`` or ``list``.
    :param default: default value rendered as a string.
    :param values: allowed values as strings, ``()`` when free-form.
    :param hint: full hint text from the registry (``""`` for prefs).
    :param value_labels: ``((value, label), ...)`` pairs giving a
        human-readable menu title per allowed value; ``()`` when the raw
        values are shown as-is. Stored values are never affected — labels
        are display-only.
    :param summary: the one-line plain hint under a row outside Expert
        (issue #823); ``""`` for an Expert row.
    """

    name: str
    label: str
    scope: str
    category: str
    advanced: bool
    vtype: type
    default: str
    values: tuple
    hint: str
    value_labels: tuple = ()
    summary: str = ""

    def label_for(self, value: str) -> str:
        """Menu title for *value* (the raw value when unlabeled)."""
        for raw, label in self.value_labels:
            if raw == value:
                return label
        return value

    def recommended(self) -> str:
        """The recommended value as the row's control shows it.

        It is the registry default — the value the app ships with;
        ``""`` when there is none to show (a preference, an empty path).
        """
        if self.scope == "pref" or self.default == "":
            return ""
        if self.vtype is bool and self.default in ("True", "False"):
            return "On" if self.default == "True" else "Off"
        return self.label_for(self.default)

    def secondary_text(self) -> str:
        """The grey line under the row (issue #823).

        Outside Expert: the one-line summary and the recommended value.
        In Expert: the cfg NAME, so forum advice still maps to the row,
        and the recommended value.  The Mac app builds the same line
        (``SettingsLayout.secondaryText``).
        """
        head = self.name if self.advanced else self.summary
        recommended = self.recommended()
        if not recommended:
            return head
        tail = RECOMMENDED_PREFIX + recommended
        return head + SECONDARY_SEPARATOR + tail if head else tail


# The words of the secondary line; SettingsLayout.swift uses the same ones.
RECOMMENDED_PREFIX = "Recommended: "
SECONDARY_SEPARATOR = " · "
EXPERT_TITLE = "Expert"


# ---------------------------------------------------------------------------
# Presentation layout — THE wording of the settings window (issue #823).
#
# The Mac app mirrors this table row for row in
# ``Sources/XPTerrainBuilder/SettingsLayout.swift``;
# ``tests/test_settings_layout_parity.py`` fails when the two differ.
#
# Each category is (key, title, members); each member is
#   (name, label, scope, expert, summary)
# where ``scope`` is ``"app"``, ``"tile"`` or ``"pref"`` (a preference that
# is not in the registry; its summary is also its hint).
#
# A row OUTSIDE Expert is a plain question (or a glossary term, issue #831)
# with a one-line ``summary``; the window adds the recommended value (the
# registry default).  An EXPERT row keeps its technical label and shows the
# cfg name as secondary text, so forum advice still maps to it; its summary
# is empty (the registry hint is its help).  Within a category the Expert
# rows come last — they form the Expert section, collapsed by default.
# Only wording and grouping live here: config KEYS and stored values never
# change with them.  Order within a category is significant and preserved.
# ---------------------------------------------------------------------------
_LAYOUT: list = [
    ("general", "General", [
        ("xplane_dir", "Where is X-Plane installed?", "pref", False,
         "Your X-Plane folder. Sets where scenery goes and which airports "
         "the map can find."),
        ("output_dir", "Where should finished tiles be saved?", "pref", False,
         "Empty uses the default Tiles folder."),
        ("custom_scenery_dir", "Where is X-Plane's Custom Scenery folder?", "app", False,
         "Finished tiles are linked into it so X-Plane finds them."),
        ("custom_overlay_src", "Where should roads, forests and buildings come from?", "app", False,
         "An X-Plane scenery folder, usually Global Scenery."),
        ("verbosity", "How much should the console show?", "app", False,
         "More detail helps when you report a problem."),
        ("cleaning_level", "Which build files should be kept?", "app", False,
         "Keeping more makes a rebuild faster but uses more disk."),
        ("custom_overlay_src_alternate", "Alternate overlay source", "app", True, ""),
        ("cifp_data_path", "X-Plane's runway data folder", "app", True, ""),
    ]),
    ("network", "Speed & Downloads", [
        ("max_build_slots", "How many tiles should build at once?", "app", False,
         "Auto uses this machine's processor cores."),
        ("max_download_slots", "How many imagery downloads should run at once?", "app", False,
         "Auto suits most connections."),
        ("max_convert_slots", "How many imagery files should be converted at once?", "app", False,
         "Auto uses every processor core but two."),
        ("overpass_server_choice", "Map data server", "app", False,
         "Where map data downloads from when no stored regional copy covers the tile."),
        ("osm_regional_extracts", "Use stored regional map data when available?", "app", False,
         "Faster than downloading each tile, and kinder to the map servers."),
        ("osm_extract_refresh_days", "Extract refresh age (days)", "app", True, ""),
        ("http_timeout", "HTTP timeout (s)", "app", True, ""),
        ("max_connect_retries", "Connection retries", "app", True, ""),
        ("max_baddata_retries", "Bad-data retries", "app", True, ""),
        ("check_tms_response", "Retry on imagery server errors", "app", True, ""),
    ]),
    ("imagery", "Imagery", [
        ("cover_airports_with_highres", "Use sharper imagery at airports?", "tile", False,
         "The same photos at a finer detail; more download and disk."),
        ("cover_zl", "Which ZL should the airport imagery use?", "tile", False,
         "ZL17 is about 1 m per pixel, ZL18 about 0.6 m."),
        ("cover_extent", "How far past the airport should it reach (km)?", "tile", False,
         "The sharper imagery covers the airport and this band around it."),
        ("sea_nodata_fill", "Repair blank spots in imagery over the sea?", "tile", False,
         "Fills the white or black rectangles some providers leave over coastal water."),
        ("color_harmonization", "Even out imagery colors across the tile?", "tile", False,
         "Removes the patchwork of different photo dates and providers."),
        ("texture_mode", "Texture mode", "tile", True, ""),
        ("airport_ortho_fade_width", "Airport ortho fade width (m)", "tile", True, ""),
        ("sea_texture_blur", "Sea texture blur (m)", "tile", True, ""),
        ("skip_downloads", "Skip imagery downloads", "app", True, ""),
        ("skip_converts", "Skip DDS conversion", "app", True, ""),
    ]),
    ("mesh", "Ground Shape", [
        ("curvature_tol", "Curvature tolerance", "tile", True, ""),
        ("apt_curv_tol", "Airport curvature tolerance", "tile", True, ""),
        ("apt_curv_ext", "Airport curvature extent (km)", "tile", True, ""),
        ("coast_curv_tol", "Coastline curvature tolerance", "tile", True, ""),
        ("coast_curv_ext", "Coastline curvature extent (km)", "tile", True, ""),
        ("limit_tris", "Max triangles (millions)", "tile", True, ""),
        ("min_angle", "Min triangle angle (°)", "tile", True, ""),
        ("sea_smoothing_mode", "Sea surface smoothing", "tile", True, ""),
        ("water_smoothing", "Inland water smoothing passes", "tile", True, ""),
        ("mesh_zl", "Max imagery zoom the mesh allows", "tile", True, ""),
    ]),
    ("elevation", "Elevation & Airports", [
        ("elevation_level", "How detailed should the elevation be?", "tile", False,
         "Auto uses 90 m data with high-resolution data at airports."),
        ("base_elevation_source", "Which elevation source should be used?", "app", False,
         "Auto picks the best source available for the tile."),
        ("custom_dem", "Use your own elevation file?", "tile", False,
         "Used instead of the downloaded elevation. Leave empty for automatic."),
        ("fill_nodata", "Fill gaps in the elevation data?", "tile", False,
         "Off turns gaps into sea level."),
        ("auto_patch", "Grade airports to official standards (FAA / ICAO / EASA)", "tile", False,
         "Shapes runways and taxiways to the slope rules, from X-Plane's runway data."),
        # App-level, not tile-level: a preference about how the user is
        # asked, not a property of a tile (spec §C.4, RULINGS 18a).
        ("auto_patch_boundary", "What if an airport crosses a tile edge?", "app", False,
         "Its ground shape needs the elevation of the tile next door too."),
        ("modify_custom_airports", "Fit custom airport buildings to the new ground", "tile", False,
         "Moves the 3-D objects of installed custom airports onto the reshaped ground."),
        ("airport_elevation_insets", "High-resolution airport elevation", "tile", False,
         "Downloads meter-class elevation for the airports where it exists."),
        ("airport_elevation_level", "How detailed should airport elevation be?", "tile", False,
         "Auto takes the finest available, down to 0.5 m."),
        ("elevation_coastline_band_km", "Coastline lidar band width (km)", "tile", True, ""),
        ("airport_elevation_inset_margin_m", "Lidar extent beyond airport (m)", "tile", True, ""),
        ("airport_elevation_inset_feather_m", "Lidar edge blend width (m)", "tile", True, ""),
        ("airport_elevation_providers", "Inset providers", "tile", True, ""),
        ("airport_inset_water", "Detect ponds in lidar", "tile", True, ""),
        ("apt_smoothing_pix", "Airport elevation smoothing (px)", "tile", True, ""),
        ("apt_smoothing_auto", "Scale smoothing to data quality", "tile", True, ""),
        ("working_grid_arc_seconds", "Working grid spacing", "tile", True, ""),
        ("iterate", "Iterative DEM refinement step", "tile", True, ""),
    ]),
    ("vector", "Roads & Map Data", [
        ("road_level", "Which roads should the ground be levelled for?", "tile", False,
         "Flattens the ground under roads and railways so they do not tilt."),
        ("road_banking_limit", "Road banking limit (m)", "tile", True, ""),
        ("lane_width", "Road lane width (m)", "tile", True, ""),
        ("max_levelled_segs", "Max levelled road segments", "tile", True, ""),
        ("clean_bad_geometries", "Repair bad OSM geometries", "tile", True, ""),
    ]),
    ("water", "Water & Coastlines", [
        ("water_tech", "Which water should X-Plane draw?", "tile", False,
         "XP12 uses X-Plane 12's water; XP11 + bathy blends the older way."),
        ("ratio_water", "How much photo should show through lakes and rivers?", "tile", False,
         "0 is plain X-Plane water, 1 is the photo only."),
        ("masking_mode", "What should the shoreline look like?", "tile", False,
         "How the land fades into the sea."),
        ("coastal_foam_edge", "Draw a wavy shoreline with a foam band?", "tile", False,
         "Replaces the straight land-to-water fade with a more natural edge."),
        ("ratio_bathy", "Bathymetry multiplier", "tile", True, ""),
        ("mask_zl", "Water mask resolution", "tile", True, ""),
        ("masks_width", "Mask width (m)", "tile", True, ""),
        ("inland_shore_feather_m", "Inland shore feather (m)", "tile", True, ""),
        ("water_simplification", "Water node simplification (m)", "tile", True, ""),
        ("min_area", "Min water area (km²)", "tile", True, ""),
        ("max_area", "Max unmasked water area (km²)", "tile", True, ""),
        ("use_masks_for_inland", "Mask inland water", "tile", True, ""),
        ("imprint_masks_to_dds", "Imprint masks into DDS", "tile", True, ""),
        ("distance_masks_too", "Build distance masks", "tile", True, ""),
        ("masks_custom_extent", "Custom mask extent", "tile", True, ""),
    ]),
    ("bathymetry", "Underwater Depth", [
        ("masks_use_DEM_too", "Use measured sea depth along the shore?", "tile", False,
         "Auto uses it near airports, where you fly low over the water."),
        ("bathymetry_airport_radius_km",
         "How far from those places should it be used (km)?", "tile", False,
         "In Auto, depth is fetched for shoreline this close to the places ticked below."),
        ("bathymetry_near_icao_airports", "Use it near airports with ICAO codes?", "tile", False,
         "Where airline and general-aviation approaches cross the water."),
        ("bathymetry_near_other_airports", "Use it near small airfields?", "tile", False,
         "Grass strips, bush fields and other fields without an ICAO code."),
        ("bathymetry_near_seaplane_bases", "Use it near seaplane bases?", "tile", False,
         "Few of them, and you land on the water there."),
        ("bathymetry_near_heliports", "Use it near heliports?", "tile", False,
         "Many of them, so this costs the most download."),
        ("reef_visibility_depth",
         "How deep can the sea floor be and still show (m)?", "tile", False,
         "Shallower water keeps part of the photo visible, like reefs and sandbanks."),
        ("osm_shallow_water_fallback",
         "Use mapped shallow water where no depth is measured?", "tile", False,
         "Mapped reefs and shoals keep their photo where no measured depth applies."),
        ("bathymetry_band_km", "Band width along shoreline (km)", "tile", True, ""),
        ("dsf_bathymetry", "DSF sea level raster source", "tile", True, ""),
    ]),
    ("rendering", "Look in the Sim", [
        ("overlay_lod", "How far away should photos over water be drawn (m)?", "tile", False,
         "A shorter distance helps frame rate and video memory."),
        ("terrain_casts_shadows", "Should the ground cast shadows?", "tile", False,
         "Only matters when scenery shadows are on in X-Plane."),
        ("use_decal_on_terrain", "Add fine ground detail up close?", "tile", False,
         "Noticeable at very low altitude."),
        ("normal_map_strength", "Normal map strength", "tile", True, ""),
        ("ovl_exclude_pol", "Exclude overlay polygon types", "app", True, ""),
        ("ovl_exclude_net", "Exclude overlay road types", "app", True, ""),
    ]),
]


def _build_registry() -> tuple:
    """Materialise Setting objects from :data:`_LAYOUT` + the cfg registry.

    Registry-backed vars missing from ``O4_Cfg_Vars.cfg_vars`` are skipped
    gracefully (omitted).  Preference members are constructed directly.
    """
    cfg_vars = O4_Cfg_Vars.cfg_vars
    ordered: list = []
    categories: list = []
    for entry in _LAYOUT:
        cat_key, cat_title, members = entry
        categories.append((cat_key, cat_title))
        for name, label, scope, advanced, summary in members:
            if scope == "pref":
                ordered.append(Setting(
                    name=name, label=label, scope=scope, category=cat_key,
                    advanced=advanced, vtype=str, default="", values=(),
                    hint=summary, summary=summary,
                ))
                continue
            spec = cfg_vars.get(name)
            if spec is None:
                # Var not present in the registry — omit gracefully.
                continue
            raw_values = spec.get("values", ())
            ordered.append(Setting(
                name=name, label=label, scope=scope, category=cat_key,
                advanced=advanced, vtype=spec["type"],
                default=str(spec["default"]),
                values=tuple(str(v) for v in raw_values),
                hint=spec.get("hint", ""),
                value_labels=tuple(
                    (str(value), title)
                    for value, title
                    in spec.get("value_labels", {}).items()
                ),
                summary=summary,
            ))
    return ordered, categories


_ALL_SETTINGS, CATEGORIES = _build_registry()
_BY_NAME: dict = {s.name: s for s in _ALL_SETTINGS}


# ---------------------------------------------------------------------------
# Registry access
# ---------------------------------------------------------------------------
def settings() -> list:
    """Return all settings in category order then declaration order."""
    return list(_ALL_SETTINGS)


def settings_for(category: str) -> list:
    """Return the settings belonging to *category* (declaration order)."""
    return [s for s in _ALL_SETTINGS if s.category == category]


def get_setting(name: str) -> Setting:
    """Return the :class:`Setting` named *name*; raise ``KeyError`` if unknown."""
    return _BY_NAME[name]


# ---------------------------------------------------------------------------
# Config file parsing helpers
# ---------------------------------------------------------------------------
def _strip_legacy_quotes(value: str) -> str:
    """Strip a single leading/trailing quote (config <= 1.20 compatibility)."""
    if value and value[0] in ('"', "'"):
        value = value[1:]
    if value and value[-1] in ('"', "'"):
        value = value[:-1]
    return value


def _parse_cfg(path: str, strip_quotes: bool = True) -> dict:
    """Parse a flat ``key=value`` config file into an ordered dict.

    Blank lines and ``#`` comments are skipped, values have legacy quotes
    stripped.  Returns ``{}`` if the file is absent.  Later duplicate keys
    win (matching the legacy loader) while keeping first-seen order.

    ``strip_quotes=False`` keeps every value EXACTLY as written — the one
    caller that needs it is the legacy-config inspector, whose whole job
    is to report the quoting a legacy writer left behind.
    """
    result: dict = {}
    if not os.path.isfile(path):
        return result
    # UTF-8; a cfg an older build wrote in this machine's ANSI code page
    # still reads back (issue #539).
    with TEXT.open_supplied(path, legacy_ansi=True) as f:
        for line in f:
            line = line.strip()
            if not line or line[0] == "#":
                continue
            if "=" not in line:
                continue
            var, value = line.split("=", 1)
            result[var] = _strip_legacy_quotes(value) if strip_quotes else value
    return result


def _default_global_cfg() -> str:
    """Path to the default global config file (``XPTerrainBuilder.cfg``),
    after the data root's one-time hand-over (:mod:`O4_Config_Names`)."""
    CN.adopt_global_cfg()
    return CN.global_cfg_path()


def _write_atomic_with_backup(path: str, data: dict,
                              keep_existing_backup: bool = False) -> None:
    """Write ``key=value`` lines to *path* atomically, backing up any prior file.

    Parent directories are created as needed.  The new content is fully
    staged in a temporary file, an existing file at *path* is COPIED to
    ``path + ".bak"``, and only then is the staged file moved into place
    with :func:`os.replace`.

    THE BACKUP IS A COPY, NOT A RENAME (2026-09-13a): renaming the cfg
    away first leaves *path* ABSENT for an instant, and a concurrent
    reader that finds no global cfg does not wait — ``O4_Config_Utils``
    RECREATES it from registry defaults, silently discarding the user's
    settings.  Since the retired-key cleanup made every cfg READ a
    potential writer, parallel tile-build workers open this file at the
    same moment by construction.  Copy-then-replace leaves no instant
    where the cfg does not exist.
    """
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding=TEXT.WRITE_ENCODING, newline="\n") as f:
        for key, value in data.items():
            f.write(key + "=" + str(value) + "\n")
    if os.path.isfile(path) and not (keep_existing_backup
                                     and os.path.isfile(path + ".bak")):
        shutil.copy2(path, path + ".bak")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Global config
# ---------------------------------------------------------------------------
def read_global_raw(cfg_file: str | None = None) -> dict:
    """Return the raw ``{key: value}`` contents of the global config file.

    :param cfg_file: path to read; defaults to ``XPTerrainBuilder.cfg``.
    :returns: parsed dict (``{}`` when the file is missing).
    """
    if cfg_file is None:
        cfg_file = _default_global_cfg()
    return _parse_cfg(cfg_file)


def write_global(values: dict, cfg_file: str | None = None) -> None:
    """Merge *values* into the global config file and write it back.

    Existing keys keep their order and any unknown keys are preserved
    (pass-through) — with ONE exception: a RETIRED key is dropped, never
    written back (owner RULINGS 2026-09-13a (2); preserving it is what
    made a stale global key nag forever).  New keys are appended in
    *values* iteration order.  The prior file is backed up to
    ``cfg_file + ".bak"``.

    :raises ValueError: if any key in *values* is a known preference
        (scope ``"pref"``), which does not belong in the global config file.
    """
    if cfg_file is None:
        cfg_file = _default_global_cfg()
    for key in values:
        setting = _BY_NAME.get(key)
        if setting is not None and setting.scope == "pref":
            raise ValueError(
                "%r is a preference and cannot be written to the global "
                "config file" % (key,)
            )
    data = _parse_cfg(cfg_file)
    for key in [k for k in data if k in O4_Cfg_Vars.retired_cfg_keys]:
        del data[key]
    for key, value in values.items():
        data[key] = str(value)
    _write_atomic_with_backup(cfg_file, data)


# ---------------------------------------------------------------------------
# Tile config
# ---------------------------------------------------------------------------
def _tile_cfg_path(lat: int, lon: int, custom_build_dir: str) -> str:
    """Return the path to the per-tile config file, after the tile's
    one-time hand-over from the Ortho4XP name (:mod:`O4_Config_Names`)."""
    build_dir = FNAMES.build_dir(lat, lon, custom_build_dir)
    CN.adopt_tile_cfg(build_dir, lat, lon)
    return CN.tile_cfg_path(build_dir, lat, lon)


def read_tile_raw(lat: int, lon: int, custom_build_dir: str) -> dict | None:
    """Return the raw ``{key: value}`` contents of a tile config file.

    Only this app's ``XPTerrainBuilder_+XX+YYY.cfg`` is read; an Ortho4XP
    tile config beside it is ignored (owner RULINGS 2026-10-26c).  The
    stamp line itself is NOT a setting and never appears in the returned
    mapping.

    :returns: parsed dict, or ``None`` when the tile config file is absent.
    """
    path = _tile_cfg_path(lat, lon, custom_build_dir)
    if not os.path.isfile(path):
        return None
    data = _parse_cfg(path)
    data.pop(CFG_STAMP_KEY, None)
    return data


# Vars whose value is never taken from the caller-supplied ``values`` and is
# preserved from the existing tile file when present.
_TILE_PRESERVED = ("zone_list", "default_website", "default_zl")


def values_equivalent(name: str, first: str, second: str) -> bool:
    """Whether two raw strings mean the same value for setting *name*.

    Comparison happens on the coerce-normalized forms so ``25000`` and
    ``25000.0`` are one value for a float setting — otherwise the sparse
    override diffing would store phantom overrides.  Unknown names or
    non-coercible values fall back to plain string equality.
    """
    if first == second:
        return True
    try:
        ok_first, normalized_first, _ = coerce(name, first)
        ok_second, normalized_second, _ = coerce(name, second)
    except KeyError:
        return False
    if ok_first and ok_second:
        return normalized_first == normalized_second
    return False


def global_effective_value(name: str, global_cfg: dict | None = None) -> str:
    """The value a tile INHERITS for *name*: global config, else default.

    :param global_cfg: pre-parsed global config (re-read when omitted).
    """
    if global_cfg is None:
        global_cfg = read_global_raw()
    if name in global_cfg:
        return global_cfg[name]
    return str(O4_Cfg_Vars.cfg_vars[name]["default"])


def sparse_tile_values(values: dict, *, always_keep: tuple = (),
                       global_cfg: dict | None = None) -> dict:
    """THE sparse-tile-cfg rule, one implementation (owner ruling
    RULINGS 2026-09-18a (1)): a tile cfg carries ONLY the keys whose value
    DIFFERS from what the tile would inherit — the global config file,
    else the registry default — plus the build-provenance keys in
    *always_keep* (``zone_list`` and friends), which are written verbatim
    and never diffed away.

    *values* maps tile var -> candidate value (anything ``str()`` renders);
    a var absent from it stays inherited.  Output preserves
    ``list_tile_vars`` order so cfg files stay diffable.

    Both writers go through here: :func:`write_tile` (the settings window /
    app tile-scope edits) and ``O4_Config_Utils.Tile.write_to_config``
    (the build).  Before 2026-09-18 the build wrote EVERY tile var, which
    froze the whole settings frame per tile and made the frozen value beat
    the global an app checkbox writes — BETA2 GEN-1 (``modify_custom_airports``
    stuck True on 23 tiles) and the same class as ``color_harmonization``.

    :raises ValueError: if any key in *values* is not a tile var.
    """
    tile_vars = O4_Cfg_Vars.list_tile_vars
    for key in values:
        if key not in tile_vars:
            raise ValueError("%r is not a tile config var" % (key,))
    if global_cfg is None:
        global_cfg = read_global_raw()
    out: dict = {}
    for var in tile_vars:
        if var not in values:
            continue
        candidate = str(values[var])
        if var in always_keep:
            out[var] = candidate
            continue
        if values_equivalent(
            var, candidate, global_effective_value(var, global_cfg)
        ):
            continue  # equal to inherited: no override to store
        out[var] = candidate
    return out


# ---------------------------------------------------------------------------
# THE STAMP, and the move rule for an UNSTAMPED (pre-1.0.352) tile cfg
# (owner RULINGS 2026-09-18c (2))
# ---------------------------------------------------------------------------
#: The stamp key itself lives in the registry (beside the live keys, so a
#: reader never looks in two places); re-exported here because every
#: writer and reader of a tile cfg goes through this module.
CFG_STAMP_KEY = O4_Cfg_Vars.cfg_stamp_key

#: Re-exported for the callers that knew it here (:mod:`O4_Config_Names`).
PRE_STAMP_BACKUP_SUFFIX = CN.PRE_STAMP_BACKUP_SUFFIX


def cfg_stamp_value() -> str:
    """What this build writes as the stamp value.

    The app version when the artifact carries one (``VERSION.txt`` beside
    a frozen engine or an app bundle — :mod:`O4_Build_Info`), else
    ``engine-<engine version>`` for a development tree or a bare engine
    checkout, which has no app version at hand.  Only the stamp's
    PRESENCE is read (the library's "built here", the hand-over of an
    ``Ortho4XP_`` named file this app wrote), so either form is a lawful
    stamp; the value is provenance for a bug report.
    """
    try:
        import O4_Build_Info                      # noqa: PLC0415 — lazy
        info = O4_Build_Info.build_info()
    except Exception:
        return "unknown"
    if info.app and info.app != O4_Build_Info.DEV:
        return info.app
    return "engine-" + (info.engine or "dev")


def tile_cfg_stamp_line() -> str:
    """THE stamp line, for a writer that renders cfg text itself.

    One helper, so a test fixture that hand-writes a tile cfg stamps it
    the same way the engine does rather than re-spelling the key.
    """
    return CFG_STAMP_KEY + "=" + cfg_stamp_value() + "\n"


def is_stamped(data: dict) -> bool:
    """Whether a parsed tile cfg was written by a stamping build."""
    return bool(str(data.get(CFG_STAMP_KEY, "")).strip())


def write_tile_cfg(path: str, values: dict) -> None:
    """Write a tile cfg (already-sparse *values*) WITH the stamp.

    Both tile-cfg writers go through here — :func:`write_tile` and
    ``O4_Config_Utils.Tile.write_to_config`` — so every tile cfg this
    engine emits carries :data:`CFG_STAMP_KEY`: provenance for a bug
    report and the library's "built here" witness.
    The stamp is written FIRST so the shape is obvious in a diff.
    """
    out = {CFG_STAMP_KEY: cfg_stamp_value()}
    for key, value in values.items():
        if key == CFG_STAMP_KEY:
            continue
        out[key] = value
    _write_atomic_with_backup(path, out)


def write_tile(lat: int, lon: int, custom_build_dir: str, values: dict) -> None:
    """Write the tile config file as SPARSE OVERRIDES (blended model).

    Only settings that DIFFER from the value the tile would inherit (the
    global config value, else the registry default) are written — every
    other setting is pulled from global, live, at build time
    (``O4_Config_Utils.Tile`` seeds every var from the global scope and
    the tile file overwrites only the keys it contains).  Consequences:

    * Setting a var to exactly its inherited value REMOVES the override.
    * Legacy full-snapshot tile configs shrink to their true differences
      on their next write (reads of either format behave identically).
    * ``zone_list`` / ``default_website`` / ``default_zl`` are build
      provenance, not settings: they are preserved verbatim from the
      existing file (never taken from *values*, never diffed away).

    Value resolution per var: *values* when present, else the existing
    tile file value; a var in neither stays inherited.  An existing file
    is backed up to ``*.cfg.bak``; the write is atomic and parent
    directories are created as needed.

    :raises ValueError: if any key in *values* is not a tile var.
    """
    tile_vars = O4_Cfg_Vars.list_tile_vars
    for key in values:
        if key not in tile_vars:
            raise ValueError("%r is not a tile config var" % (key,))
    path = _tile_cfg_path(lat, lon, custom_build_dir)
    file_exists = os.path.isfile(path)
    existing = _parse_cfg(path) if file_exists else {}
    global_cfg = read_global_raw()

    resolved: dict = {}
    for var in tile_vars:
        if var in _TILE_PRESERVED:
            if file_exists and var in existing:
                resolved[var] = existing[var]
            continue
        if var in values:
            resolved[var] = str(values[var])
        elif var in existing:
            resolved[var] = existing[var]
    out = sparse_tile_values(resolved, always_keep=_TILE_PRESERVED,
                             global_cfg=global_cfg)
    write_tile_cfg(path, out)


# ---------------------------------------------------------------------------
# Legacy per-tile configs (written by an older or different Ortho4XP)
# ---------------------------------------------------------------------------
#: What a modernised tile config KEEPS — the tile's identity rather than
#: its settings: which imagery source it was built from, at which zoom
#: level, and the zones the user drew by hand.  Everything else falls
#: back to the current global config, exactly as for a tile created today.
LEGACY_KEPT_KEYS = ("default_website", "default_zl", "zone_list")


def legacy_tile_settings(lat: int, lon: int,
                         custom_build_dir: str) -> dict | None:
    """What an older version of this app left in this tile's config.

    Only this app's own ``XPTerrainBuilder_+XX+YYY.cfg`` is inspected: an
    Ortho4XP config (``Ortho4XP_+XX+YYY.cfg`` or the generic
    ``Ortho4XP.cfg``) is ignored, never modernised or moved (owner
    RULINGS 2026-10-26c).  Reports only what this engine INTERPRETS rather
    than takes literally, so a front end can offer to modernise the file:

    ``foreign_enums``
        ``(key, value, replacement)`` for enum values this version does
        not define; ``replacement`` is what an update would write (the
        current global value, else the registry default).
    ``quoted_keys``
        keys carrying legacy quoted values (``'Arc'``).
    ``missing_pins``
        ``custom_dem`` pins whose file no longer exists.

    ``None`` when there is nothing to say (or no config at all).
    """
    cfg_path = _tile_cfg_path(lat, lon, custom_build_dir)
    if not os.path.isfile(cfg_path):
        return None
    raw = _parse_cfg(cfg_path, strip_quotes=False)
    global_cfg = read_global_raw()
    quoted_keys: list = []
    foreign_enums: list = []
    missing_pins: list = []
    for (key, written) in raw.items():
        written = written.strip()
        bare = _strip_legacy_quotes(written)
        if bare != written:
            quoted_keys.append(key)
        if key == "custom_dem":
            for token in bare.split(";"):
                token = token.strip()
                if token.startswith("/") and not os.path.isfile(token):
                    missing_pins.append(token)
            continue
        variable = O4_Cfg_Vars.cfg_vars.get(key)
        if variable is None or variable.get("type") is not str:
            continue
        allowed = variable.get("values")
        bare = _normalize_legacy_mode_value(key, bare)
        if allowed and bare not in allowed:
            replacement = _strip_legacy_quotes(
                str(global_cfg.get(key, variable["default"])).strip()
            )
            foreign_enums.append((key, bare, replacement))
    if not (foreign_enums or quoted_keys or missing_pins):
        return None
    return {
        "lat": lat,
        "lon": lon,
        "cfg_path": cfg_path,
        "foreign_enums": sorted(foreign_enums),
        "quoted_keys": sorted(quoted_keys),
        "missing_pins": sorted(missing_pins),
    }


def update_legacy_tile_settings(legacy: dict, custom_build_dir: str) -> str:
    """Reduce a legacy tile config to the tile's IDENTITY.

    Effectively "delete the tile config", except that the keys other
    features rely on (source adoption, the imagery audit, the mismatch
    guard) and the user's hand-drawn zones survive: everything else falls
    back to the current global defaults.  The original file is kept as
    ``*.cfg.bak``.

    Returns the path written.  Takes the mapping
    :func:`legacy_tile_settings` returned, never a hand-built one.
    """
    (lat, lon) = (int(legacy["lat"]), int(legacy["lon"]))
    source = _parse_cfg(legacy["cfg_path"])
    kept = {
        key: source[key] for key in LEGACY_KEPT_KEYS if key in source
    }
    destination = _tile_cfg_path(lat, lon, custom_build_dir)
    write_tile_cfg(destination, kept)
    return destination


# Tile-scope settings most commonly customized per tile (the pinned
# "This tile" section of the blended settings window): texture source
# mode, elevation quality, the coastline lidar band, road detail, the
# coastline mask blur, and the airport imagery zoom.
CURATED_TILE_SETTINGS = (
    "texture_mode",
    "elevation_level",
    "airport_elevation_level",
    "elevation_coastline_band_km",
    "road_level",
    "masks_width",
    "cover_zl",
)


def effective_tile_settings(
    lat: int, lon: int, custom_build_dir: str
) -> dict:
    """Blended view of every tile-scope setting for one tile.

    :returns: ``{name: (value, origin)}`` for each tile-scope setting in
        the window registry, where origin is ``"tile"`` (overridden in
        the tile file — present AND different from the inherited value,
        so legacy full-snapshot files report only true differences),
        ``"global"`` (inherited from the global config file) or
        ``"default"`` (inherited from the registry default).
    """
    tile_raw = read_tile_raw(lat, lon, custom_build_dir) or {}
    global_cfg = read_global_raw()
    blended = {}
    for setting in settings():
        if setting.scope != "tile":
            continue
        inherited = global_effective_value(setting.name, global_cfg)
        tile_value = tile_raw.get(setting.name)
        if tile_value is not None and not values_equivalent(
            setting.name, tile_value, inherited
        ):
            blended[setting.name] = (tile_value, "tile")
        elif setting.name in global_cfg:
            blended[setting.name] = (inherited, "global")
        else:
            blended[setting.name] = (inherited, "default")
    return blended


def tile_override_names(
    lat: int, lon: int, custom_build_dir: str
) -> tuple:
    """Names of the settings genuinely customized on this tile."""
    return tuple(
        name
        for name, (_value, origin) in effective_tile_settings(
            lat, lon, custom_build_dir
        ).items()
        if origin == "tile"
    )


def autodetect_cifp(xplane_dir: str) -> str:
    """The CIFP/AIRAC data folder inside an X-Plane installation, or ``""``.

    ``Custom Data/CIFP`` (Navigraph or other AIRAC updates) wins over the
    stock ``Resources/default data/CIFP``. Both UIs seed ``cifp_data_path``
    from this when the X-Plane folder is chosen.
    """
    if not xplane_dir:
        return ""
    for candidate in (
        os.path.join(xplane_dir, "Custom Data", "CIFP"),
        os.path.join(xplane_dir, "Resources", "default data", "CIFP"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return ""


#: What makes a folder a USABLE X-Plane installation for this app (beta
#: plan §1 B2).  ``Custom Scenery`` is where a finished tile installs;
#: ``Resources/default data/CIFP`` is X-Plane's own stock AIRAC corpus and
#: is what makes auto-patching possible without a Navigraph subscription.
#: A folder missing either one is not an install we can build against, and
#: BOTH UIs validate against exactly this tuple — one spelling.
XPLANE_REQUIRED_SUBDIRS = ("Custom Scenery", "Resources/default data/CIFP")


def xplane_install_problem(xplane_dir: str) -> str | None:
    """``None`` when ``xplane_dir`` is a usable X-Plane install, else why not.

    The returned string is USER-FACING copy: both the Qt wizard and the
    Swift first-run page show it verbatim under the folder field.
    """
    xplane_dir = (xplane_dir or "").strip()
    if not xplane_dir:
        return "No X-Plane folder set."
    if not os.path.isdir(xplane_dir):
        return "%s is not a folder." % xplane_dir
    missing = [sub for sub in XPLANE_REQUIRED_SUBDIRS
               if not os.path.isdir(os.path.join(xplane_dir, *sub.split("/")))]
    if missing:
        return ("This folder has no %s — is it really an X-Plane install?"
                % " and no ".join("%s/" % m for m in missing))
    return None


def resolve_cifp_dir(cifp_data_path: str, custom_scenery_dir: str) -> str:
    """The CIFP directory a tile build will ACTUALLY read, or ``""``.

    ONE spelling of the resolution ``O4_Vector_Map.run_auto_patch_generation``
    performs and ``tools/harness/build_airport.py`` enforces:

    * a non-empty ``cifp_data_path`` is authoritative — if it is not a
      directory the answer is ``""`` (a typo must refuse, never silently
      fall back to some other corpus);
    * an EMPTY ``cifp_data_path`` falls back to :func:`autodetect_cifp`
      on the X-Plane root above ``custom_scenery_dir``.
    """
    cifp_data_path = (cifp_data_path or "").strip()
    if cifp_data_path:
        return cifp_data_path if os.path.isdir(cifp_data_path) else ""
    custom_scenery_dir = (custom_scenery_dir or "").strip()
    if not custom_scenery_dir:
        return ""
    return autodetect_cifp(
        os.path.dirname(os.path.normpath(custom_scenery_dir)))


def cifp_refusal_reason(cifp_data_path: str, custom_scenery_dir: str,
                        auto_patch_mode: str = "ICAO") -> str | None:
    """``None`` when auto-patch may run, else THE refusal text naming the key.

    The law (beta plan §1 B2): with auto-patch ENABLED and no CIFP
    directory resolving, the tile build must FAIL — it used to print a
    loud warning and then build every airport on the raw DEM, exiting 0.
    An explicitly disabled auto-patch (``auto_patch=None``) still builds.
    """
    if not auto_patch_mode or str(auto_patch_mode) == "None":
        return None
    if resolve_cifp_dir(cifp_data_path, custom_scenery_dir):
        return None
    given = (cifp_data_path or "").strip()
    if given:
        detail = "cifp_data_path=%r is not a directory" % given
    else:
        detail = ("cifp_data_path is empty and no CIFP folder was found "
                  "under the X-Plane install above custom_scenery_dir=%r"
                  % ((custom_scenery_dir or "").strip(),))
    return ("auto_patch=%s but NO CIFP data resolves: %s. Every airport "
            "on this tile would drape over the raw DEM — runways, taxiways "
            "and aprons ungraded. Set cifp_data_path to X-Plane's "
            "'Resources/default data/CIFP' (or a Navigraph 'Custom "
            "Data/CIFP'), or set auto_patch=None to build without airport "
            "grading on purpose." % (auto_patch_mode, detail))


def elevation_source_options() -> list[str]:
    """Choices for ``base_elevation_source``: ``auto``, the legacy keywords,
    then every shipped elevation provider definition
    (``Providers/Elevation/<CODE>.elv``), sorted.

    The registry cannot list these (they are files), so both UIs build the
    dropdown from this enumeration.
    """
    options = ["auto", "View", "SRTM", "NED1", "NED1/3", "ALOS"]
    elv_dir = os.path.join(FNAMES.Provider_dir, "Elevation")
    try:
        for entry in sorted(os.listdir(elv_dir)):
            if entry.endswith(".elv"):
                code = entry[:-4]
                if code not in options:
                    options.append(code)
    except OSError:
        pass
    return options


# ---------------------------------------------------------------------------
# Value validation / normalisation
# ---------------------------------------------------------------------------
def _normalize_legacy_mode_value(name: str, normalized: str) -> str:
    """Map a legacy scalar of a mode-valued setting onto its enum value.

    ``airport_elevation_insets`` was a bool until 2026-09-18 and
    ``auto_patch`` before that; existing config files, older front ends and
    older JSONL clients still send ``True``/``False``.  Mapping them HERE —
    in the one coercion every reader (validator, ``values_equivalent``, the
    sparse-tile rule, ``tile_settings_write``, the legacy-enum report)
    already goes through — is what stops the foreign-enum rule from seeing
    ``"False"`` ∉ ``values`` and silently REPLACING a user's per-tile Off
    with the global (RULINGS 2026-09-18e; spec §A.5).

    A value already in ``values``, and any non-mode setting, is returned
    unchanged.
    """
    from O4_Airport_Modes import DEFAULT_MODE, normalize_mode

    if name not in DEFAULT_MODE:
        return normalized
    variable = O4_Cfg_Vars.cfg_vars.get(name) or {}
    allowed = variable.get("values") or ()
    if normalized in allowed:
        return normalized
    mapped = normalize_mode(normalized, name)
    # Garbage must still FAIL validation rather than silently become the
    # default: only a recognised legacy token is rewritten.
    if normalized.strip() in ("True", "true", "1", "False", "false", "0"):
        return mapped
    return normalized


def coerce(name: str, text: str) -> tuple:
    """Validate and normalise *text* against the setting *name*'s type.

    :returns: ``(ok, normalized, error)`` — on success ``ok`` is ``True``,
        ``normalized`` is the canonical string form and ``error`` is ``""``;
        on failure ``ok`` is ``False``, ``normalized`` echoes the input and
        ``error`` is a human-readable message.
    :raises KeyError: if *name* is not a known setting.
    """
    setting = get_setting(name)
    if setting.scope == "pref":
        return (True, text, "")

    vtype = setting.vtype
    if vtype is bool:
        token = text.strip()
        if token in ("True", "true", "1"):
            normalized = "True"
        elif token in ("False", "false", "0"):
            normalized = "False"
        else:
            return (False, text, "Expected a boolean (True/False), got %r" % (text,))
    elif vtype is int:
        try:
            normalized = str(int(text.strip()))
        except (ValueError, TypeError):
            return (False, text, "Expected an integer, got %r" % (text,))
    elif vtype is float:
        try:
            normalized = str(float(text.strip()))
        except (ValueError, TypeError):
            return (False, text, "Expected a number, got %r" % (text,))
    elif vtype is list:
        try:
            parsed = ast.literal_eval(text.strip())
        except (ValueError, SyntaxError):
            return (False, text, "Expected a list, got %r" % (text,))
        if isinstance(parsed, bool):
            return (False, text, "Expected a list, got %r" % (text,))
        if isinstance(parsed, list):
            normalized = str(parsed)
        elif isinstance(parsed, (int, float)):
            # Legacy quirk: e.g. ``masks_width=100`` is a bare number.
            normalized = str(parsed)
        else:
            return (False, text, "Expected a list, got %r" % (text,))
    else:  # str
        normalized = text.strip()
        normalized = _normalize_legacy_mode_value(name, normalized)

    if setting.values and normalized not in setting.values:
        return (
            False, text,
            "%r is not one of: %s" % (normalized, ", ".join(setting.values)),
        )
    return (True, normalized, "")


# ---------------------------------------------------------------------------
# Runtime application
# ---------------------------------------------------------------------------
def apply_runtime(values: dict) -> list:
    """Apply *values* to the running process via ``O4_Config_Utils``.

    For each setting the module-level variable is updated through
    ``set_global_variables``; tile-scoped settings additionally get their
    ``global_``-prefixed mirror set (matching the legacy loader).  Preference
    settings are skipped silently.

    :returns: the list of setting names that failed to apply.
    """
    import O4_Config_Utils as CFG  # lazy: heavy imports + file side effects

    prefix = O4_Cfg_Vars.global_prefix
    failed: list = []
    for name, value in values.items():
        setting = _BY_NAME.get(name)
        if setting is not None and setting.scope == "pref":
            continue
        try:
            CFG.set_global_variables(name, value)
            if setting is not None and setting.scope == "tile":
                CFG.set_global_variables(prefix + name, value)
        except Exception:
            failed.append(name)
    return failed
