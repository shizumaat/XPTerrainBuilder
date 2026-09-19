"""Auto-patch: generate runway slope patches from CIFP/AIRAC data.

The public entry point :func:`generate_auto_patches` is invoked
per tile by ``O4_Vector_Map``.  It scans the CIFP directory for
airport data, parses runway threshold elevations, and writes
``{ICAO}_auto.patch.osm`` files into the tile's Patches directory.

Auto-patches replace Ortho4XP's default polynomial-fit altitude
model with authoritative aeronautical data.  They have lower
priority than user-provided manual patches.

Package layout
--------------
* ``driver``                — tile-level orchestrator (this entry point)
* ``pipeline``              — per-airport pavement-build orchestrator
* ``layout`` / ``config``   — shared data model + tunables
* ``cifp_reader``           — CIFP threshold-elevation reader
* ``osm_aeroway``           — OSM aeroway data extraction
* ``elevation``             — phase-2 altitude solver
* ``boundary``              — airport perimeter ribbon
* ``bridges``               — taxi/road bridges (gated off)
* ``groundside``            — curbside / drop-off pavement
* ``terminals``             — OSM terminal building pads
* ``pavement/``             — airside paved-surface construction (sub-package)
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
