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
    """The bracket rule is PARKED default-OFF (attempt cap reached — see
    ``lateral_spine_nodes._bracket_feet``).  The tests that exercise it
    arm its gate explicitly, so the default arm stays the measured one."""
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


def test_axis_on_the_edge_still_gets_a_far_edge_foot(bracket_on):
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
