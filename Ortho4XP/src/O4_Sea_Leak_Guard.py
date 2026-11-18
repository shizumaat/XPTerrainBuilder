"""THE MESH'S SEA STAYS IN THE COASTLINE'S SEA — the post-mesh guard.

MEASURED (+53+009, app 1.0.557, owner 2026-11-17: "EDDH somehow lost its
mesh and is sitting in the ocean now"): one SEA seed stood 0.5 mm from
the Elbe coastline, a node move of 1.3 mm put it on the land side, and
Triangle4XP's plague spread the SEA attribute over 2,449,475 of the
tile's 2,942,253 triangles — Hamburg and its airport levelled to sea.
Nothing refused it; the DSF shipped.  The seed is fixed at its
derivation site (``O4_Coastline_Vetting.sea_seed_points``); this is the
guard that keeps the CLASS from ever shipping silently again, whatever
lets a seed's region leak next.

THE LAW: a SEA triangle lies in the coastline's sea.  The witness is the
tree's single SEA/LAND partition (``O4_Vector_Map.sea_area_from_coastline``
over ``cached_coastline_multilinestring``, the data the vector step
encoded), read from disk, never downloaded.  The plague can only reach
what the coastline's edges enclose, so a SEA triangle whose centroid
lies outside that sea is a leak.  More than :data:`SEA_LEAK_MAX_KM2` of
it refuses the tile (:class:`SeaLeak`, failure ``mesh_refused``) before
a flooded DSF is written; ``O4_SEA_LEAK=warn`` downgrades the refusal to
a loud line for a deliberate investigation.  A tile with no coastline on
disk has nothing to judge against and is not judged (said once).
"""

from __future__ import annotations

import os

import numpy
import O4_Geo_Utils as GEO
import O4_UI_Utils as UI

__all__ = ["SEA_LEAK_ENV", "SEA_LEAK_MAX_KM2", "SeaLeak", "leaked_sea",
           "audit_sea_extent"]

SEA_LEAK_ENV = "O4_SEA_LEAK"

#: SEA triangles outside the coastline's sea past which the tile is
#: refused.  A plague leak floods the whole land region it reaches (the
#: measured one: 7,270 km2), and the honest residue is the triangles a
#: coastline vertex shares with both sides — square metres.  1 km2 sits
#: three orders of magnitude from each.
SEA_LEAK_MAX_KM2 = 1.0

_SEA_BIT = 2          # ``Vector_Map.dico_attributes["SEA"]``


class SeaLeak(Exception):
    """SEA triangles reached ground the coastline calls land."""


def leaked_sea(xy, corners, attrs, sea):
    """``(area_deg2, count, sample_xy)`` of the SEA triangles whose
    centroid lies outside ``sea`` (tile-relative polygon).

    ``xy`` is ``(n, 2)`` tile-relative vertex positions, ``corners``
    ``(m, 3)`` 0-based vertex indices, ``attrs`` the ``(m,)`` integer
    triangle attributes.  ``sample_xy`` is the leaked triangle centroid
    farthest inland (the largest distance to ``sea``), ``None`` when
    nothing leaked."""
    import shapely

    is_sea = (numpy.asarray(attrs, dtype=numpy.int64) & _SEA_BIT) != 0
    if not is_sea.any():
        return 0.0, 0, None
    tri = numpy.asarray(xy, dtype=float)[numpy.asarray(corners)[is_sea]]
    centroid = tri.mean(axis=1)
    if sea is None or sea.is_empty:
        outside = numpy.ones(len(centroid), dtype=bool)
    else:
        shapely.prepare(sea)
        outside = ~shapely.contains_xy(sea, centroid[:, 0], centroid[:, 1])
    if not outside.any():
        return 0.0, 0, None
    tri, centroid = tri[outside], centroid[outside]
    area = 0.5 * numpy.abs(
        (tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1])
        - (tri[:, 2, 0] - tri[:, 0, 0]) * (tri[:, 1, 1] - tri[:, 0, 1]))
    sample = centroid[int(numpy.argmax(area))]
    if sea is not None and not sea.is_empty:
        step = max(1, len(centroid) // 2000)
        probe = centroid[::step]
        depth = shapely.distance(sea, shapely.points(probe))
        sample = probe[int(numpy.argmax(depth))]
    return float(area.sum()), int(outside.sum()), tuple(sample)


def _coastline_sea(tile):
    """The coastline's sea for ``tile`` (cache only), or ``None``."""
    import O4_Vector_Map as VMAP

    memo = getattr(tile, "_water_datum_layers", None)
    if isinstance(memo, tuple) and memo[0] is not None:
        return memo[0]
    coastline, custom_source = VMAP.cached_coastline_multilinestring(tile)
    if coastline is None:
        return None
    return VMAP.sea_area_from_coastline(coastline, tile.lat, tile.lon,
                                        custom_source)


def audit_sea_extent(tile, xy, corners, attrs, sea=None) -> float:
    """REFUSE (:class:`SeaLeak`) when the mesh's SEA triangles reach more
    than :data:`SEA_LEAK_MAX_KM2` outside the coastline's sea.  Returns
    the leaked km2 (0.0 when the tile has no coastline to judge by)."""
    if sea is None:
        try:
            sea = _coastline_sea(tile)
        except Exception as error:                         # pragma: no cover
            UI.vprint(1, "   Sea leak guard: the coastline could not be "
                      "read (", type(error).__name__, "); not judged.")
            return 0.0
        if sea is None:
            if ((numpy.asarray(attrs, dtype=numpy.int64) & _SEA_BIT) != 0
                    ).any():
                UI.vprint(1, "   Sea leak guard: no coastline on disk; "
                          "the tile's sea is not judged.")
            return 0.0
    area_deg2, count, sample = leaked_sea(xy, corners, attrs, sea)
    km2 = area_deg2 * GEO.lat_to_m * GEO.lon_to_m(tile.lat + 0.5) / 1e6
    if km2 <= SEA_LEAK_MAX_KM2:
        if count:
            UI.vprint(1, "   Sea leak guard: {} SEA triangle(s), {:.4f} km2, "
                      "outside the coastline's sea (under {:g} km2)."
                      .format(count, km2, SEA_LEAK_MAX_KM2))
        return km2
    sea_km2 = 0.0 if sea is None or sea.is_empty else (
        sea.area * GEO.lat_to_m * GEO.lon_to_m(tile.lat + 0.5) / 1e6)
    message = (
        "SEA LEAK at {:+03d}{:+04d}: {} SEA triangle(s) covering {:.1f} km2 "
        "lie OUTSIDE the coastline's sea ({:.1f} km2) — a sea seed's region "
        "leaked onto land (deepest at {:.6f}, {:.6f}). The tile is not "
        "written: rebuild it, and report it if it repeats.".format(
            tile.lat, tile.lon, count, km2, sea_km2,
            sample[1] + tile.lat, sample[0] + tile.lon))
    if os.environ.get(SEA_LEAK_ENV, "").strip().lower() == "warn":
        UI.lvprint(0, "WARNING:", message)
        return km2
    raise SeaLeak(message)
