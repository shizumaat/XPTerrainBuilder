"""auto_patch_v2.planar — the PLANAR MAP producer (plan §1 row 4).

``build(airport, classification, law) -> (PlanarMap, BuildStats)``:
one noded arrangement (``overlay``), zone regions (``zones``), chord
density (``chords``), the STRtree + GeoJSON view (``index``).  Imports
``law``, ``model``, ``airport`` and ``classify``; shapely lives here and
in ``classify``.  CLI: ``python -m auto_patch_v2.planar ICAO --out DIR``.
"""
from .build import BuildStats, build  # noqa: F401
from .index import PlanarIndex, face_polygon, to_geojson  # noqa: F401

__all__ = ["BuildStats", "build", "PlanarIndex", "face_polygon", "to_geojson"]
