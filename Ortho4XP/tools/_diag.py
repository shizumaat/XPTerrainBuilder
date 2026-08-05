"""Shared helpers for auto-patch diagnostic tools.

Centralizes the boilerplate every diagnostic script needs so individual
tools stay short and consistent:

  * ``sys.path`` setup (adds ``src/`` and repo root)
  * an X-Plane root default
  * building an airport layout (``build``)
  * the ordered list of geometry-mutating pipeline passes

Coordinate conventions (see ``layout.py``): layout shape polygons are in
LOCAL METRES anchored at ``layout.anchor``; ``layout.m_to_ll(x, y)``
returns geographic ``(lat, lon)``.

Import note: always import ``auto_patch.pipeline`` BEFORE
``auto_patch.junction_repair`` (junction_repair <-> elevation have a
circular import that only resolves via the normal pipeline import order).
``build`` imports pipeline first, so callers that go through it are safe.

The OSM-dump / union-capture / role-tally / pass-patching helpers that
used to live here were deleted in the dead-code round: their only callers
were quarantined scripts under ``tools/attic/``.
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_XPLANE = "/Users/noah/X-Plane 12"

for _p in (os.path.join(REPO, "src"), REPO, os.path.join(REPO, "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def build(icao: str, xplane: str = DEFAULT_XPLANE, **kw):
    """Build and return a pavement layout (full pipeline by default)."""
    from auto_patch.pipeline import build_airport_pavement
    return build_airport_pavement(icao, xplane, **kw)


# Ordered geometry-mutating passes between pav_union construction and the
# final emit.  (module path, function name).  Pavement coverage of
# pav_union should hold ~100% across all of these; a drop pinpoints the
# pass that erased pavement.  Some passes run more than once in the
# pipeline — instrumentation fires on each call, so the timeline shows
# every invocation in order.  Add new geometry passes here as they appear.
PIPELINE_GEOMETRY_PASSES = [
    ("auto_patch.junction_rules", "_enforce_runway_1to1_sharing"),
    ("auto_patch.junction_rules", "widen_junctions_to_runway_corners"),
    ("auto_patch.junction_rules", "stitch_pavement_to_flat_runways"),
    ("auto_patch.seam_anchors", "split_pavement_at_seams"),
    ("auto_patch.junction_rules", "stitch_pavement_to_terminals"),
    ("auto_patch.junction_rules", "stitch_pavement_polygons"),
    ("auto_patch.junction_repair", "_merge_sliver_junctions_into_neighbours"),
    ("auto_patch.junction_repair", "_drop_thin_orphan_slivers"),
    ("auto_patch.junction_repair", "_drop_floating_orphan_junctions"),
    ("auto_patch.groundside", "_reclassify_groundside_orphan_junctions"),
]



