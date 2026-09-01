"""ONE RAMP SURFACE PER DESCENDING RUN — the emitter-level law.

Spec ``docs/specs/linear-transport-redesign-spec.md`` §5-SUPPLEMENT item
1 (spec author 2026-08-31), which closes the gap Batch 3's measurement
exposed and REFUTES census #31 as scoped:

    The retired stand-down was doing double duty as the SYNTHETIC ramp
    de-duplicator (measured: ramps 22 -> 95 without it).  The law "one
    ramp surface descending the corridor centre" is enforced AT THE
    EMITTER: consecutive ramp strips along one corridor chain merge into
    ONE surface per descending run before emission — never a post-pass
    re-creating the stand-down.

The owner law it serves is RULINGS 2026-08-30 (canonical tunnel mouth):
*"ONE ramp surface descending the corridor centre to the mouth line …
no second road shape may share the corridor."*
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch import bridges
from auto_patch.layout import PavementLayout, ROLE_TUNNEL_RAMP


def _layout():
    return PavementLayout("OTHH", anchor=(25.0, 51.0))


def _straight_run(n_seg: int, half: float = 4.0, z0: float = -1.0,
                  dz: float = 0.25, x0: float = 0.0):
    """A descending run of ``n_seg`` strips along +y, ``half`` wide."""
    st = []
    quads = []
    for k in range(n_seg + 1):
        y = 10.0 * k
        st.append(((x0 + half, y), (x0 - half, y), z0 + dz * k))
    for k in range(n_seg):
        (lx, ly), (rx, ry), ea = st[k]
        (lx2, ly2), (rx2, ry2), eb = st[k + 1]
        quads.append((Polygon([(lx, ly), (lx2, ly2), (rx2, ry2), (rx, ry)]),
                      max(ea, eb), min(ea, eb)))
    return {"st": st, "quads": quads}


def _ramps(lay):
    return [s for s in lay.shapes
            if s.role == ROLE_TUNNEL_RAMP and s.ref == "tunnel_ramp"]


class TestOneSurfacePerRun:

    def test_eight_strips_emit_one_surface(self):
        """The measured defect class in miniature: eight consecutive
        strips are ONE descending run and must emit ONE surface."""
        lay = _layout()
        n = bridges._emit_merged_ramp_runs(lay, [_straight_run(8)])
        assert n == 1
        assert len(_ramps(lay)) == 1

    def test_the_merged_ring_is_the_strips_own_boundary(self):
        """Not a union and not a buffer: one vertex per station per
        side, left forward then right back, so no corner is rounded
        under the wall band that is offset from it."""
        lay = _layout()
        run = _straight_run(3, half=4.0)
        bridges._emit_merged_ramp_runs(lay, [run])
        shape = _ramps(lay)[0]
        coords = list(shape.polygon.exterior.coords)[:-1]
        assert len(coords) == 2 * len(run["st"])
        # area of a 8 m wide, 30 m long strip
        assert shape.polygon.area == pytest.approx(8.0 * 30.0, rel=1e-9)

    def test_altitudes_ride_per_vertex_and_both_sides_share_a_station(self):
        """A multi-segment run is not a sloped RECT, so the profile is
        per vertex; a ramp is laterally level (RULINGS 2026-08-25g) so
        the two sides of one station carry one value."""
        lay = _layout()
        run = _straight_run(3, z0=-1.0, dz=0.25)
        bridges._emit_merged_ramp_runs(lay, [run])
        shape = _ramps(lay)[0]
        alts = list(shape.node_altitudes)
        assert alts == [-1.0, -0.75, -0.5, -0.25, -0.25, -0.5, -0.75, -1.0]
        assert shape.altitude is None
        assert shape.altitude_high is None and shape.altitude_low is None

    def test_the_descending_profile_survives_the_merge(self):
        """The whole point of the surface: it still descends."""
        lay = _layout()
        bridges._emit_merged_ramp_runs(lay, [_straight_run(6)])
        alts = _ramps(lay)[0].node_altitudes
        assert min(alts) == pytest.approx(-1.0)
        assert max(alts) == pytest.approx(-1.0 + 0.25 * 6)


class TestRunsBreakWhereTheEmitterBrokeThem:

    def test_two_runs_emit_two_surfaces(self):
        """A run BREAKS wherever a segment was skipped (too short,
        throat-paved, yielded to an object trench).  Merging across the
        gap would pave ground the emitter deliberately left."""
        lay = _layout()
        n = bridges._emit_merged_ramp_runs(
            lay, [_straight_run(3), _straight_run(2, x0=200.0)])
        assert n == 2
        assert len(_ramps(lay)) == 2

    def test_a_single_segment_run_still_emits_one_surface(self):
        lay = _layout()
        assert bridges._emit_merged_ramp_runs(lay, [_straight_run(1)]) == 1
        assert len(_ramps(lay)) == 1

    def test_no_runs_emit_nothing(self):
        lay = _layout()
        assert bridges._emit_merged_ramp_runs(lay, []) == 0
        assert lay.shapes == []


class TestTheFallbackIsTodaysGeometry:

    def test_a_self_intersecting_run_falls_back_to_its_quads(self):
        """A hairpin chain can self-intersect its own offset.  Dropping
        the ramp would trade a duplicate for a HOLE, so the run's
        original quads emit exactly as before the supplement."""
        lay = _layout()
        # a run whose left/right offsets cross: stations fold back on
        # themselves, so the strip boundary is not a simple ring
        st = [((4.0, 0.0), (-4.0, 0.0), -1.0),
              ((4.0, 10.0), (-4.0, 10.0), -0.5),
              ((-4.0, 5.0), (4.0, 5.0), 0.0)]
        quads = [(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), 0.0, -1.0),
                 (Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]), 0.5, 0.0)]
        n = bridges._emit_merged_ramp_runs(lay, [{"st": st,
                                                  "quads": quads}])
        assert n == 2, "the fallback must emit the run's own quads"
        emitted = _ramps(lay)
        assert len(emitted) == 2
        # …and in the pre-supplement encoding: a sloped rect
        assert emitted[0].altitude_high == pytest.approx(0.0)
        assert emitted[0].altitude_low == pytest.approx(-1.0)

    def test_a_degenerate_run_falls_back_rather_than_dropping(self):
        lay = _layout()
        st = [((0.0, 0.0), (0.0, 0.0), -1.0),
              ((0.0, 0.0), (0.0, 0.0), -0.5)]
        quads = [(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), -0.5, -1.0)]
        assert bridges._emit_merged_ramp_runs(
            lay, [{"st": st, "quads": quads}]) == 1
        assert len(_ramps(lay)) == 1


class TestItIsNotAPostPass:
    """The supplement forbids a post-pass 're-creating the stand-down'."""

    def test_the_merge_is_called_from_the_chain_emitter(self):
        import inspect
        src = inspect.getsource(bridges._emit_portal_cluster)
        assert "_emit_merged_ramp_runs(layout, _ramp_runs)" in src, (
            "the merge must run inside the chain emitter, before "
            "emission — a later sweep over layout.shapes would be the "
            "stand-down again")

    def test_the_retired_stand_down_is_still_gone(self):
        assert not hasattr(bridges, "_stand_down_synthetic_over_claimed")
