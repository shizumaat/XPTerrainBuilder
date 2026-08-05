"""Unit tests for ``auto_patch.verification`` check exemptions.

These are pure synthetic-geometry tests (no X-Plane install, no airport
build) so they always run and pin the FALSE-POSITIVE exemptions the
build-time verification relies on — the same checks Ortho4XP runs on every
emitted patch.
"""
from __future__ import annotations

from shapely.geometry import Polygon

from auto_patch.layout import (
    PavementLayout, BuiltShape,
    ROLE_STUB, ROLE_JUNCTION, ROLE_GROUNDSIDE_PAVEMENT, ROLE_RUNWAY,
)
from auto_patch.verification import check_runway_profile


def _single_poly_runway_with_interior_bump() -> BuiltShape:
    """A DE-SEGMENTED single-poly runway ring (``from_single_poly``) 1000 m
    long × 30 m wide whose profile is FLAT at both physical ends but bulges
    +20 m at the mid station (x=500).

    The ring's vertices, going bottom edge then top edge, encode three
    profile stations (x = 0, 500, 1000) as interior long-edge vertices:

      * end→mid grade = 20 m / 500 m = 4.0 % — a clear violation under
        EVERY authority and code class;
      * end→end grade (what the OLD extreme-station cross-end sampler saw,
        clustering only the two physical ends) = 0 % — INVISIBLE.

    This is exactly the de-seg blind spot: the whole interior profile went
    dark once runways emitted as one ring per ref instead of a chain of
    sub-rects.

    PHASE B (region rulesets): the bump was 10 m / 2.0 % while the repo
    carried ONE blended 1.5 % runway cap.  A 1,000 m runway is aerodrome
    code 2, and ICAO Annex 14 §3.1.14 allows 2 per cent at code 1-2 — so
    the old fixture sat exactly AT its own authority's cap and no longer
    proves anything about the reader.  Doubled to 4.0 %, which is over
    cap at every code under both authorities; the reader's blind spot,
    not the cap value, is what this test is for.
    """
    coords = [
        (0.0, -15.0), (500.0, -15.0), (1000.0, -15.0),   # bottom edge
        (1000.0, 15.0), (500.0, 15.0), (0.0, 15.0),      # top edge
    ]
    node_altitudes = [0.0, 20.0, 0.0, 0.0, 20.0, 0.0]
    return BuiltShape(
        polygon=Polygon(coords), role=ROLE_RUNWAY, ref="02/20",
        node_altitudes=node_altitudes, from_single_poly=True)


def test_single_poly_runway_interior_grade_is_flagged():
    """The de-seg fix: a single-poly runway ring's interior profile stations
    are sampled per-station, so a > 1.5 % grade hidden between the physical
    ends (invisible to the extreme-station cross-end sampler) is caught."""
    shape = _single_poly_runway_with_interior_bump()
    layout = PavementLayout(icao="TEST", anchor=(35.22, -80.94), shapes=[shape])
    vios = check_runway_profile(
        layout, end_grade_cap=None, check_curvature=False)
    grade_vios = [v for v in vios if v[0] == "grade"]
    assert grade_vios, f"expected an interior grade violation, got: {vios}"
    # 20 m over 500 m = 4.0 %, judged against the runway's OWN
    # authority-keyed cap — 2.0 % here, because a 1,000 m runway is
    # aerodrome code 2 and ICAO Annex 14 §3.1.14 allows 2 per cent at code
    # 1-2 (phase B; the repo previously carried one blended 1.5 % cap for
    # every code).
    assert abs(grade_vios[0][2] - 0.04) < 1e-4, grade_vios
    assert abs(grade_vios[0][3] - 0.02) < 1e-9, grade_vios


def test_legacy_extreme_station_sampler_misses_interior_grade():
    """Pins the blind spot the fix closes: the SAME ring geometry read by the
    legacy cross-end path (``from_single_poly`` unset — extreme-station
    clustering) samples only the two physical ends, so the 4 % interior bump
    reads as a flat 0 % end→end profile and is NOT flagged.  This is what the
    validator did for every de-segmented runway before the per-station fix."""
    shape = _single_poly_runway_with_interior_bump()
    shape.from_single_poly = False
    layout = PavementLayout(icao="TEST", anchor=(35.22, -80.94), shapes=[shape])
    vios = check_runway_profile(
        layout, end_grade_cap=None, check_curvature=False)
    assert not [v for v in vios if v[0] == "grade"], (
        "legacy extreme-station sampler should have missed the interior "
        f"bump, but flagged: {vios}")
