"""THE OPEN-CUT REGION PUBLISHER, and why it stands alone.

``bridges.publish_tunnel_open_cut_regions`` hands the portal walk's own
plan-space extent — ``_tunnel_open_cut_regions``' level and approach
zones — to ``layout.tunnel_open_cut_polys``, beside the sibling
publisher that hands on R14-1's CLAIM SET.

WHY IT HAS NO CONSUMER TODAY.  The node book's tunnel exclusion reads
the CLAIM (v1, the merged rule).  Amendments 4 and 5 of
``docs/specs/tunnel-corridor-node-book-exclusion-spec.md`` re-keyed it to
this region and were measured: the cut covers ZERO of OTHH's bore-floor
ring's 34 nodes and the claim covers 2, so neither region names the
surface, and the node-book work went to the owner as a ledger
(lane/tunnelfix e37963bc, 5c4f4400 — kept unmerged).  The PUBLISHER
survives on this branch because it is the region authority any future
design needs and because publishing it derives nothing: it is a list
flatten over records the claim pass already computes.  A published
region with a twin is inert; a region re-derived at the point of use is
the spec violation the one-authority clause exists to prevent.

The twin therefore asserts exactly two things — the publisher is
faithful to the records, and the two regions stay two.
"""
from __future__ import annotations

import types

from shapely.geometry import Polygon

from auto_patch import bridges


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout():
    return types.SimpleNamespace(shapes=[], anchor=(0.0, 0.0))


class TestTheOpenCutPublisher:

    def test_it_flattens_the_walks_own_records(self):
        """Level zone AND approach zone, in order, verbatim — the
        elevations stay with the regions (the R14-3 grade lives there),
        so only the plan-space polygons are published."""
        lay = _layout()
        level, approach = _rect(0, 0, 10, 10), _rect(10, 0, 30, 10)
        assert bridges.publish_tunnel_open_cut_regions(
            lay, [(level, approach, -1.1)]) == 2
        assert lay.tunnel_open_cut_polys == [level, approach]

    def test_a_portal_whose_walk_cannot_buffer_publishes_its_level(self):
        """``_approach_zone`` returns None for a walk it cannot buffer;
        the record still carries a level zone and must not be dropped."""
        lay = _layout()
        level = _rect(50, 50, 60, 60)
        assert bridges.publish_tunnel_open_cut_regions(
            lay, [(level, None, 2.0)]) == 1
        assert lay.tunnel_open_cut_polys == [level]

    def test_it_accumulates_across_tunnel_systems(self):
        """A tile has many systems and each publishes its own — a second
        call may never replace the first."""
        lay = _layout()
        a, b = _rect(0, 0, 10, 10), _rect(40, 40, 50, 50)
        bridges.publish_tunnel_open_cut_regions(lay, [(a, None, 0.0)])
        bridges.publish_tunnel_open_cut_regions(lay, [(b, None, 0.0)])
        assert lay.tunnel_open_cut_polys == [a, b]

    def test_nothing_to_publish_leaves_no_attribute(self):
        """No cut ⇒ no attribute ⇒ no consumer can mistake an empty
        region for a published one."""
        empty = _layout()
        assert bridges.publish_tunnel_open_cut_regions(empty, []) == 0
        assert not hasattr(empty, "tunnel_open_cut_polys")
        assert bridges.publish_tunnel_open_cut_regions(
            empty, [(None, None, 0.0)]) == 0
        assert not hasattr(empty, "tunnel_open_cut_polys")

    def test_it_derives_nothing(self):
        """ONE AUTHORITY: the publisher may read the records and flatten
        them — it may not compute a zone of its own."""
        import inspect
        src = inspect.getsource(bridges.publish_tunnel_open_cut_regions)
        for forbidden in ("buffer(", "intersection(", "difference(",
                          "unary_union(", "Polygon("):
            assert forbidden not in src, (
                f"the publisher calls {forbidden} — a second geometric "
                f"notion of 'inside the cut' is what the spec forbids")

    def test_the_two_regions_stay_two(self):
        """The CLAIM SET (re-profiled road surfaces) and the CUT (the
        ground the bore occupies) are different regions and different
        attributes — measured 0-2 of 34 nodes apart at OTHH.  Neither
        publisher may write the other's list."""
        lay = _layout()
        claim = _rect(0, 0, 10, 10)
        assert bridges.publish_tunnel_open_cut_claim_set(lay, [claim]) == 1
        assert lay.tunnel_open_cut_claim_polys == [claim]
        assert not hasattr(lay, "tunnel_open_cut_polys")
        cut = _rect(-5, -5, 15, 15)
        bridges.publish_tunnel_open_cut_regions(lay, [(cut, None, 0.0)])
        assert lay.tunnel_open_cut_claim_polys == [claim]
        assert lay.tunnel_open_cut_polys == [cut]
