"""Classification round — the lateral-contiguity grade law, the scorer's
service-adjacency feature, the needle-collapse source discriminator and the
drainage second-parent lockstep.

Spec: ``docs/specs/classification-round-spec.md``.  Owner rulings:
``docs/RULINGS.md`` (lateral-contiguity grade law, FINAL 2026-08-02;
grade-law completeness standard).

Every law here is TWO-SIDED by requirement (completeness standard): the
generation-binding constraint and its validator twin must read the same
number, so the tests assert the pair, not one side.
"""
import math
import os
import types

from shapely.geometry import Polygon


# ═════════════════════════════════════════════════════════════════════
# §2 — the law itself
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §2 — the emitter (the owner's two thought tests)
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    return types.SimpleNamespace(shapes=list(shapes))


# ═════════════════════════════════════════════════════════════════════
# §1 — the scorer's service-adjacency feature
# ═════════════════════════════════════════════════════════════════════

class TestServiceAdjacencyFeature:
    """``service_adj``: road-width pavement sharing a SUBSTANTIAL edge with
    the service network is a service road, never a landside lot."""


    def test_the_weight_votes_service(self):
        from auto_patch.config import PAVEMENT_SCORE_WEIGHTS
        w = PAVEMENT_SCORE_WEIGHTS["service_adj"]
        assert set(w) == {"SERVICE"}
        # It must be able to answer the GROUNDSIDE case that demoted the
        # HECA class: road_cover 2.0 + runway_disconnected 2.0 = 4.0 vs
        # SERVICE's road_cover 0.5 + road_narrow 2.5 = 3.0.
        assert w["SERVICE"] >= 1.0


# ═════════════════════════════════════════════════════════════════════
# §3 — the needle-collapse SOURCE discriminator
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §4 — the drainage second-parent lockstep
# ═════════════════════════════════════════════════════════════════════

class TestDrainageParentSelection:


    def test_validator_search_is_sound(self):
        """The measured HECA defect: a parent whose nearest edge lies just
        outside the first cell ring is NEARER than one inside it.  The
        search must find it."""
        import sys
        from pathlib import Path
        tools = str(Path(__file__).resolve().parent.parent / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import check_grade as CG

        # station at the origin; parent "near" sits 67 m away (outside the
        # 40 m seed ring), parents "far1"/"far2" sit ~92 m away.
        rings = [
            ("near", [(60.0, -5.0, 99.0), (80.0, -5.0, 99.0),
                      (80.0, 5.0, 99.0), (60.0, 5.0, 99.0)]),
            ("far1", [(-120.0, -5.0, 95.0), (-95.0, -5.0, 95.0),
                      (-95.0, 5.0, 95.0), (-120.0, 5.0, 95.0)]),
            ("far2", [(-5.0, 90.0, 96.0), (5.0, 90.0, 96.0),
                      (5.0, 120.0, 96.0), (-5.0, 120.0, 96.0)]),
        ]
        grid = {}
        c = CG._SPINE_PARENT_CELL_M
        for si, (_wid, ring) in enumerate(rings):
            for ei in range(len(ring)):
                a, b = ring[ei], ring[(ei + 1) % len(ring)]
                x0, x1 = sorted((a[0], b[0]))
                y0, y1 = sorted((a[1], b[1]))
                for gx in range(int(x0 // c), int(x1 // c) + 1):
                    for gy in range(int(y0 // c), int(y1 // c) + 1):
                        grid.setdefault((gx, gy), []).append((si, ei))
        picked = CG._nearest_edge_alt_by_way(0.0, 0.0, rings, grid)
        assert [p[1] for p in picked[:2]] == ["near", "far2"]
        assert math.isclose(picked[0][0], 60.0, abs_tol=0.01)
