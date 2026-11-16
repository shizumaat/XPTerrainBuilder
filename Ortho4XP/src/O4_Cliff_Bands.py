"""The cliff overlay's texture follows the slope over the shadow (#2102).

``O4_Cliff_Shade`` carries the cliff overlay past the cliff, across the
photo's dark band at its foot.  That band is often gentle ground, where
X-Plane itself draws no rock (owner 2026-11-16: "we don't want to use the
cliff textures there"), so over the carried part the overlay draws what
the landclass draws at each slope, as three layers, bottom to top:

* ``base``  -- the landclass's ``BASE_TEX``, at the carried opacity;
* ``hill``  -- its ``AUTO_SLOPE_HILL`` texture, faded in over the hill
  band (e.g. 35..40 degrees);
* ``cliff`` -- its ``AUTO_SLOPE_CLIFF`` texture, faded in over the cliff
  band (e.g. 57..62 degrees), and as before on the cliff itself.

Each layer's node opacity is the carried opacity times the smoothstep of
the node's slope (its steepest land triangle) over that layer's band, so
the texture blends from base to hill to rock with the same soft ramps as
the overlay's own edge.  Where nothing is carried the cliff layer is the
overlay's slope alpha alone and the other two are empty: the bytes
without this module.  Pure numpy.
"""
from __future__ import annotations

import numpy
import O4_Cliff_Faces as FACES

__all__ = ["DEFAULT_BANDS", "LAYERS", "band_alphas", "dominant_layers",
           "node_bands"]

#: Draw order of the layers, bottom first.
LAYERS = ("base", "hill", "cliff")
#: ``(hill lo, hill hi, cliff lo, cliff hi)`` degrees where a region's
#: landclass gives none (X-Plane's common landclass rows).
DEFAULT_BANDS = (35.0, 40.0, 57.0, 62.0)


def node_bands(layout, tri_idx, region_bands, nbr_nodes):
    """(n, 4) per node the bands of its region (``region_bands[r]`` a
    4-tuple or None for :data:`DEFAULT_BANDS`); a node two regions share
    takes the later region's."""
    out = numpy.tile(numpy.asarray(DEFAULT_BANDS, float), (nbr_nodes, 1))
    for r, tris in enumerate(layout.region_tris):
        bands = region_bands[r] if r < len(region_bands) else None
        if bands is not None:
            out[numpy.unique(tri_idx[tris])] = bands
    return out


def band_alphas(steepest, slope_alpha, extra, bands):
    """``{layer: (n,) opacity}``: ``steepest`` (n,) node slopes,
    ``slope_alpha`` (n,) the overlay's own ramp, ``extra`` (n,) the carried
    opacity, ``bands`` (n, 4) from :func:`node_bands`."""
    hill = FACES.slope_ramp(steepest, bands[:, 0], bands[:, 1])
    cliff = FACES.slope_ramp(steepest, bands[:, 2], bands[:, 3])
    return {"base": extra, "hill": extra * hill,
            "cliff": numpy.maximum(slope_alpha, extra * cliff)}


def dominant_layers(tri_idx, tris, alphas):
    """Per triangle of ``tris`` the index in :data:`LAYERS` of the layer
    that shows most at its centre (the mean of its nodes' opacities,
    composited bottom to top)."""
    a = {k: v[tri_idx[tris]].mean(1) for k, v in alphas.items()}
    cliff = a["cliff"]
    hill = a["hill"] * (1 - cliff)
    base = a["base"] * (1 - a["hill"]) * (1 - cliff)
    return numpy.argmax(numpy.stack((base, hill, cliff), 1), 1)
