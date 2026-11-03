"""THE MATCH KEY of a tile bundle (#1699 design, "Matching the pack
version").  A content hash, never a name: the receiving app computes the
same key from what it has installed, so a pack renamed in Custom Scenery
still matches and a pack whose DSF its developer patched does not.

The key is a hash of four things (the design's fifth, the data snapshot
month, is shown to the user and kept out of the exact match):

* the tile;
* for every airport the tile grades (``build_airports.tile_airports`` —
  the selector the build itself runs), its pack SIGNATURE taken from the
  PRISTINE pack: the airport's apt.dat block hash, the hash of the pack's
  tile DSF as installed (its ``.anchor_bak`` when an earlier build
  rewrote the live file, ``dsf_write.pristine_dsf_path``), a borrowed
  Global Airports block's hash, and the ``1302 flatten`` declaration;
* the MESH PROFILE: the settings the vector, mesh and masks steps key on
  (``O4_Step_Reuse.live_settings``), install paths left out;
* the CODE FAMILY: each step's code digest and the auto-patch
  configuration digest (``O4_Step_Reuse.code_identity``).

Tile bundles are made only for the default mesh settings (owner Q301):
:func:`profile_deviations` names the settings that are not.
"""
from __future__ import annotations

import O4_Step_Reuse as REUSE
from auto_patch import provenance_env as _env
from auto_patch_v2.airport.pack_identity import digest as _digest
from auto_patch_v2.airport.pack_identity import pack_signature  # the one derivation

from . import FORMAT

__all__ = ["NOT_PROFILE", "MATCHED_NOT_REFUSED", "LOCATION_ENVS", "mesh_profile",
           "profile_deviations", "without_locations", "xplane_root",
           "pack_signature", "airport_signatures", "key_parts",
           "bundle_key", "first_difference"]

#: Settings in a step's key that are not part of the mesh profile: where
#: the user keeps X-Plane and its CIFP data (not what the mesh is), and
#: ``airport_inset_water``, whose own definition says its value has no
#: effect (``O4_Cfg_Vars``: retired 2026-07-26, kept so old files parse).
NOT_PROFILE = ("custom_scenery_dir", "cifp_data_path", "airport_inset_water")

#: Settings a bundle is made for at ANY value: still in the profile digest
#: (so matched), never a reason to refuse an export (owner Q315,
#: 2026-11-02: "For 301, option a." — ``road_level`` is part of the key).
MATCHED_NOT_REFUSED = ("road_level",)


def mesh_profile(tile) -> dict:
    """``{setting: repr(value)}`` the three steps key on, minus
    :data:`NOT_PROFILE`."""
    profile: dict = {}
    for step in REUSE.REUSABLE_STEPS:
        profile.update(REUSE.live_settings(tile, step))
    return {name: value for name, value in sorted(profile.items())
            if name not in NOT_PROFILE}


def profile_deviations(profile: dict) -> list:
    """The settings of ``profile`` whose value is not the engine's default
    (``O4_Cfg_Vars``) — a bundle is made only when there are none."""
    import O4_Cfg_Vars as CFGVARS
    return [name for name, value in sorted(profile.items())
            if name in CFGVARS.cfg_vars and name not in MATCHED_NOT_REFUSED
            and value != repr(CFGVARS.cfg_vars[name].get("default"))]


#: ``O4_`` variables the auto-patch configuration digest reads that say
#: WHERE a cache is kept, not what it holds; a bundle's key must not name
#: the machine (``auto_patch.provenance_env.CACHE_LOCATIONS``, the one
#: list, shared with the library's airport entries).
LOCATION_ENVS = _env.CACHE_LOCATIONS
without_locations = _env.without_cache_locations


def _code_family() -> dict:
    """``{step: {"code", "auto_patch_cfg"}}`` for this engine, the
    configuration digest taken without :data:`LOCATION_ENVS`."""
    with without_locations():
        return {step: REUSE.code_identity(step)
                for step in REUSE.REUSABLE_STEPS}


def xplane_root(tile) -> str | None:
    """The X-Plane install the tile's build reads (its CIFP folder's)."""
    import O4_Vector_Map as VMAP
    from auto_patch_v2.airport.cifp import xplane_root_from_cifp_path
    cifp = VMAP.resolve_cifp_dir_for_tile(tile)
    return xplane_root_from_cifp_path(cifp) if cifp else None


def _graded_airports(tile) -> list:
    from o4_engine.build_airports import tile_airports
    rows = tile_airports(tile.lat, tile.lon,
                         getattr(tile, "custom_build_dir", "") or "")
    return sorted({row["icao"] for row in rows})


def airport_signatures(tile) -> dict:
    """``{icao: {"pack", "custom", "signature"}}`` for every airport the
    tile grades, from this machine's installed packs."""
    root = xplane_root(tile)
    if not root:
        return {}
    return {icao: pack_signature(root, icao, tile.lat, tile.lon)
            for icao in _graded_airports(tile)}


def key_parts(tile) -> dict:
    """The four parts the key hashes (module doc)."""
    import O4_File_Names as FNAMES
    return {"format": FORMAT,
            "tile": FNAMES.short_latlon(tile.lat, tile.lon),
            "airports": {icao: entry["signature"] for icao, entry
                         in airport_signatures(tile).items()},
            "mesh_profile": _digest(mesh_profile(tile))[:32],
            "code": _code_family()}


def bundle_key(parts: dict) -> str:
    """The key: a hash of :func:`key_parts`."""
    return _digest(parts)[:32]


def first_difference(theirs: dict, ours: dict) -> str | None:
    """The first part of two :func:`key_parts` that differs, in the
    user's words, or ``None`` when they match."""
    if theirs.get("format") != ours.get("format"):
        return "the bundle is format %s; this app reads %s" % (
            theirs.get("format"), ours.get("format"))
    if theirs.get("tile") != ours.get("tile"):
        return "the bundle is for tile %s, not %s" % (theirs.get("tile"),
                                                      ours.get("tile"))
    a, b = theirs.get("airports") or {}, ours.get("airports") or {}
    for icao in sorted(set(a) | set(b)):
        if icao not in b:
            return "%s is in the bundle but this app does not grade it" % icao
        if icao not in a:
            return "%s is graded here but the bundle was built without it" \
                % icao
        if a[icao] != b[icao]:
            return ("%s: the installed scenery pack is not the version the "
                    "bundle was built with" % icao)
    if theirs.get("mesh_profile") != ours.get("mesh_profile"):
        return "the mesh settings differ from the bundle's"
    for step in sorted(set(theirs.get("code") or {}) | set(ours.get("code") or {})):
        if (theirs.get("code") or {}).get(step) != (ours.get("code") or {}).get(step):
            return "this app's %s step code is not the bundle's engine's" % step
    return None
