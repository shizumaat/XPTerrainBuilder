"""THE SCENERY-FILE STEP'S DATA INPUTS, CARRIED BY A TILE BUNDLE (#1699
phase 1; census ``docs/specs/tile-bundle-phase1-census.md``).

The scenery-file step (``O4_DSF_Utils.build_dsf``) reads elevation data
of its own, beside the mesh and the masks: the XP12 ``elevation`` and
``sea_level`` rasters come from the installed Global Scenery DSF, and
where measured coastal bathymetry applies, from the bathymetry band —
which reads the tile's OpenStreetMap COASTLINE to decide whether there is
one (``O4_Bathymetry_Band._band_geometry``, a download on a cold cache)
and warps the band's cells with GDAL — and from the base DEM on the DSF
post grid.  A tile laid down from a bundle has none of those data, so the
bundle carries what the step derives from them, on the DSF's own 1201 x
1201 post grid:

* ``band`` — whether the tile has a measured bathymetry band at all;
* ``measured`` — the band warped to the post grid (float32), when it has;
* ``elevation`` — the base DEM on the post grid (int16), when it has.

The Global Scenery donor is NOT carried: it is the user's own X-Plane
install, read where it is.  :func:`bundled` answers only for a tile whose
vector-step record a bundle laid down with the key the file names
(``O4_Step_Reuse.adopt_bundle_record``); every other build computes as it
always has.
"""
from __future__ import annotations

import io
import os

import O4_DSF_Utils as DSF
import O4_Step_Reuse as REUSE

__all__ = ["FILE_SUFFIX", "path", "compute", "to_bytes", "bundled"]

#: ``Data<tile>`` + this, in the tile's build folder.
FILE_SUFFIX = ".dsf_inputs.npz"


def path(tile) -> str:
    import O4_File_Names as FNAMES
    return os.path.join(tile.build_dir, "Data" + FNAMES.short_latlon(
        tile.lat, tile.lon) + FILE_SUFFIX)


def compute(tile) -> dict:
    """The inputs as the scenery-file step derives them on this machine
    (the bathymetry band's default arguments, the DSF raster callers');
    a tile laid down from a bundle answers with that bundle's."""
    import O4_Bathymetry_Band as BATHYBAND
    carried = bundled(tile)
    if carried is not None:
        return carried
    band_vrt = BATHYBAND.ensure_bathymetry_band(tile)
    if band_vrt is None:
        return {"band": False, "measured": None, "elevation": None}
    return {"band": True,
            "measured": BATHYBAND.warp_band_to_post_grid(
                band_vrt, tile.lat, tile.lon, DSF.DSF_RASTER_POSTS),
            "elevation": DSF.tile_elevation_post_grid(tile)}


def to_bytes(inputs: dict, key: str) -> bytes:
    """The file's bytes: an ``.npz`` naming the bundle ``key``."""
    import numpy
    arrays = {"key": numpy.array(key), "band": numpy.array(bool(inputs["band"]))}
    for name in ("measured", "elevation"):
        if inputs.get(name) is not None:
            arrays[name] = numpy.asarray(inputs[name])
    out = io.BytesIO()
    numpy.savez(out, **arrays)
    return out.getvalue()


def bundled(tile) -> dict | None:
    """The bundle's inputs for ``tile``, or ``None``: no file, or a tile
    whose vector record is not the bundle's that wrote it."""
    if not getattr(tile, "build_dir", None):
        return None
    file_path = path(tile)
    if not os.path.isfile(file_path):
        return None
    bundle = REUSE.committed_entry(tile, "vector").get("bundle") or {}
    try:
        import numpy
        with numpy.load(file_path, allow_pickle=False) as data:
            if not bundle or str(data["key"]) != bundle.get("key"):
                return None
            return {"band": bool(data["band"]),
                    "measured": data["measured"] if "measured" in data else None,
                    "elevation": data["elevation"] if "elevation" in data else None}
    except (OSError, ValueError, KeyError):
        return None
