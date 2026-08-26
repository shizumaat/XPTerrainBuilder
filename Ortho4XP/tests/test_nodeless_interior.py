"""THE NODELESS-INTERIOR INSTRUMENT — twins for §2 of
docs/specs/heca-apron-round2-spec.md.

The instrument exists because the census is STRUCTURALLY BLIND to a
region with no emitted nodes: every family table prices PAIRS OF EMITTED
NODES, so an apron interior the slice never cut contributes zero rows
and reads as compliant however wrong its surface is.  HECA's 215 x 430 m
void passed three rounds of censuses at 1,679 while carrying a visible
cliff at 30.1289374, 31.4052385.

Twins, per the spec: a synthetic apron with an empty 100 m disk gives a
line + a sidecar count; a densely-cut apron gives zero.  Plus the
registration twin (an emitted sidecar key classified nowhere fails
``test_harness``) and the sidecar round-trip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.nodeless_interior import (find_nodeless_interiors,
                                          largest_nodeless_disk,
                                          report_nodeless_interiors)


ANCHOR = (30.12, 31.40)


class _Shape:
    def __init__(self, polygon, role="apron", ref=""):
        self.polygon = polygon
        self.role = role
        self.ref = ref


def _square(side):
    h = side / 2.0
    return Polygon([(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)])


def _ring_vertices(side, step):
    """Vertices ON the ring only — a densely CUT boundary with a hollow
    interior, which is exactly the shape that must still be reported."""
    h = side / 2.0
    pts = []
    n = max(1, int(side / step))
    for i in range(n):
        t = -h + i * step
        pts += [(t, -h), (t, h), (-h, t), (h, t)]
    return pts


def _grid_vertices(side, step):
    """Interior vertices too — the DENSELY-CUT apron the twin needs."""
    h = side / 2.0
    pts = []
    n = int(side / step) + 1
    for i in range(n):
        for j in range(n):
            pts.append((-h + i * step, -h + j * step))
    return pts


# ═════════════════════════════════════════════════════════════════════
# The measurement
# ═════════════════════════════════════════════════════════════════════

def test_an_apron_with_an_empty_100m_disk_is_reported():
    """A 300 m apron whose only emitted vertices are its four corners
    holds a 150 m empty interior disk — far over the 80 m radius."""
    shape = _Shape(_square(300.0))
    corners = list(shape.polygon.exterior.coords)[:-1]
    recs = find_nodeless_interiors([shape], corners, 80.0)
    assert len(recs) == 1
    assert recs[0]["shapeID"] == 0
    assert recs[0]["radius_m"] >= 100.0
    # the centre is the middle of the square
    cx, cy = recs[0]["centre_m"]
    assert abs(cx) < 5.0 and abs(cy) < 5.0


def test_a_densely_cut_apron_reports_nothing():
    """Interior vertices every 40 m: no disk of radius 80 m can avoid
    them, so the same apron reads clean."""
    shape = _Shape(_square(300.0))
    recs = find_nodeless_interiors([shape], _grid_vertices(300.0, 40.0),
                                   80.0)
    assert recs == []


def test_a_boundary_dense_but_hollow_apron_is_still_reported():
    """The discriminating case, and the HECA one: the RING is cut every
    10 m (the emit decimators cap chords at 60 m, so a real apron ring
    is dense) and the INTERIOR has nothing.  A boundary-only reading
    would call this apron well-sampled."""
    shape = _Shape(_square(300.0))
    recs = find_nodeless_interiors([shape], _ring_vertices(300.0, 10.0),
                                   80.0)
    assert len(recs) == 1
    assert recs[0]["radius_m"] >= 100.0


def test_a_shape_too_small_to_hold_the_disk_is_rejected_fast():
    """The fast reject: a 100 m apron's furthest interior point is 50 m
    from its own boundary, so no 80 m disk exists at all."""
    shape = _Shape(_square(100.0))
    assert find_nodeless_interiors([shape], [], 80.0) == []
    assert largest_nodeless_disk(_square(100.0), None, [], 80.0) is None


def test_only_apron_role_shapes_are_measured():
    """The spec scopes the instrument to apron-role polygons."""
    taxi = _Shape(_square(300.0), role="taxiway")
    assert find_nodeless_interiors([taxi], [], 80.0) == []
    apron = _Shape(_square(300.0), role="apron")
    assert len(find_nodeless_interiors([apron], [], 80.0)) == 1


def test_one_vertex_in_the_middle_kills_the_disk():
    """The measurement is ``min(distance to boundary, distance to the
    nearest emitted vertex)`` — one node in the void is enough to halve
    the empty radius."""
    shape = _Shape(_square(300.0))
    corners = list(shape.polygon.exterior.coords)[:-1]
    with_centre = corners + [(0.0, 0.0)]
    recs = find_nodeless_interiors([shape], with_centre, 120.0)
    assert recs == []                    # the 150 m disk is gone


# ═════════════════════════════════════════════════════════════════════
# The report: loud at zero, and published on the layout
# ═════════════════════════════════════════════════════════════════════

class _FakeLayout:
    """The minimum surface the reporter reads."""

    def __init__(self, shapes):
        self.shapes = shapes
        self.anchor = ANCHOR

    def m_to_ll(self, x, y):
        return (ANCHOR[0] + y / 111_320.0, ANCHOR[1] + x / 96_000.0)


def test_the_report_is_loud_at_zero(capsys):
    """A line that only appears on a finding cannot distinguish 'found
    nothing' from 'did not run'."""
    layout = _FakeLayout([_Shape(_square(100.0))])
    recs = report_nodeless_interiors(layout, [], icao="TEST")
    assert recs == []
    assert layout._nodeless_interiors == []
    blob = capsys.readouterr().out
    assert "[nodeless-interior]" in blob
    assert "0 apron shape(s)" in blob


def test_the_report_names_the_shape_the_centre_and_the_radius(capsys):
    layout = _FakeLayout([_Shape(_square(300.0), ref="apron_test")])
    recs = report_nodeless_interiors(layout, [], icao="TEST")
    assert len(recs) == 1
    assert "centre_ll" in recs[0]
    blob = capsys.readouterr().out
    assert "UNCONTROLLED" in blob
    assert "CENSUS-INVISIBLE" in blob
    assert "shapeID 0" in blob
    assert "apron_test" in blob


# ═════════════════════════════════════════════════════════════════════
# Sidecar registration + round trip
# ═════════════════════════════════════════════════════════════════════

def test_the_sidecar_keys_are_registered_as_evidence():
    """An emitted sidecar key classified nowhere fails
    ``test_harness.test_every_emitted_sidecar_key_is_classified``."""
    import check_grade as CG
    for key in ("nodeless_interiors", "gap_spine_bridges"):
        assert key in CG.SIDECAR_EVIDENCE_KEYS
        assert key not in CG.SIDECAR_LAW_KEYS


def test_the_evidence_reader_counts_them(tmp_path):
    import check_grade as CG
    osm = tmp_path / "p.osm"
    osm.write_text("<osm/>")
    (tmp_path / "p.osm.axes.json").write_text(json.dumps({
        "anchor": list(ANCHOR), "ruleset": "icao",
        "nodeless_interiors": [{"shapeID": 3, "radius_m": 107.4},
                               {"shapeID": 9, "radius_m": 88.0}],
        "gap_spine_bridges": [{"node_a": 462, "node_b": 470}]}))
    ev = CG.sidecar_evidence(str(osm))
    assert ev["nodeless_interior_count"] == 2
    assert ev["gap_spine_bridge_count"] == 1
    assert ev["unknown_keys"] == []


def test_an_empty_reading_is_not_an_absent_key(tmp_path):
    """``[]`` means the instrument ran and found none; a MISSING key
    means the patch predates the instrument.  The census must be able to
    tell them apart, so the writer is unconditional."""
    import check_grade as CG
    from auto_patch.layout import PavementLayout
    patch = tmp_path / "NONE_auto.patch.osm"
    PavementLayout(icao="NONE", anchor=ANCHOR).to_osm(str(patch))
    side = json.loads((tmp_path / "NONE_auto.patch.osm.axes.json")
                      .read_text())
    assert side["nodeless_interiors"] == []
    assert side["gap_spine_bridges"] == []
    ev = CG.sidecar_evidence(str(patch))
    assert ev["nodeless_interior_count"] == 0
    assert ev["unknown_keys"] == []


def test_the_records_reach_the_sidecar(tmp_path):
    from auto_patch.layout import PavementLayout
    layout = PavementLayout(icao="TEST", anchor=ANCHOR)
    layout.gap_spine_bridges = [{"node_a": 462, "node_b": 470,
                                 "dist_m": 254.1}]
    patch = tmp_path / "TEST_auto.patch.osm"
    layout.to_osm(str(patch))
    side = json.loads((tmp_path / "TEST_auto.patch.osm.axes.json")
                      .read_text())
    assert side["gap_spine_bridges"][0]["node_a"] == 462
    # the instrument ran over an empty layout and published its zero
    assert side["nodeless_interiors"] == []
