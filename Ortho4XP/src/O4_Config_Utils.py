"""Ortho4XP configuration state: defaults, config file parsing and the Tile class."""

from __future__ import annotations

import ast
import logging
import os

import O4_Cfg_Module_Values as MODULE_VALUES
import O4_Cfg_Vars as CFG
import O4_Config_Names as CONFIG_NAMES
import O4_File_Names as FNAMES
import O4_Text_Files as TEXT
import O4_UI_Utils as UI
import O4_Unmounted_Links as UNMOUNTED
from O4_Cfg_Vars import (
    cfg_app_vars,
    cfg_global_tile_vars,
    cfg_tile_vars,
    cfg_vars,
    global_prefix,
    gui_app_vars_long,
    gui_app_vars_short,
    list_app_vars,
    list_cfg_vars,
    list_dsf_vars,
    list_global_dsf_vars,
    list_global_mask_vars,
    list_global_mesh_vars,
    list_global_tile_vars,
    list_global_vector_vars,
    list_mask_vars,
    list_mesh_vars,
    list_tile_vars,
    list_vector_vars,
    cfg_stamp_key,
    cleanup_retired_cfg_keys,
    legacy_cfg_value,
    _legacy_cfg_reported,
    retired_cfg_keys,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)
handler = logging.StreamHandler()
_LOGGER.addHandler(handler)

# THIS APP'S OWN GLOBAL (owner RULINGS 2026-10-26c): XPTerrainBuilder.cfg;
# Ortho4XP.cfg is never read, written, moved or copied (O4_Config_Names).
global_cfg_file = CONFIG_NAMES.global_cfg_path()
global_cfg_bak_file = global_cfg_file + ".bak"


def set_global_variables(var: str, value: str) -> None:
    """
    Set global Python variables for the application.
    
    :param str var: variable name
    :param str value: value for variable
    :returns: None
    """
    # There are no global_* variables for the app config settings so skip them
    if var.startswith(global_prefix):
        var_without_global = var[len(global_prefix):]
        if var_without_global in cfg_app_vars:
            return
    if cfg_vars[var]["type"] in (bool, list):
        _assign(var, ast.literal_eval(value))
    else:
        _assign(var, cfg_vars[var]["type"](value))


def _assign(var: str, value) -> None:
    """Set config variable ``var``: on the module its ``"module"`` alias
    names (``O4_Cfg_Module_Values``), else on this module."""
    if "module" in cfg_vars[var]:
        MODULE_VALUES.assign(cfg_vars[var]["module"], var, value)
    else:
        globals()[var] = value


def __getattr__(name: str):
    """``getattr(O4_Config_Utils, "IMG")`` — the module a ``"module"``
    alias names (``o4_engine.command_process`` and ``O4_Step_Reuse`` read
    settings so)."""
    if name in MODULE_VALUES.MODULES:
        return MODULE_VALUES.holder(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def config_compatibility(value) -> str:
    """
    Check for compatibility with config files from version <= 1.20.
    
    :param str value: value to check
    :returns: value in format based on cfg_vars
    :return type: str
    """
    if value and value[0] in ('"', "'"):
        value = value[1:]
    if value and value[-1] in ('"', "'"):
        value = value[:-1]
    return value

################################################################################
# Initialization to default values
# Some variables are set using simply their name
# Others are set using the module name and the variable name because
# they are defined in a different module and overriden when the config is loaded (below)
# hence the reason this module is imported last (see Ortho4XP.py)
for var in cfg_vars:
    _assign(var, cfg_vars[var]["default"])

################################################################################
# Config keys of retired settings, recognised so configs written by older
# versions load without noise.  airport_elevation_inset_resolution_m was
# superseded by airport_elevation_level (2026-07-24).
RETIRED_CFG_KEYS = tuple(retired_cfg_keys)

################################################################################
# Update from the global XPTerrainBuilder.cfg
try:
    f = TEXT.open_supplied(global_cfg_file, legacy_ansi=True)
    for line in f.readlines():
        line = line.strip()
        if not line:
            continue
        if line[0] == "#":
            continue
        try:
            (var, value) = line.split("=", 1)
            if var in RETIRED_CFG_KEYS:
                # A key from an older version: skipped here and DELETED
                # from the file after the read (the cleanup below,
                # owner RULINGS 2026-09-13a (2)) — never reported as an
                # invalid line, never a warning.
                continue
            value = config_compatibility(value)
            # Set all tile and app config variables
            set_global_variables(var, value)
            # Set all global tile config variables
            var = global_prefix + var
            set_global_variables(var, value)
        except:
            UI.lvprint(1, "Global config file contains an invalid line:", line)
            pass
    f.close()
    # THE CLEANUP (owner RULINGS 2026-09-13a (2)): the global reader and
    # the tile reader share it — a retired key is removed from the file
    # it was read from and reported once, never warned about forever.
    for _info in cleanup_retired_cfg_keys(global_cfg_file):
        UI.lvprint(0, "   INFO:", _info)
except FileNotFoundError:
    # Create a new global config file using default values
    os.makedirs(os.path.dirname(global_cfg_file), exist_ok=True)
    with open(global_cfg_file, "w", encoding=TEXT.WRITE_ENCODING,
              newline="\n") as file:
        for var, value in cfg_global_tile_vars.items():
            # Remove global_ prefix from cfg_global_tile_vars since that's not
            # how they are stored in the global config file
            _var = var.replace(global_prefix, "")
            file.write(_var + "=" + str(value["default"]) + "\n")
        for var, value in cfg_app_vars.items():
            file.write(var + "=" + str(value["default"]) + "\n")
    _LOGGER.info("No global config file found. New config created using defaults.")
except Exception as e:
    _LOGGER.error("Error accessing global config file: %s", e)


#: The tile settings a build request may set for that build only (#818).
BUILD_OVERRIDE_KEYS = ("auto_patch", "modify_custom_airports")


################################################################################
class Tile:
    """Class for building tiles."""
    def __init__(self, lat, lon, custom_build_dir):

        self.lat = lat
        self.lon = lon
        self.custom_build_dir = custom_build_dir
        self.grouped = (
            True
            if custom_build_dir and not custom_build_dir.endswith(("/", "\\"))
            else False
        )
        self.build_dir = FNAMES.build_dir(lat, lon, custom_build_dir)
        self.dem = None
        for var in list_tile_vars:
            exec("self." + var + "=" + var)

    def apply_build_overrides(self, overrides):
        """Land a build request's per-build switches on this tile (#818).

        The Build pane's "Grade airports" and "Fit custom airport
        buildings" toggles change THIS build only: the value read from the
        cfg layers is kept aside, and :meth:`write_to_config` writes that
        kept value, so the tile's own cfg never learns the override.  Off
        grades nothing (``auto_patch`` "None"); on keeps the tile's own
        mode, or grades every airport when that mode is "None".  Keys
        other than :data:`BUILD_OVERRIDE_KEYS` and non-bool values are
        ignored.
        """
        from O4_Airport_Modes import resolved_auto_patch_mode

        saved = self.__dict__.setdefault("_build_override_saved", {})
        for key, value in (overrides or {}).items():
            if key not in BUILD_OVERRIDE_KEYS or not isinstance(value, bool):
                continue
            saved.setdefault(key, getattr(self, key))
            if key == "auto_patch":
                if not value:
                    value = "None"
                elif resolved_auto_patch_mode(self) == "None":
                    value = "All"
                else:
                    continue
            setattr(self, key, value)

    def make_dirs(self):
        self._check_elevation_folder()
        if os.path.isdir(self.build_dir):
            if not os.access(self.build_dir, os.W_OK):
                UI.vprint(
                    0,
                    "OS error: Tile directory",
                    self.build_dir,
                    " is write protected.",
                )
                raise Exception
        elif (found := UNMOUNTED.dangling_link(self.build_dir)):
            # A DANGLING LINK on the tile dir (or a folder above it), not a
            # permissions problem: an external volume left unmounted is
            # the everyday cause (found in the wild 2026-09-16, VHHH; and
            # #668).  os.makedirs would raise FileExistsError here, which
            # said nothing.  The typed exception carries the link, its
            # target and the drive to the user's message.
            error = UNMOUNTED.UnmountedLink(found)
            UI.vprint(0, "OS error: Tile directory is a symlink whose "
                      "target is missing:", found["link"], "->",
                      found["target"] or "?", "(is the volume mounted?)")
            raise error
        else:
            try:
                os.makedirs(self.build_dir)
            except OSError as e:
                UI.vprint(
                    0,
                    "OS error: Cannot create tile directory",
                    self.build_dir,
                    " check file permissions:",
                    e,
                )
                raise Exception

    def _check_elevation_folder(self):
        """Refuse a tile whose ``Elevation_data/<bucket>`` folder is a
        dangling link (#1167): every ``os.makedirs`` under it raised
        FileExistsError/FileNotFoundError, which named nothing.  The link
        is left alone; the message names it and its missing target."""
        bucket = os.path.join(FNAMES.Elevation_dir,
                              FNAMES.round_latlon(self.lat, self.lon))
        try:
            UNMOUNTED.check_elevation_folder(bucket)
        except UNMOUNTED.ElevationLinkBroken as error:
            UI.vprint(0, "OS error: elevation folder is a symlink whose "
                      "target is missing:", error.failure_params["link"],
                      "->", error.failure_params["target"] or "?")
            raise

    def _tile_cfg_path(self):
        """This tile's own config file path (build dir + this app's
        ``XPTerrainBuilder_+XX+YYY.cfg``; never Ortho4XP's)."""
        return CONFIG_NAMES.tile_cfg_path(self.build_dir, self.lat, self.lon)

    def read_from_config(self, config_file=None, use_global=False):
        """
        Read tile config and update class variables — LAYERED.

        The value a tile var resolves to is, in order of precedence:

        1. the tile's own config file (``XPTerrainBuilder_+XX+YYY.cfg`` in
           the build dir, or *config_file* when given) — only the keys it
           actually carries;
        2. the global ``XPTerrainBuilder.cfg`` — again only the keys it
           carries;
        3. whatever the instance already holds: ``__init__`` seeds every
           tile var from this module's globals, i.e. the global config
           as loaded at import PLUS any in-memory session settings a
           front end applied since (``O4_Settings_Model.apply_runtime``);
        4. the registry default (what those globals start from).

        Tile configs are SPARSE OVERRIDES (``O4_Settings_Model.write_tile``,
        the blended model): a key absent from a tile file means "inherit",
        never "keep whatever this instance happened to carry".  The
        pre-2026-09-04 reader opened EITHER the tile file OR the global
        one, so a tile cfg written before a setting existed (the owner's
        −13-077 / −13-078 tiles, cfgs from July, carrying no line for a
        setting added after they were written) resolved that setting to the registry default while a tile
        with no cfg at all resolved it from the global — two tiles in one
        build, one global setting, two engines.  One reader now serves the
        engine CLI (``Ortho4XP.py lat lon``), the JSONL session and the
        parallel worker children alike.

        :params str config_file: explicit tile config path (still layered
            over the global config)
        :params bool use_global: read ONLY the global config file

        :returns: 1 if at least one config file was read, 0 if not
        :return type: int
        """
        if use_global:
            layers = [global_cfg_file]
        else:
            # THE TILE'S ONE-TIME HAND-OVER (owner RULINGS 2026-10-26c,
            # amending 2026-09-18c), before the tile layer is read: a
            # stamped Ortho4XP_ named cfg this app wrote takes this app's
            # name, and an Ortho4XP cfg 09-18c moved to *.pre352.bak goes
            # back.  An Ortho4XP tile cfg is never read for settings.
            if not config_file:
                for _info in CONFIG_NAMES.adopt_tile_cfg(
                        self.build_dir, self.lat, self.lon):
                    UI.lvprint(0, "   INFO:", _info)
            tile_cfg = config_file or self._tile_cfg_path()
            layers = [global_cfg_file, tile_cfg]
        layers = [path for path in layers if os.path.isfile(path)]
        if not layers:
            UI.lvprint(
                0,
                "CFG error: No tile or global config file found.",
                FNAMES.short_latlon(self.lat, self.lon),
            )
            return 0
        for path in layers:
            if not self._apply_config_file(path):
                return 0
        return 1

    def _apply_config_file(self, config_file):
        """Overlay ONE ``key=value`` file onto this tile: only the keys the
        file carries change.  Retired keys are skipped and then DELETED
        from the file (owner RULINGS 2026-09-13a (2)), legacy quoting and
        foreign-fork values are normalised, unknown keys are ignored at
        verbosity 2.

        :returns: 1 on success, 0 when the file could not be read
        """
        try:
            f = TEXT.open_supplied(config_file, legacy_ansi=True)
            for line in f.readlines():
                line = line.strip()
                if not line:
                    continue
                if line[0] == "#":
                    continue
                try:
                    (var, value) = line.split("=", 1)
                    if var == cfg_stamp_key:
                        # THE STAMP (RULINGS 2026-09-18c (2)): provenance,
                        # not a setting.  Skipped explicitly so it is
                        # never reported as an unknown key, and left in
                        # the file so the cfg stays recognisably stamped.
                        continue
                    if var in retired_cfg_keys:
                        # RETIRED: a tile cfg carrying it loads, and the
                        # cleanup after the read DELETES the line (owner
                        # RULINGS 2026-09-13a (2)).  The generic handler
                        # below would have swallowed it as an unknown key
                        # at verbosity 2 — a setting that stopped being
                        # read must be visible, once.
                        continue
                    # compatibility with config files from version <= 1.20
                    value = config_compatibility(value)
                    # Values from other forks map to their closest
                    # equivalent here (registry-driven), loudly — never
                    # silently treated as "off".
                    # The cleanup after the read rewrites the line
                    # (#676), so the notice is printed once per run.
                    current = legacy_cfg_value(var, value)
                    if current is not None:
                        if (var, value) not in _legacy_cfg_reported:
                            _legacy_cfg_reported.add((var, value))
                            UI.vprint(
                                1,
                                "   Legacy config value", value, "for", var,
                                "read as", current + ".",
                            )
                        value = current
                    if cfg_vars[var]["type"] in (bool, list):
                        cmd = "self." + var + "=" + value
                    else:
                        cmd = (
                            "self."
                            + var
                            + "=cfg_vars['"
                            + var
                            + "']['type'](value)"
                        )
                    exec(cmd)
                except Exception as e:
                    # compatibility with zone_list config files from
                    # version <= 1.20
                    if "zone_list.append" in line:
                        try:
                            exec("self." + line)
                        except:
                            pass
                    else:
                        UI.vprint(2, e)
                        pass
            f.close()
            # THE CLEANUP (owner RULINGS 2026-09-13a (2)), the same one
            # the global reader runs: a retired key is deleted from the
            # cfg it was read from and reported once as INFO.
            for info in cleanup_retired_cfg_keys(config_file):
                UI.lvprint(0, "   INFO:", info)
            return 1
        except:
            UI.lvprint(
                0,
                "CFG error: Could not read config file for tile",
                FNAMES.short_latlon(self.lat, self.lon),
                "(" + str(config_file) + ")",
            )
            return 0

    def _tile_zones(self):
        """The zones the user drew that fall inside THIS tile."""
        tile_zones = []
        lat = self.lat + 1 if self.lat < 0 else self.lat
        lon = self.lon + 1 if self.lon < 0 else self.lon
        for zone in globals()["zone_list"]:
            _zone_list = set(int(coord) for coord in zone[0])
            if lat in _zone_list and lon in _zone_list:
                tile_zones.append(zone)
                _LOGGER.debug("Zones in tile found: %s", tile_zones)
        return tile_zones

    def write_to_config(self, config_file = None):
        """
        Write this tile's config file as SPARSE OVERRIDES.

        Owner ruling RULINGS 2026-09-18a (1), BETA2 GEN-1: a tile cfg
        carries ONLY the keys whose value differs from the GLOBAL layer
        (the global cfg file, else the registry default), plus its zones
        and build provenance.  Until 2026-09-18 this dumped EVERY
        ``list_tile_vars`` key, so each build froze the whole resolved
        settings frame into the tile file — and on the next build that
        frozen value BEAT the global the app checkbox writes
        (``read_from_config`` layers global then tile).  Any global-only
        app toggle was therefore dead on a tile that had ever been built:
        ``modify_custom_airports`` (GEN-1, all 23 of the owner's tile cfgs
        said True while the box was unchecked) and ``color_harmonization``
        were two instances of ONE defect.

        The diffing rule itself is not implemented here — it is
        ``O4_Settings_Model.sparse_tile_values``, the same function the
        settings window's ``write_tile`` uses.  One rule, one code path.

        :params str config_file: path to config file; unknown use case

        :returns: 1 if successful, 0 if not
        :return type: int
        """
        import O4_Settings_Model as SM
        if not config_file:
            config_file = self._tile_cfg_path()
        saved = self.__dict__.get("_build_override_saved", {})
        try:
            values = {}
            for var in list_tile_vars:
                if var == "zone_list":
                    values[var] = self._tile_zones()
                else:
                    # A per-build override is never the tile's own value.
                    values[var] = saved.get(var, getattr(self, var))
            out = SM.sparse_tile_values(
                values, always_keep=SM._TILE_PRESERVED,
                global_cfg=SM.read_global_raw(global_cfg_file))
            # Stamped (RULINGS 2026-09-18c (2)) — one writer helper, so a
            # cfg this build writes is never taken for a legacy one.
            SM.write_tile_cfg(config_file, out)
            return 1
        except Exception as e:
            UI.vprint(2, e)
            UI.lvprint(
                0,
                "CFG error: Could not write config file for tile",
                FNAMES.short_latlon(self.lat, self.lon),
            )
            return 0
