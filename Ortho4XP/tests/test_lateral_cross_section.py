"""The lateral CROSS-SECTION restoration (fabric Phase B, battery round).

Three facts, each of which was a real miss:

1. The emitter's span rule and the TRANSVERSE validator's span rule are
   ONE rule — the minimum width they price is the same number
   (``_BRACKET_MIN_WIDTH_M`` vs ``check_grade._TRANSVERSE_MIN_WIDTH_M``).
   Two copies drifting is exactly the census-wrapper defect class.
2. An axis running ALONG a pavement edge still yields a foot on the FAR
   edge.  The nearest-projection rule missed it whenever the corridor was
   wider than the dead lookup's 12 m fallback (CYXY apron ``shapeID 115``:
   far edge 19.7-23.2 m away, one 480 m segment, 1.5 m of cross-fall
   priced over 18 m).
3. ``station_step_m=None`` — the pre-solve call site — is untouched, so
   the fabric flags' OFF arm stays byte-identical.
"""
from __future__ import annotations

import os
import sys

import pytest
from shapely.geometry import LineString, Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from auto_patch import lateral_spine_nodes as lsn          # noqa: E402
from auto_patch.layout import ROLE_APRON                    # noqa: E402


@pytest.fixture()
def bracket_on(monkeypatch):
    """ATTEMPT 3 — the PLAIN union (bracket with its width condition
    dropped), authorized by lead ruling R-c and still default-OFF.  R-b
    (default-ON) is the width-adaptive half and needs no gate; these
    tests arm ``O4_XSECTION_BRACKET`` only where the point is the union.
    """
    monkeypatch.setenv("O4_XSECTION_BRACKET", "1")
    return True


class _Shape:
    def __init__(self, polygon, role=ROLE_APRON):
        self.polygon = polygon
        self.role = role
        self.node_altitudes = None
        self.ref = "T"


class _CL:
    def __init__(self, line, is_service=False):
        self.line = line
        self.is_service = is_service


class _Layout:
    def __init__(self, shapes, centerlines):
        self.shapes = shapes
        self.apt_taxi_centerlines = centerlines


def _corridor(width=20.0, length=480.0):
    """A long thin apron whose NEAR edge carries the axis and whose FAR
    edge is a single segment — the CYXY shape, minimally."""
    return Polygon([(0.0, 0.0), (0.0, length),
                    (width, length), (width, 0.0)])


def test_min_width_is_lockstep_with_the_transverse_validator():
    import check_grade
    assert (lsn._BRACKET_MIN_WIDTH_M
            == check_grade._TRANSVERSE_MIN_WIDTH_M), (
        "the emitter inserts the cross-section the validator prices; "
        "two different minimum widths is one law with two readers")
    # ONE span rule, all three of its numbers.  The minimum width alone
    # was not enough: the emitter also has to select the SAME span (near
    # side within the gap, hits within the censused half-width).
    assert lsn._SPAN_MAX_GAP_M == check_grade._TRANSVERSE_MAX_GAP_M
    assert lsn._SPAN_HALF_M == check_grade._TRANSVERSE_HALF_M


@pytest.mark.parametrize("axis_x, expect", [
    (0.0, True),        # axis exactly ON the near edge
    (-0.5, True),       # axis 0.5 m OUTSIDE it — the CYXY authoring
    (0.5, True),        # axis 0.5 m INSIDE it
    (-3.0, False),      # 3 m off: not this axis's corridor (gap > 1.0 m)
])
def test_the_span_rule_is_the_validators_not_a_strict_bracket(axis_x, expect):
    """THE ATTEMPT-2 MECHANISM, measured at the emitter.

    A strict both-signs bracket inserts NOTHING when every hit lands on
    one side of the section — which is the wide-corridor class itself (an
    axis running along a pavement edge, authored a few centimetres either
    way).  The validator does not use a strict bracket: it takes the
    consecutive hit pair whose near side is closest to the axis, and
    prices it when that gap is within ``_TRANSVERSE_MAX_GAP_M``.  The
    emitter now selects the same span, so the pair the law prices is the
    pair the emitter emits — for every authoring of the same corridor.
    """
    from collections import defaultdict
    from shapely.strtree import STRtree

    poly = _corridor(width=20.0)
    tree = STRtree([poly])
    inserts = defaultdict(lambda: defaultdict(list))
    cs = [(axis_x, 0.0), (axis_x, 12.0), (axis_x, 24.0)]
    lsn._bracket_feet(axis_x, 12.0, cs, 1, tree, [lsn._open(poly)], [poly],
                      inserts)
    assert bool(inserts) is expect, (
        f"axis at x={axis_x} m: the emitter and the validator must agree "
        f"on whether this corridor has a priced cross-section")


def test_axis_on_the_edge_still_gets_a_far_edge_foot():
    """R-b, DEFAULT-ON: a 20 m span exceeds the 12 m lateral pass reach,
    so the row is completed on the far edge with no gate at all."""
    poly = _corridor()
    shape = _Shape(poly)
    # The axis runs ALONG x=0 (the near edge) with ONE segment, exactly
    # the authoring the nearest-projection rule cannot serve.
    layout = _Layout([shape], [_CL(LineString([(0.0, 0.0), (0.0, 480.0)]))])
    n = lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    assert n > 0
    ring = list(shape.polygon.exterior.coords)[:-1]
    far = [p for p in ring if abs(p[0] - 20.0) < 1e-6]
    assert len(far) > 30, (
        f"the far edge kept {len(far)} vertices; the cross-section the "
        f"transverse law prices has no node to grade")
    gaps = sorted(abs(far[i + 1][1] - far[i][1])
                  for i in range(len(far) - 1))
    assert gaps[-1] <= 12.0 + 1e-6


def test_rb_is_width_adaptive_not_a_blanket_union():
    """The R-b condition, both directions.

    A span WIDER than the lateral pass reach (12 m) gets its far-side row
    — that is the wide-corridor cross-fall class.  A span the reach
    already covers gets nothing extra from R-b: the nearest-projection
    rule serves it, and inserting the bracket there too is attempt 3
    (``O4_XSECTION_BRACKET``), which measured as a trade, not a win.
    Turning R-b off restores the pre-ruling emitter exactly.
    """
    def _far_count(width, env):
        shape = _Shape(_corridor(width=width))
        layout = _Layout([shape],
                         [_CL(LineString([(0.0, 0.0), (0.0, 480.0)]))])
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        ring = list(shape.polygon.exterior.coords)[:-1]
        return len([p for p in ring if abs(p[0] - width) < 1e-6])

    assert _far_count(20.0, {}) > 30, "a 20 m span must get its far row"
    assert _far_count(20.0, {"O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS": "0"}) == 2, (
        "R-b OFF is the pre-ruling emitter: no far-edge node at all")
    # An 8 m span is inside the reach, so the far edge is served by the
    # nearest-projection rule whether R-b is on or off — R-b adds nothing.
    assert (_far_count(8.0, {})
            == _far_count(8.0, {"O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS": "0"}))


def test_narrower_than_the_law_prices_gets_no_bracket():
    """A 2 m span is below ``_BRACKET_MIN_WIDTH_M``, so the law prices no
    cross-section there and the bracket rule records none.  Asserted on
    the helper, not through the pass: the pass ALSO runs the legacy
    nearest-projection rule, which serves a 2 m corridor perfectly well
    (both edges are inside its 12 m reach) — the question here is only
    whether the span rule agrees with the validator's minimum."""
    from collections import defaultdict
    from shapely.strtree import STRtree

    poly = _corridor(width=2.0)
    tree = STRtree([poly])
    rings = [lsn._open(poly)]
    inserts = defaultdict(lambda: defaultdict(list))
    cs = [(0.0, 0.0), (0.0, 12.0), (0.0, 24.0)]
    lsn._bracket_feet(0.0, 12.0, cs, 1, tree, rings, [poly], inserts)
    assert not inserts

    wide = _corridor(width=20.0)
    tree2 = STRtree([wide])
    inserts2 = defaultdict(lambda: defaultdict(list))
    lsn._bracket_feet(0.0, 12.0, cs, 1, tree2, [lsn._open(wide)], [wide],
                      inserts2)
    assert inserts2, "a 20 m span IS priced and must get its pair"


def test_default_call_is_the_pre_fabric_behaviour():
    """``station_step_m`` unset ⇒ the legacy nearest-projection rule, so
    the pre-solve call site (and every fabric-flag OFF arm) is unchanged:
    a 20 m corridor with the axis on its edge gets NOTHING on the far
    edge, which is precisely the pre-2026-08-08 behaviour."""
    shape = _Shape(_corridor())
    layout = _Layout([shape], [_CL(LineString([(0.0, 0.0), (0.0, 480.0)]))])
    lsn.insert_lateral_spine_nodes(layout, "TEST")
    ring = list(shape.polygon.exterior.coords)[:-1]
    far = [p for p in ring if abs(p[0] - 20.0) < 1e-6]
    assert len(far) == 2


def test_service_pass_shares_one_station_densifier():
    """``_densify_to_step`` is the ONE implementation both passes use."""
    cs = [(0.0, 0.0), (0.0, 100.0)]
    out = lsn._densify_to_step(cs, 12.0)
    assert out[0] == cs[0] and out[-1] == cs[-1]
    gaps = [out[i + 1][1] - out[i][1] for i in range(len(out) - 1)]
    assert max(gaps) <= 12.0 + 1e-9
    assert min(gaps) > 0.0


@pytest.mark.parametrize("step", [12.0, 25.0])
def test_feet_land_on_both_sides_when_the_axis_is_centred(step, bracket_on):
    shape = _Shape(_corridor())
    layout = _Layout([shape], [_CL(LineString([(10.0, 0.0), (10.0, 480.0)]))])
    lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=step)
    ring = list(shape.polygon.exterior.coords)[:-1]
    near = [p for p in ring if abs(p[0]) < 1e-6]
    far = [p for p in ring if abs(p[0] - 20.0) < 1e-6]
    assert len(near) > 2 and len(far) > 2
