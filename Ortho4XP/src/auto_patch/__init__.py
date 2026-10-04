"""Auto-patch: the tile driver, the readers and the object stage.

The public entry point :func:`generate_auto_patches` is invoked per tile by
``O4_Vector_Map``.  It selects the tile's airports, builds each one through
the v2 engine (``auto_patch_v2``, the ONLY engine since RULINGS 2026-09-13au)
and places ``{ICAO}_auto.patch.osm`` into the tile's Patches directory.
Auto-patches have lower priority than user-provided manual patches.

THE CHARTER (stage B of the v1 retirement, round 2, 2026-10-04): this
package is what SURVIVED the v1 engine — the 27 modules production reaches,
declared one by one in ``tests/test_v1_retired.py`` (``KEEP``), which also
asserts that nothing else is on disk here.  The v1 pavement builder, its
solver, law, emitter and feature passes (104 modules, 185k lines) are
deleted; surface construction, the solve, the law tables and the emitter
live in ``auto_patch_v2``.  A new module here is a visible edit to ``KEEP``;
new engine work belongs in ``auto_patch_v2``.

Package layout
--------------
* the drivers — ``driver`` (tile-level orchestrator, this entry point),
  ``engine_v2`` (the per-airport v2 adapter: build, stamp, verify, place),
  ``selection`` (which airports a tile builds), ``progress``,
  ``provenance`` (the freshness stamps and gate inventory)
* the readers — ``apt_dat_reader``, ``cifp_reader``, ``dsf_reader``,
  ``agp_reader``, ``obj8_reader``, ``osm_aeroway``
* the flat-site detector — ``flat_site`` / ``flat_site_mode``
* the object stage (post-mesh) — ``post_mesh``, ``object_rebake``,
  ``object_anchor``, ``object_frame``, ``object_clusters``,
  ``object_footprints``, ``object_terrain_features``,
  ``object_terrain_kinds``, ``obj8_partition``, ``mesh_sampler``
* shared support — ``build_support`` (apt.dat selection, the airports OSM
  prefetch and its fetch predicate, the local-metre frame), ``config``
  (the constants still read), ``geom_safe``
"""
from __future__ import annotations

__all__ = ["generate_auto_patches"]


def __getattr__(name):
    """Resolve the package entry point LAZILY (PEP 562).

    ``auto_patch.selection`` holds the pure mode predicates that core
    modules (settings, insets, the harness) import; an eager
    ``from .driver import generate_auto_patches`` here would drag the whole
    auto-patch pipeline into every one of those importers.
    """
    if name == "generate_auto_patches":
        from .driver import generate_auto_patches

        return generate_auto_patches
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
