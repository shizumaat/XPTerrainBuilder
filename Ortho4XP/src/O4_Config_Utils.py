"""Ortho4XP configuration state: defaults, config file parsing and the Tile class."""

from __future__ import annotations

import logging
import os

import O4_Cfg_Vars as CFG
import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_OSM_Utils as OSM
import O4_Overlay_Utils as OVL
import O4_Tile_Utils as TILE
import O4_UI_Utils as UI
import O4_Vector_Map as VMAP
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
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)
handler = logging.StreamHandler()
_LOGGER.addHandler(handler)

global_cfg_file = FNAMES.data_path("Ortho4XP.cfg")
global_cfg_bak_file = FNAMES.data_path("Ortho4XP.cfg.bak")


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
    target = (
        cfg_vars[var]["module"] + "." + var
        if "module" in cfg_vars[var]
        else "globals()['" + var + "']"
        )
    if cfg_vars[var]["type"] in (bool, list):
        cmd = target + "=" + value
    else:
        cmd = target + "=cfg_vars['" + var + "']['type'](value)"
    exec(cmd)

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
    target = (
        cfg_vars[var]["module"] + "." + var
        if "module" in cfg_vars[var]
        else var
    )
    exec(target + "=cfg_vars['" + var + "']['default']")

################################################################################
# Config keys of retired settings, recognised so configs written by older
# versions load without noise.  airport_elevation_inset_resolution_m was
# superseded by airport_elevation_level (2026-07-24).
RETIRED_CFG_KEYS = ("airport_elevation_inset_resolution_m",)

################################################################################
# Update from Global Ortho4XP.cfg
try:
    f = open(global_cfg_file, "r")
    for line in f.readlines():
        line = line.strip()
        if not line:
            continue
        if line[0] == "#":
            continue
        try:
            (var, value) = line.split("=", 1)
            if var in RETIRED_CFG_KEYS:
                # A key from an older version, superseded by a newer
                # setting: skipped silently (the next config write drops
                # it), never reported as an invalid line.
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
except FileNotFoundError:
    # Create a new global config file using default values
    os.makedirs(os.path.dirname(global_cfg_file), exist_ok=True)
    with open(global_cfg_file, "w") as file:
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

    def make_dirs(self):
        if os.path.isdir(self.build_dir):
            if not os.access(self.build_dir, os.W_OK):
                UI.vprint(
                    0,
                    "OS error: Tile directory",
                    self.build_dir,
                    " is write protected.",
                )
                raise Exception
        else:
            try:
                os.makedirs(self.build_dir)
            except:
                UI.vprint(
                    0,
                    "OS error: Cannot create tile directory",
                    self.build_dir,
                    " check file permissions.",
                )
                raise Exception

    def read_from_config(self, config_file=None, use_global=False):
        """
        Read tile config from config file and update class variables.

        :params str config_file: path to config file; unknown use case
        :params bool use_global: force use of global config file
        
        :returns: 1 if successful, 0 if not
        :return type: int
        """
        if not config_file:
            config_file = os.path.join(
                self.build_dir,
                "Ortho4XP_" + FNAMES.short_latlon(self.lat, self.lon) + ".cfg",
            )
            if not os.path.isfile(config_file) or use_global:
                config_file = global_cfg_file

                if not os.path.isfile(config_file):
                    
                    UI.lvprint(
                        0,
                        "CFG error: No tile or global config file found.",
                        FNAMES.short_latlon(self.lat, self.lon),
                    )
                    return 0
        try:
            f = open(config_file, "r")
            for line in f.readlines():
                line = line.strip()
                if not line:
                    continue
                if line[0] == "#":
                    continue
                try:
                    (var, value) = line.split("=", 1)
                    # compatibility with config files from version <= 1.20
                    value = config_compatibility(value)
                    # Values from other forks map to their closest
                    # equivalent here (registry-driven), loudly — never
                    # silently treated as "off".
                    legacy_map = cfg_vars.get(var, {}).get("legacy_values")
                    if legacy_map and value in legacy_map:
                        UI.vprint(
                            1,
                            "   Legacy config value", value, "for", var,
                            "read as", legacy_map[value] + ".",
                        )
                        value = legacy_map[value]
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
            return 1
        except:
            UI.lvprint(
                0,
                "CFG error: Could not read config file for tile",
                FNAMES.short_latlon(self.lat, self.lon),
            )
            return 0

    def write_to_config(self, config_file = None):
        """
        Create tile config file from class variables.

        :params str config_file: path to config file; unknown use case
        
        :returns: 1 if successful, 0 if not
        :return type: int
        """
        if not config_file:
            config_file = os.path.join(
                self.build_dir,
                "Ortho4XP_" + FNAMES.short_latlon(self.lat, self.lon) + ".cfg",
            )
            config_file_bak = config_file + ".bak"
        try:
            os.replace(config_file, config_file_bak)
        except:
            pass
        try:
            f = open(config_file, "w")
            for var in list_tile_vars:
                tile_zones = []
                lat = self.lat
                lon = self.lon
                if lat < 0:
                    lat = lat + 1
                if lon < 0:
                    lon = lon + 1
                for zone in globals()["zone_list"]:
                    _zone_list = [int(coord) for coord in zone[0]]
                    _zone_list = set(_zone_list)
                    if lat in _zone_list and lon in _zone_list:
                        tile_zones.append(zone)
                        _LOGGER.debug("Zones in tile found: %s", tile_zones)
                if var == "zone_list":
                    f.write(var + "=" + str(tile_zones) + "\n")
                else:
                    f.write(var + "=" + str(eval("self." + var)) + "\n")
            f.close()
            return 1
        except Exception as e:
            UI.vprint(2, e)
            UI.lvprint(
                0,
                "CFG error: Could not write config file for tile",
                FNAMES.short_latlon(self.lat, self.lon),
            )
            return 0
