"""Sea cells the land mask calls land (issue #1721).

``Utils/world_tiles.png`` is one pixel per degree cell and coarse: it
marks some open-ocean cells as land (the Atlantic east of the New Jersey
shore, south of Long Island).  A base source that answers "not there"
for such a cell raised ``ElevationAbsentRefused``, the fallbacks
answered "no tile" too, and the tile was refused -- for the sea.

THE RULE.  A cell is SEA when the configured base source answered "not
there" (never a transport failure: that says nothing about the cell),
and every fallback source asked answered "no tile" without an error,
and at least one of them is a LAND-COMPLETE source: its ``.elv``
carries ``land_complete=True`` because it publishes a tile for every
cell holding land (Copernicus GLO-30 / GLO-90), so its "no tile" is a
water witness.  A source that could not be reached, refused this
client, or does not cover the cell is no witness, and the refusal
stands.

A stronger LAND witness overrules the water witness: the cell's own
cached OSM coastline layer holding any coastline inside the cell.  It is
read from disk only (never fetched); no cached layer is no witness.

A sea cell is built exactly as the engine builds any ocean cell the mask
calls ocean: the 3x3 assembly zero-fills it (bathymetry, where fetched,
lies on top as it does for every sea cell).
"""

import os

import O4_File_Names as FNAMES

from elevation_access.definitions import _parse_boolean

__all__ = ["LAND_COMPLETE_KEY", "is_land_complete", "osm_land_witness"]

#: The ``.elv`` key of a source that publishes a tile for every land cell.
LAND_COMPLETE_KEY = "land_complete"


def is_land_complete(definition):
    """Does this source's "no tile" witness water?"""
    return bool(_parse_boolean(definition.get(LAND_COMPLETE_KEY)))


def osm_land_witness(lat, lon):
    """The cached OSM coastline file of cell ``(lat, lon)`` when it holds
    coastline inside the cell, else ``None``.  Disk only; a layer that
    does not parse is no witness (it answers nothing about the cell)."""
    cached = FNAMES.osm_cached(lat, lon, "coastline")
    if not os.path.isfile(cached):
        return None
    import O4_OSM_Utils as OSM  # lazy: heavy, and only for a sea verdict

    tags = {"n": [], "w": [("natural", "coastline")], "r": []}
    layer = OSM.OSM_layer()
    try:
        if not layer.update_dicosm(
                cached, tags, {k: list(v) for (k, v) in tags.items()}):
            return None
        coastline = OSM.OSM_to_MultiLineString(layer, lat, lon)
    except Exception:
        return None
    return None if coastline.is_empty else cached
