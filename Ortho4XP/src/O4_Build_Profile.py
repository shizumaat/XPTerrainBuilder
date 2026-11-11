"""Build profiles: the ONE place a profile name becomes tile settings
(flight manager / World spec 2026-11-10, §8.4 "A profile override
("light") joins overrides and is resolved in ONE engine function to the
settings of §2.1; no view composes it").

``light`` is the intermediate tile flown on the CYYR World pack flight
(§2.1, settings of that kit's ``build_root/XPTerrainBuilder.cfg``): our
mesh at 90 m, no airport grading or insets, no high-res airport cover, no
bathymetry, no road levelling, imagery on demand at the 512 px
placeholder tier.  The imagery source and zoom level stay the build's own.
``full`` is the normal build (no change).

A build request carries ``overrides={"profile": "light"}``;
``O4_Config_Utils.Tile.apply_build_overrides`` lands
:func:`profile_settings` on the tile after its cfg is read, and never
writes them back to the tile's cfg.

Pure: no I/O.
"""
from __future__ import annotations

__all__ = ["PROFILES", "DEFAULT_PROFILE", "profile_settings", "profile_of"]

#: The default: the build as the user's settings make it.
DEFAULT_PROFILE = "full"
#: Profile name -> the tile settings it sets (values typed as the cfg
#: registry types them, ``O4_Cfg_Vars``).
PROFILES: dict = {
    "full": {},
    "light": {
        "elevation_level": "90",
        "auto_patch": "None",
        "airport_elevation_insets": "None",
        "cover_airports_with_highres": "False",
        "imagery_on_demand": True,
        "placeholder_zl_drop": 3,
        "bathymetry_near_icao_airports": False,
        "bathymetry_near_seaplane_bases": False,
        "dsf_bathymetry": "False",
        "road_level": "0",
        "masks_use_DEM_too": "False",
    },
}


def profile_settings(name) -> dict:
    """The tile settings of profile ``name`` (a copy); ``ValueError`` for
    an unknown name."""
    if name not in PROFILES:
        raise ValueError(f"unknown build profile {name!r} "
                         f"(known: {sorted(PROFILES)})")
    return dict(PROFILES[name])


def profile_of(overrides) -> str:
    """The profile a build's ``overrides`` ask for (``full`` when none)."""
    name = (overrides or {}).get("profile") or DEFAULT_PROFILE
    return name if name in PROFILES else DEFAULT_PROFILE
