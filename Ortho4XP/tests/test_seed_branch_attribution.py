"""``O4_SEED_BRANCH_ATTRIB`` — WHICH SEEDING BRANCH supplied a value.

``_seed_elevations`` has ten branches — the runway/CIFP profile, five pin
families, the flat-site fast path, the warm start off a shape's own
altitudes, the per-vertex DEM sample and the nearest-hard backfill — and
every one of them writes the same ``elev`` array.  Afterwards the value
carries no record of where it came from, which is exactly the question
round 17c's attribution turns on: a CONSTANT FILL over a run of vertices
and a PER-VERTEX DEM SAMPLE select different fixes, and no amount of code
reading separates them (the "attribution reads are not causal" trap).

The instrument is OFF by default and byte-inert; on, it stamps
``layout._seed_branch_attrib`` with the branch, the owning shape and the
ring index per node.

Fixture: the EAT twin's own layout — a real ``PavementLayout`` with a
runway whose corners seed HARD and one taxi shape inside the EAT
corridor, so two different branches fire in one call.
"""

from __future__ import annotations

import os

import pytest

from auto_patch.elevation_per_surface import solver_primitives as SP
from test_eat_ceiling import _IN, _layout, _seed  # noqa: F401

#: Every branch label the seeding pass may stamp.  A label appearing in
#: production but missing here is a branch nobody twinned.
BRANCHES = {
    "runway_cifp_profile",
    "tile_seam_pin",
    "object_bridge_deck_pin",
    "runway_end_skirt_pin",
    "eat_anchor_rect_pin",
    # ``claimed_tunnel_road_pin`` retired with R14-1's claim class and
    # ``solver_primitives._build_tunnel_road_pins`` (RULINGS 2026-08-31b,
    # redesign spec §5.1, census #37) — the seeding pass no longer has
    # that branch to stamp.
    "flat_fast_path_born_at_z0",
    "warm_start_shape_constant_fill",
    "warm_start_shape_high_low",
    "warm_start_shape_node_altitudes",
    "per_vertex_dem_sample",
    "nearest_hard_backfill",
}


@pytest.fixture
def gated(monkeypatch):
    monkeypatch.setenv("O4_SEED_BRANCH_ATTRIB", "1")


class TestTheGate:
    def test_OFF_is_the_default_and_stamps_nothing(self, monkeypatch):
        monkeypatch.delenv("O4_SEED_BRANCH_ATTRIB", raising=False)
        layout = _layout(_IN)
        _seed(layout)
        assert not getattr(layout, "_seed_branch_attrib", None)

    def test_the_seeded_VALUES_are_identical_either_way(self, monkeypatch):
        """Byte-inert: an instrument that moves a number is not an
        instrument."""
        monkeypatch.delenv("O4_SEED_BRANCH_ATTRIB", raising=False)
        _n, _b, elev_off, hard_off = _seed(_layout(_IN))
        monkeypatch.setenv("O4_SEED_BRANCH_ATTRIB", "1")
        _n2, _b2, elev_on, hard_on = _seed(_layout(_IN))
        assert list(elev_off) == list(elev_on)
        assert list(hard_off) == list(hard_on)


class TestWhatItRecords:
    def test_it_names_a_KNOWN_branch_for_every_node_it_stamps(self, gated):
        layout = _layout(_IN)
        _seed(layout)
        recorded = layout._seed_branch_attrib
        assert recorded
        assert {r["branch"] for r in recorded.values()} <= BRANCHES

    def test_the_runway_corners_are_the_CIFP_branch_with_a_ring_index(
            self, gated):
        layout = _layout(_IN)
        _n, _b, _elev, hard = _seed(layout)
        rows = [r for r in layout._seed_branch_attrib.values()
                if r["branch"] == "runway_cifp_profile"]
        assert rows
        assert all(r["role"] == "runway" for r in rows)
        assert all(isinstance(r["ring_index"], int) for r in rows)

    def test_the_EAT_pins_are_named_as_their_own_branch(self, gated):
        """The round-17c question in one assertion: an EAT anchor-rect
        pin is a PIN FAMILY, not a DEM sample and not a warm start."""
        layout = _layout(_IN)
        _n, _b, _elev, _hard = _seed(layout)
        branches = {r["branch"] for r in layout._seed_branch_attrib.values()}
        assert "eat_anchor_rect_pin" in branches

    def test_every_stamped_node_is_actually_seeded(self, gated):
        layout = _layout(_IN)
        _n, _b, elev, _hard = _seed(layout)
        for idx in layout._seed_branch_attrib:
            assert 0 <= idx < len(elev)


class TestTheFillVsSampleDISTINCTION:
    """The distinction the round exists to settle: production must be
    able to say CONSTANT FILL where a shape's single ``altitude`` filled
    a whole ring, and something else where a value came per vertex."""

    def test_the_three_warm_start_branches_are_kept_apart(self):
        import inspect
        source = inspect.getsource(SP._seed_elevations)
        assert "warm_start_shape_constant_fill" in source
        assert "warm_start_shape_high_low" in source
        assert "warm_start_shape_node_altitudes" in source

    def test_the_dem_sample_and_the_backfill_are_kept_apart(self):
        import inspect
        source = inspect.getsource(SP._seed_elevations)
        assert "per_vertex_dem_sample" in source
        assert "nearest_hard_backfill" in source

    def test_every_marked_label_is_in_the_twinned_set(self):
        """A branch label production stamps but this file does not know
        is a branch nobody twinned — the census-wrapper failure mode,
        applied to an instrument."""
        import inspect
        import re
        source = inspect.getsource(SP._seed_elevations)
        labels = set(re.findall(r'_mark\([^,]+,\s*\n?\s*"([a-z0-9_]+)"',
                                source))
        labels |= set(re.findall(r'"([a-z_0-9]*warm_start[a-z_0-9]*)"',
                                 source))
        assert labels
        assert labels <= BRANCHES
