"""The photo's own sun: cast shadow or dark rock (#2102, LPPD 2026-11-18).

``O4_Cliff_Shade`` carries the cliff overlay over dark photo beside a cliff,
reading the dark as the cliff's shadow.  Black volcanic rock is dark too.
The two differ by where the sun is: a shadow lies on faces turned AWAY from
the sun and at their foot, while a face turned TOWARD the sun is lit in the
photo, so a dark sun-facing face is dark material, not shadow (owner
2026-11-18: "we might be identifying the rocky cliff edge as shadow, when in
fact it's just black volcanic rock").

The sun is read from the photo itself, never from a date or a place: over
moderately sloped land (:data:`SUN_SLOPES`) the photo's luminance follows
Lambert's law, ``lum ~ a + b . n_h`` with ``n_h`` the triangle's horizontal
normal, so the least-squares ``b`` points (east, north) toward the sun.  A
fit whose amplitude is under :data:`SUN_MIN_AMPLITUDE` of the median
luminance (flat light, overcast, too few samples) gives no sun and no
witness.  Measured on +37-026 (LPPD): azimuth 152 deg, amplitude 26 on a
median of 76; 51 of the tile's 59 dark cliff regions face away from it.
Pure numpy.
"""
from __future__ import annotations

import math

import numpy

__all__ = ["ROCK_FACING_MIN", "SUN_MIN_AMPLITUDE", "SUN_SLOPES",
           "dark_rock_regions", "region_aspects", "sun_direction"]

#: Triangles this sloped (degrees) read the sun: steep enough for their
#: aspect to change their brightness, gentle enough to be lit ground.
SUN_SLOPES = (8.0, 45.0)
#: The fit's horizontal amplitude must reach this fraction of the median
#: luminance, or the photo shows no sun.
SUN_MIN_AMPLITUDE = 0.15
#: A region faces the sun when the cosine between its mean aspect and the
#: sun's azimuth is at least this (75 degrees).
ROCK_FACING_MIN = 0.25
#: Fewer readable samples than this fit no sun.
MIN_SAMPLES = 200


def sun_direction(values, normals, slopes):
    """Unit (east, north) toward the sun, or None.  ``values`` (k,)
    luminance of k sampled land triangles (NaN: unread), ``normals`` (k, 3)
    their upward unit normals, ``slopes`` (k,) degrees."""
    values = numpy.asarray(values, float)
    lo, hi = SUN_SLOPES
    ok = numpy.isfinite(values) & (slopes >= lo) & (slopes <= hi)
    if ok.sum() < MIN_SAMPLES:
        return None
    x = numpy.column_stack((numpy.ones(ok.sum()), normals[ok, 0],
                            normals[ok, 1]))
    coef = numpy.linalg.lstsq(x, values[ok], rcond=None)[0]
    amplitude = math.hypot(coef[1], coef[2])
    if amplitude < SUN_MIN_AMPLITUDE * numpy.median(values[ok]):
        return None
    return numpy.array((coef[1], coef[2])) / amplitude


def region_aspects(region_tris, normals, areas, slopes, face_min):
    """(r, 2) per region the unit horizontal direction its steep face
    (triangles at or above ``face_min`` degrees, else all of it) looks."""
    out = numpy.zeros((len(region_tris), 2))
    for r, tris in enumerate(region_tris):
        tris = numpy.asarray(tris)
        steep = tris[slopes[tris] >= face_min]
        steep = steep if len(steep) else tris
        h = (normals[steep, :2] * areas[steep, None]).sum(0)
        norm = numpy.linalg.norm(h)
        if norm > 0:
            out[r] = h / norm
    return out


def dark_rock_regions(region_tris, tri_idx, node_lum, typical, sun, normals,
                      areas, slopes, face_min=45.0):
    """(r,) bool: the region faces the sun (:data:`ROCK_FACING_MIN`) and
    its nodes' median luminance is under ``typical`` (the tile's median
    land luminance) -- a face the sun shines on is at least as bright as
    the typical ground unless its material is darker: dark rock, never a
    shadow.  All False without a sun."""
    out = numpy.zeros(len(region_tris), bool)
    if sun is None or not len(region_tris):
        return out
    facing = region_aspects(region_tris, normals, areas, slopes,
                            face_min) @ sun
    for r, tris in enumerate(region_tris):
        if facing[r] < ROCK_FACING_MIN:
            continue
        lum = node_lum[numpy.unique(tri_idx[tris])]
        lum = lum[numpy.isfinite(lum)]
        out[r] = bool(len(lum)) and float(numpy.median(lum)) < typical
    return out
