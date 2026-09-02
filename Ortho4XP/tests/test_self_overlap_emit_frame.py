"""Invariant A1 measures the EMITTED frame — twin tests both ways.

SPAWNER RULING (lane ovfix, 2026-09-01): ``check_self_overlap``'s own
docstring legislates that no two EMITTED pavement polygons may overlap,
but the instrument read ``layout.shapes[i].polygon`` — PRE-EMIT shapely
geometry.  At SPJC, building17 ∩ building62 read 7.5351 m² pre-emit (a
~0.133 m ribbon over a 56.72 m shared boundary) while the emitted patch
reads overlap 0.0 m² / shared_edge 56.72 m — the pair TILES, because
``to_osm`` interns every ring vertex through the shared
``CanonicalPointRegistry`` at ``SHARED_VERTEX_TOL_M`` and the weld
closes the ribbon exactly.  The instrument now resolves each ring
READ-ONLY through the same registry before intersecting.  This is the
same class as the ratified quantization allowance (RULINGS 2026-09-01m):
an instrument corrected to its own stated law, not a widened bar — no
new threshold, no tolerance widening.

The two twins this file pins:

* a pair that tiles ONLY AFTER the weld (the SPJC ribbon class) PASSES;
* a genuine pre-AND-post-weld double-cover — one that SURVIVES
  interning because its overlap is far wider than the weld tolerance —
  still FAILS.

Plus the probe-spec §1x guarantee: the instrument never inserts into
the registry (a probe that interns anything moves the emitted surface).
"""
from __future__ import annotations

import sys
from pathlib import Path

from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_patch.canonical_points import CanonicalPointRegistry  # noqa: E402
from auto_patch.layout import (                                 # noqa: E402
    BuiltShape, SHARED_VERTEX_TOL_M)
from auto_patch.verification import check_self_overlap          # noqa: E402


class _Layout:
    """Minimal stand-in: ``check_self_overlap`` reads only ``shapes``,
    ``canonical_points`` and (for the report string) ``m_to_ll``."""

    def __init__(self, shapes, registry):
        self.shapes = shapes
        self.canonical_points = registry

    def m_to_ll(self, x, y):
        return (y * 1e-5, x * 1e-5)


def _shape(ring):
    return BuiltShape(polygon=Polygon(ring + [ring[0]]),
                      role="building", ref="")


# ── the SPJC ribbon class: tiles only after the weld ─────────────────

# Shape A registers its corners first (the registry's first-registered-
# owns-the-coordinate law); shape B's left edge drifted 0.133 m INTO A
# — inside SHARED_VERTEX_TOL_M, so the emitter welds B's edge onto A's
# corners and the pair tiles.  0.133 m over 60 m mirrors the measured
# SPJC pair (~0.133 m ribbon over 56.72 m, 7.5351 m²).
_A_RING = [(0.0, 0.0), (30.0, 0.0), (30.0, 60.0), (0.0, 60.0)]
_B_RIBBON_RING = [(29.867, 0.0), (60.0, 0.0), (60.0, 60.0),
                  (29.867, 60.0)]


def _ribbon_layout():
    registry = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    for x, y in _A_RING:            # construction-order claim: A owns
        registry.get_or_add(x, y)   # the canonical coordinates
    return _Layout([_shape(_A_RING), _shape(_B_RIBBON_RING)], registry)


def test_the_ribbon_fixture_really_overlaps_pre_weld():
    """Frame check (the fixture only means something if the raw rings
    DO overlap past the noise floor — the pre-fix instrument flagged
    exactly this): ~0.133 m x 60 m = ~7.98 m² pre-weld."""
    raw = (Polygon(_A_RING + [_A_RING[0]])
           .intersection(Polygon(_B_RIBBON_RING + [_B_RIBBON_RING[0]])))
    assert raw.area > 5.0, (
        f"raw pre-weld overlap {raw.area:.4f} m² no longer clears the "
        f"instrument's floors — the fixture stopped reproducing the "
        f"SPJC building17 ∩ building62 ribbon class")
    (ax, ay), (bx, by) = _A_RING[1], _B_RIBBON_RING[0]
    d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    assert d < SHARED_VERTEX_TOL_M, (
        "the drifted corner is outside the emitter's weld tolerance — "
        "the emitter would NOT close this ribbon")


def test_a_pair_that_tiles_only_after_the_weld_passes():
    """The emit-time weld resolves B's drifted edge onto A's canonical
    corners, so the EMITTED pair tiles (overlap 0.0, shared edge) —
    invariant A1's own frame.  The instrument must agree."""
    layout = _ribbon_layout()
    pairs = check_self_overlap(layout)
    assert pairs == [], (
        f"emit-frame instrument still flags the welded-tiling pair: "
        f"{pairs} — it is measuring the pre-emit frame A1 does not "
        f"legislate")


def test_the_instrument_never_interns_into_the_registry():
    """Probe-spec §1x: ``get``, never ``get_or_add`` — an instrument
    that interns anything moves the emitted surface (round 6: SPJC,
    +1 node, 86 altitudes)."""
    layout = _ribbon_layout()
    size_before = layout.canonical_points.size
    check_self_overlap(layout)
    assert layout.canonical_points.size == size_before, (
        "check_self_overlap inserted canonical points — the instrument "
        "moved the surface it measures")


# ── a genuine double-cover survives interning and still fails ────────

# B's left edge sits 2.0 m inside A — four times the weld tolerance, so
# interning resolves every corner to ITSELF and the 2 m x 60 m
# double-cover survives into the emitted frame.
_B_COVER_RING = [(28.0, 0.0), (60.0, 0.0), (60.0, 60.0), (28.0, 60.0)]


def test_a_genuine_pre_and_post_weld_overlap_still_fails():
    registry = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    for ring in (_A_RING, _B_COVER_RING):   # both shapes' corners are
        for x, y in ring:                   # registered — the overlap
            registry.get_or_add(x, y)       # SURVIVES interning
    layout = _Layout([_shape(_A_RING), _shape(_B_COVER_RING)], registry)
    pairs = check_self_overlap(layout)
    assert len(pairs) == 1, (
        f"expected the 2 m x 60 m double-cover to be flagged once, "
        f"got {pairs}")
    area, idx_a, idx_b, _loc = pairs[0]
    assert (idx_a, idx_b) == (0, 1)
    assert abs(area - 120.0) < 1.0, (
        f"flagged area {area:.4f} m² is not the real double-cover "
        f"(~120 m²) — the emit-frame resolution moved a genuine "
        f"overlap")


def test_no_registry_reads_the_raw_frame():
    """A layout without a registry (defensive path) measures the raw
    rings: the instrument may over-report there, never hide."""
    layout = _Layout([_shape(_A_RING), _shape(_B_RIBBON_RING)], None)
    pairs = check_self_overlap(layout)
    assert len(pairs) == 1 and pairs[0][0] > 5.0


# ── the EMIT-FRAME RE-CLIP twins (lane weldov, attribution round on
# RULINGS 2026-09-01w's reveal) ──────────────────────────────────────
#
# The corrected instrument revealed weld-MINTED double-covers: a ring
# vertex parked exactly ON its neighbour's edge whose 0.5 m bucket is
# claimed by a canonical point OFF that edge emits at the claimant's
# coordinate, bowing the ring into the neighbour (SPJC 13 pairs /
# 5.13 m², CYXY 2 / 0.59 m², every pair raw-overlap 0.000000 m²).
# ``conformance.reclip_emit_frame_overlaps`` is the recorded last-word
# re-clip for exactly this class: the ring that GAINED area is
# re-clipped against its neighbour in the frame the weld produces.
# Twins: a weld that would bow a ring into its neighbour re-clips and
# the pair stops overlapping; a lawful shared edge is untouched; a
# never-yield (runway-family) ring is never mutated.

from auto_patch.conformance import reclip_emit_frame_overlaps  # noqa: E402


def _tiling_pair(role_a="junction", role_b="junction",
                 mid_vertex_on="B", attractor=None):
    """A (0..30 × 0..60) and B (30..60 × 0..60) tile along x=30.  One
    of them carries a mid-edge vertex at (30, 30) on the shared edge —
    the conformance-inserted, non-canonical vertex class.  A's corners
    (and B's shared ones) are registered canonical; ``attractor``, when
    given, is registered after them (the zone-node / triangulation-
    lookup pollution class the attribution round measured)."""
    a_ring = [(0.0, 0.0), (30.0, 0.0), (30.0, 60.0), (0.0, 60.0)]
    b_ring = [(30.0, 0.0), (60.0, 0.0), (60.0, 60.0), (30.0, 60.0)]
    if mid_vertex_on == "B":
        b_ring = [(30.0, 0.0), (60.0, 0.0), (60.0, 60.0), (30.0, 60.0),
                  (30.0, 30.0)]
    else:
        a_ring = [(0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (30.0, 60.0),
                  (0.0, 60.0)]
        # keep the mid vertex non-canonical: register corners only.
    registry = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    for x, y in [(0.0, 0.0), (30.0, 0.0), (30.0, 60.0), (0.0, 60.0)]:
        registry.get_or_add(x, y)
    if attractor is not None:
        registry.get_or_add(*attractor)
    sa = BuiltShape(polygon=Polygon(a_ring + [a_ring[0]]), role=role_a,
                    ref="")
    sb = BuiltShape(polygon=Polygon(b_ring + [b_ring[0]]), role=role_b,
                    ref="")
    return _Layout([sa, sb], registry)


def test_a_weld_bow_is_reclipped_and_the_pair_stops_overlapping():
    """B's on-edge vertex (30, 30) resolves to the attractor
    (29.7, 30) INSIDE A — the emit frame reads a ~9 m² bow.  The
    re-clip makes B yield the gained area; the pair stops overlapping
    and A (which gained nothing) is untouched."""
    layout = _tiling_pair(attractor=(29.7, 30.0))
    before = check_self_overlap(layout)
    assert before and before[0][0] > 5.0, (
        f"fixture no longer reproduces the weld-minted bow: {before}")
    a_coords_before = list(layout.shapes[0].polygon.exterior.coords)
    n = reclip_emit_frame_overlaps(layout, "TEST")
    assert n == 1, f"expected exactly one yielding shape, got {n}"
    after = check_self_overlap(layout)
    assert after == [], (
        f"re-clip left emit-frame overlap pairs standing: {after}")
    assert list(layout.shapes[0].polygon.exterior.coords) == \
        a_coords_before, "the non-gaining neighbour was mutated"
    assert abs(layout.shapes[1].polygon.area - 1800.0) < 0.5, (
        f"yielder area {layout.shapes[1].polygon.area:.2f} — the clip "
        f"took more than the welded bow")


def test_a_lawful_shared_edge_is_untouched():
    """No attractor: the pair tiles exactly in both frames.  The
    re-clip must do nothing — not one coordinate moves."""
    layout = _tiling_pair(attractor=None)
    coords_before = [list(s.polygon.exterior.coords)
                     for s in layout.shapes]
    n = reclip_emit_frame_overlaps(layout, "TEST")
    assert n == 0, "re-clip acted on a lawful shared edge"
    assert [list(s.polygon.exterior.coords)
            for s in layout.shapes] == coords_before, (
        "a lawful shared edge was mutated")


def test_the_weld_closed_ribbon_pair_stays_closed():
    """The 2026-09-01w ribbon fixture (tiles only after the weld) has
    no emit-frame overlap — the re-clip must not touch it."""
    layout = _ribbon_layout()
    coords_before = [list(s.polygon.exterior.coords)
                     for s in layout.shapes]
    assert reclip_emit_frame_overlaps(layout, "TEST") == 0
    assert [list(s.polygon.exterior.coords)
            for s in layout.shapes] == coords_before


def test_a_runway_never_yields_the_neighbour_does():
    """The runway's own on-edge vertex is pulled INTO its neighbour by
    an attractor — the runway is never-yield, so the NEIGHBOUR yields
    the overlap and the runway ring is byte-untouched."""
    layout = _tiling_pair(role_a="runway", role_b="junction",
                          mid_vertex_on="A", attractor=(30.3, 30.0))
    before = check_self_overlap(layout)
    assert before and before[0][0] > 5.0, (
        f"fixture no longer reproduces the runway-bow class: {before}")
    rwy_before = list(layout.shapes[0].polygon.exterior.coords)
    n = reclip_emit_frame_overlaps(layout, "TEST")
    assert n == 1
    assert check_self_overlap(layout) == []
    assert list(layout.shapes[0].polygon.exterior.coords) == rwy_before, (
        "the runway ring was mutated — never-yield violated")
