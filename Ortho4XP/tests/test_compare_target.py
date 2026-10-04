"""Structural-fidelity gates against the reference fixture outputs.

``tests/fixtures/SPJC_target.osm`` and the per-tile
``tests/fixtures/SPLP_target_tile*.osm`` are the canonical builds
(regenerated 2026-07-05 with the curve-native / route-arc global-slice
pipeline).  Every code change must continue
to reproduce these outputs: the tests compare the produced layout
against each target shape-for-shape via
``tools/compare_target.match_by_role`` and assert that each role's
match count stays at or above an established baseline.

If a future change drops matched shapes below the baseline — even
if every invariant test still passes — these gates fail.  That makes
regressions visible the way the comparison tool does manually.

Baseline reset 2026-05-13 after:
  * diagonal V3-style stub trapezoid emission (Approach A) +
    ``db_local ≥ 15°`` digit→STUB classifier tightening.
  * Seam-anchor architecture: ``split_pavement_at_seams`` +
    ``apply_seam_dem_anchors`` + Stage A runway regrade +
    unified-Jacobi seam-HARD override (seam wins).
  * Tile-cut bridge polygons removed.
  * ``_resample_node_altitudes_nn`` upgraded to edge interpolation
    (cut-edge vertices use linear gradient of the underlying old
    edge instead of nearest-neighbour).

Baseline re-cut 2026-05-20 (SPJC + SPLP) after: grade[SPLP]
runway-corner nudge, floating-orphan junction drop, and the Rule-2
sloping-edge re-snap.  Per-role floors set ~5 % below the new target
counts.

Add new airport baselines as ``tests/fixtures/<ICAO>_target.osm``
files come online.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from conftest import xplane_available, xplane_root


# ══════════════════════════════════════════════════════════════════════
# ADJUDICATED RED, 2026-08-04 (test-maintenance lane) — STALE FIXTURES.
# All three gates in this module (SPJC + both SPLP tiles) are RED at
# HEAD and have been for the whole campaign.  The cause is NOT a
# regression in the builder; it is that the target fixtures are stale.
# Recorded here so the next session does not re-derive it.
#
# EVIDENCE.
# 1. The fixtures have never been re-cut since the engine was vendored:
#    ``git log -1 -- tests/fixtures/SPJC_target.osm`` is 38b3eaf
#    (2026-07-20), and 73 commits have touched ``src/auto_patch/`` since.
#    The notes below stop at the 2026-07-17b cut.
# 2. A whole ROLE that did not exist at cut time is now emitted:
#    ``ols_cut`` (``layout.ROLE_OLS_CUT``, introduced by 3cdc8a3
#    "Runway-end + pocket + OLS round") shows target=0 against out=17
#    (SPJC), out=6 (SPLP -77) and out=3 (SPLP -78).  A role can only
#    read target=0 / out>0 if the emitter landed after the fixture.
#    ``service_junction`` (SPLP target=0, out=9 / out=18) and
#    ``tunnel_ramp`` (SPLP -78 target=0, out=7) are the same shape.
# 3. The fixture and the floors below are DESYNCED from each other:
#    the SPJC floor comment records retaining_wall as "9 of 9 current",
#    but the fixture it is compared against carries target=40 (out=6).
#    The two inputs to this gate disagree about what "current" was.
#
# CONSEQUENCE: the gate currently fires unconditionally, so it can no
# longer do its job — detect a NEW regression against a known-good
# partition.  Its measured state at HEAD (e07a3f6), for the re-cut:
#   SPJC       matched 525 / floor 736
#   SPLP -77   matched  51 / floor 121
#   SPLP -78   matched  80 / floor 165
#
# ACTION DELIBERATELY NOT TAKEN HERE: re-cutting
# (``tools/build_target_osm.py`` + floors = int(0.95 x new), the
# convention every prior cut used).  Two reasons.  (a) Every previous
# re-cut in this file's history carries an owner sign-off and an
# attribution of the reshape it absorbs; re-baselining inside a
# test-maintenance pass would absorb whatever is in the tree by
# narrative rather than by attribution.  (b) A cut taken at e07a3f6
# would be stale again within hours — several lanes still to land
# (seam v4, the flip batch, the terrace default) reshape this exact
# partition.  The re-cut belongs AFTER feature freeze, at the release
# tip, where it is both valid and attributable.
# ══════════════════════════════════════════════════════════════════════


_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


pytestmark = [
    pytest.mark.skipif(
        not xplane_available(),
        reason="X-Plane install not found (set XPLANE_ROOT to override)",
    ),
]


# ══════════════════════════════════════════════════════════════════════
# THE SCOPED IoU (added 2026-08-28 for the HECA round-4 §H3 acceptance;
# promoted from the hecar2 lane's ``surgery_diff`` scratch reader on its
# SECOND use, RULINGS 7e90032 — a parameter on a near-fit, never a fork)
# ══════════════════════════════════════════════════════════════════════

def _shp(poly, role="apron", shape_id="582", source="target"):
    import compare_target as CT
    return CT.OsmShape(way_id="-1", role=role, aeroway="apron", ref="",
                       polygon=poly, source=source, shape_id=shape_id)


def test_scoped_iou_is_1_when_the_build_kept_exactly_the_reference():
    import compare_target as CT
    from shapely.geometry import box
    foot = box(0, 0, 100, 100)
    ref = box(0, 0, 100, 80)
    out = [_shp(ref, source="output")]
    r = CT.envelope_iou([_shp(ref)], out, [_shp(foot)], "582")
    assert r is not None
    assert r["iou"] == pytest.approx(1.0)
    assert r["cut_reference_m2"] == pytest.approx(2000.0)
    assert r["cut_built_m2"] == pytest.approx(2000.0)


def test_scoped_iou_falls_when_the_build_keeps_the_whole_footprint():
    """The measured HECA state: the reference removes 17.7 % of apron
    582 and the build keeps it, so the IoU is the reference's own share
    of the footprint."""
    import compare_target as CT
    from shapely.geometry import box
    foot = box(0, 0, 100, 100)
    ref = box(0, 0, 100, 80)
    r = CT.envelope_iou([_shp(ref)], [_shp(foot, source="output")],
                        [_shp(foot)], "582")
    assert r["iou"] == pytest.approx(0.8, abs=1e-6)
    assert r["retained_outside_reference_m2"] == pytest.approx(2000.0)


def test_scoped_iou_clips_to_the_footprint_so_neighbours_do_not_count():
    """Only what the build emitted INSIDE the footprint is the retained
    region — an adjacent apron is not this shape's extent."""
    import compare_target as CT
    from shapely.geometry import box
    foot = box(0, 0, 100, 100)
    ref = box(0, 0, 100, 80)
    out = [_shp(ref, source="output"),
           _shp(box(200, 0, 300, 100), source="output", shape_id="999")]
    r = CT.envelope_iou([_shp(ref)], out, [_shp(foot)], "582")
    assert r["iou"] == pytest.approx(1.0)


def test_scoped_iou_reports_nothing_when_the_shape_id_does_not_join():
    import compare_target as CT
    from shapely.geometry import box
    assert CT.envelope_iou([_shp(box(0, 0, 10, 10))], [],
                           [_shp(box(0, 0, 10, 10), shape_id="X")],
                           "582") is None
