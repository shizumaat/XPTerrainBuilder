"""Owner constants (lot 5 %, service road 8 %) + the merged-surface law.

Rulings: ``docs/RULINGS.md`` — "Owner constants: lot 5%, service road 8%"
(2026-08-03, approved on the primary-source research) and the
merged-surface ruling of the same day: *the merged lot+road polygon is
ONE surface and gets graded as one*.

The constants are LAW, so their test twin asserts the cited numbers
directly (a test that read the constant back would assert nothing).  The
merged-surface law is GENERATION-BINDING, so its twin asserts the
property of the produced surface, not the presence of a call.
"""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Polygon


# ═════════════════════════════════════════════════════════════════════
# helpers
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    return types.SimpleNamespace(shapes=list(shapes))


# ═════════════════════════════════════════════════════════════════════
# the constants themselves
# ═════════════════════════════════════════════════════════════════════

class TestOwnerConstants:
    """The two numbers the owner approved on 2026-08-03, with their
    citations recorded in ``docs/STANDARDS.md`` rows 25/27."""

    def test_the_lot_cap_is_the_walking_surface_ceiling(self):
        # ADA 2010 §403.3 running slope 1:20; Iowa SUDAS §8B-1; City of
        # Santa Barbara Parking Design Standards §D.5.  The CONSTANT is
        # unchanged by the 2026-08-12 ruling — only the role map moved
        # (see below); the fan-ramp law and the groundside band's
        # off-route pricing still read this number.
        from auto_patch import config as cfg
        assert cfg.GROUNDSIDE_MAX_GRADE == pytest.approx(0.050)

    def test_groundside_pavement_grades_at_the_road_limit(self):
        """Owner ruling 2026-08-12: groundside_pavement's cap IS the road
        limit — the SAME constant, never a second number.

        Identity, not value: a copied 0.080 would drift the first time
        the road limit is re-ruled, and "one constant, no second number"
        is the ruling's own emphasis (the owner cited "~7 %"; the
        substance is the road limit itself).
        """
        from auto_patch import config as cfg
        assert (cfg.ROLE_GRADE_LIMITS["groundside_pavement"]
                is cfg.ROLE_GRADE_LIMITS["service_road"])
        assert (cfg.ROLE_GRADE_LIMITS["groundside_pavement"]
                is cfg.SERVICE_ROAD_MAX_GRADE)
        assert cfg.ROLE_GRADE_LIMITS["groundside_pavement"] \
            != pytest.approx(cfg.GROUNDSIDE_MAX_GRADE)

    def test_the_service_road_cap_is_the_v2_road_law(self):
        # Was VDOT GS-9's level-terrain 8 %; owner RULINGS 2026-10-07b (2):
        # roads and ramps grade up to 10 %.  The census constant IS the
        # law value — read from the law, never retyped.
        from auto_patch import config as cfg
        from auto_patch_v2.law import tables as T
        law = T.load_default()
        road = float(law.tables.common.road_max_grade)
        assert cfg.SERVICE_ROAD_MAX_GRADE == pytest.approx(road)
        assert cfg.ROLE_GRADE_LIMITS["service_road"] == pytest.approx(road)

    def test_service_junction_rides_the_service_road_constant(self):
        """The COUPLING the round flags for the owner: junctions are not a
        separate number.  If they are ever split, this test is the one that
        must be changed deliberately."""
        from auto_patch import config as cfg
        assert (cfg.ROLE_GRADE_LIMITS["service_junction"]
                is cfg.ROLE_GRADE_LIMITS["service_road"])

    def test_the_landside_caps_stay_distinct_from_the_tunnel_ramp(self):
        """Several dispatch sites resolve a cap by VALUE equality; the lot
        cap used to collide with the tunnel ramp's 4 %. It must not
        collide with anything now.

        NOTE (2026-08-12): the CONSTANTS below stay distinct, but the ROLE
        MAP now gives `groundside_pavement` and `service_road` the same
        number by owner ruling. The one value-equality consumer that sees
        it is `grade_law._cap_runs`, which segments a road's lateral
        stations at cap CHANGES — a road/lot cross-section is now one run
        instead of two, which is what "same cap" means and is why this
        test pins the constants, not the map.

        NOTE (RULINGS 2026-09-12m, owner): the tunnel ramp is no longer one
        of the distinct numbers — "a tunnel ramp IS a road", so it takes
        SERVICE_ROAD_MAX_GRADE exactly, and a ramp/road cross-section is
        deliberately ONE `_cap_runs` run for the same reason the road/lot
        one is. The collision this test guards against is a ramp sharing an
        UNRELATED cap; the deliberate identity is asserted, not forbidden."""
        from auto_patch import config as cfg
        assert cfg.TUNNEL_RAMP_MAX_GRADE == pytest.approx(cfg.SERVICE_ROAD_MAX_GRADE)
        vals = [cfg.GROUNDSIDE_MAX_GRADE, cfg.SERVICE_ROAD_MAX_GRADE,
                cfg.TAXI_MAX_GRADE,
                cfg.APRON_MAX_GRADE, cfg.TAXI_MAX_GRADE_NARROW]
        assert len(set(round(v, 6) for v in vals)) == len(vals)


# ═════════════════════════════════════════════════════════════════════
# the merged surface is ONE surface
# ═════════════════════════════════════════════════════════════════════


class TestTheLimitersRideTheRoadCap:
    """THE LAW IS THE ROAD LIMIT; THE SHAPING SITS BELOW IT (owner
    2026-08-12, lead ruling on the measurement).

    Two numbers on purpose.  ``ROLE_GRADE_LIMITS["groundside_pavement"]``
    IS the road cap — that is the owner's ruling and it is what the
    validator adjudicates a lot against.  Every LIMITER in
    ``groundside`` shapes at ``GROUNDSIDE_MAX_GRADE`` (5 %), which is
    the MARGIN that makes the law reachable: measured, pointing the
    limiters at the cap put lots exactly ON it and the emitted 2-dp
    quantization over short chords tipped families of pairs 0.08-2.36 pp
    past it (CYXY within_shape 4 → 62 on ONE lot, KMCI 420 → 490,
    +58/+75 adjudicated) while the road-stub class it was supposed to
    clear did not move (transverse Δ0 at both airports).

    These tests fail if either half drifts: if the LAW stops being the
    road cap, or if a limiter is re-pointed AT the cap with no margin.
    """

    def test_the_law_is_the_road_cap(self):
        from auto_patch import config as cfg
        # Identity WITHIN one config instance: the alias is the road cap
        # object, so re-ruling the road limit re-rules the lot with it.
        assert cfg.GROUNDSIDE_PAVEMENT_MAX_GRADE is cfg.SERVICE_ROAD_MAX_GRADE
        assert (cfg.ROLE_GRADE_LIMITS["groundside_pavement"]
                is cfg.ROLE_GRADE_LIMITS["service_road"])
        # …and the walking-surface constant is still its own thing, for
        # the laws that kept it.
        assert cfg.GROUNDSIDE_MAX_GRADE == pytest.approx(0.050)
        assert cfg.FAN_RAMP_CAP is cfg.GROUNDSIDE_MAX_GRADE


