"""THE OPEN-CUT REGION PUBLISHER — now the region of record.

``bridges.publish_tunnel_open_cut_regions`` hands the portal walk's own
plan-space extent — ``_tunnel_open_cut_regions``' level and approach
zones — to ``layout.tunnel_open_cut_polys``.

IT NOW HAS A CONSUMER.  This publisher used to stand beside a sibling
that published R14-1's CLAIM SET, and the node book's tunnel exclusion
read the CLAIM, leaving this region inert.  RULINGS 2026-08-31b retired
the claim class; ``docs/specs/linear-transport-redesign-spec.md`` §5.2
and census rows #47/#49/#51 re-key the node-book exclusion to THIS
region (``groundside._tunnel_open_cut_region``), re-home the publication
out of the retiring claim pass, and delete the claim publisher outright.
The measurement that forced the membership rule to move with the region
— the cut covers ZERO of OTHH's bore-floor ring's 34 nodes where the
claim covered 2 — is recorded in
``tests/test_tunnel_corridor_exclusion.py``'s seam-probe-4 twin, not
here.

Publishing derives nothing: it is a list flatten over records the portal
walk already computed.  A region re-derived at the point of use is the
spec violation the one-authority clause exists to prevent, so the twin
asserts the publisher is faithful to the records and computes no zone of
its own.
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

    def test_the_claim_sibling_is_retired(self):
        """RULINGS 2026-08-31b / census #48: there is now ONE published
        region.  The claim publisher and its attribute are gone, so no
        consumer can be re-keyed back to them by accident."""
        assert not hasattr(bridges, "publish_tunnel_open_cut_claim_set")
        lay = _layout()
        cut = _rect(-5, -5, 15, 15)
        bridges.publish_tunnel_open_cut_regions(lay, [(cut, None, 0.0)])
        assert lay.tunnel_open_cut_polys == [cut]
        assert not hasattr(lay, "tunnel_open_cut_claim_polys")
