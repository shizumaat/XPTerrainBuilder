"""Twin of ``tools/drawn_cover.py`` (#2053 round 3): the 1 m cover raster,
OPEN / ROOFED and the edge band, the judge, the corner labels, SINK, RIM
and the riders -- synthetic geometry, no DSFTool, no installed scenery."""
from __future__ import annotations

import os
import sys
import types

import numpy as np
import pytest

_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, _TOOLS)

import drawn_cover as DCV  # noqa: E402
import drawn_site as DS  # noqa: E402

LAT, LON = -22.9, -43.16


def _box(e0, n0, e1, n1, z):
    q = np.array([[e0, n0, z], [e1, n0, z], [e1, n1, z], [e0, n1, z]], float)
    return [q[[0, 1, 2]], q[[0, 2, 3]]]


def _island():
    """A 40 x 40 m ground at 3 m with a 10 x 10 m roof 6 m over it."""
    return np.array(_box(0, 0, 40, 40, 3.0) + _box(15, 15, 25, 25, 9.0))


class _Mesh:
    def __init__(self, frame, f):
        self.frame, self.f = frame, f

    def z(self, lat, lon):
        e, n = self.frame.enter(np.asarray(lat, float), np.asarray(lon, float))
        return self.f(np.asarray(e), np.asarray(n))


def test_the_raster_is_one_metre_and_the_classes_read_roof_and_band():
    r = DCV.cover_raster(_island())
    assert r.step == DCV.CELL_M
    cls = DCV.classes(r)
    e, n = r.centres(cls["ij"])
    roofed = (e > 16) & (e < 24) & (n > 16) & (n < 24)
    assert not cls["open"][roofed].any() and cls["open"][~roofed & (e < 10)].all()
    assert np.all(cls["edge"][(e < 5) | (n < 5)] <= DCV.BAND_M)
    assert cls["edge"].max() > DCV.BAND_M


def test_the_judge_counts_open_samples_over_the_bar_off_and_on_the_patch():
    d = np.array([0.0, 0.06, 0.6, 0.06, 2.0])
    is_open = np.array([True, True, True, True, False])
    on = np.array([False, False, True, True, False])
    v = DCV.judge(d, is_open, on, 0.05)
    assert v == {"open_off_over": 1, "open_on_over": 2, "open_on_over_ground": 1,
                 "worst_m": 0.6}


def test_a_corner_is_named_node_water_edge_inner_or_outside():
    node = lambda en: bool(np.hypot(*en) < 0.1)                       # noqa: E731
    edge = lambda en: float(en[0])                                     # noqa: E731
    assert DCV.corner_label(np.array([0.0, 0.0]), 5.0, edge, node) == "patch node"
    assert DCV.corner_label(np.array([30.0, 1.0]), 0.0, edge, node) == "water"
    assert DCV.corner_label(np.array([1.0, 1.0]), 5.0, edge, node) == "plan edge"
    assert DCV.corner_label(np.array([-1.0, 1.0]), 5.0, edge, node) == "plan edge"
    assert DCV.corner_label(np.array([12.0, 1.0]), 5.0, edge, node) == "inner"
    assert DCV.corner_label(np.array([-12.0, 1.0]), 5.0, edge, node) == "outside"


def test_sink_is_the_open_share_drawn_half_a_metre_under():
    d = np.array([-0.6, -0.4, -2.0, 0.0])
    s = DCV.sink(d, np.array([True, True, True, False]), np.array([True, True, False, False]))
    assert s == {"open_pct": pytest.approx(66.67), "band_pct": 50.0, "inner_pct": 100.0}


def test_the_rim_reads_the_ground_outside_each_run():
    fr = DS.Frame(LAT, LON)
    r = DCV.cover_raster(_island())
    runs = DCV.rim(r, fr, _Mesh(fr, lambda e, n: np.where(e < 0, 1.0, 3.0)))
    assert runs
    west = [x for x in runs if x["median_m"] == pytest.approx(-2.0)]
    assert west and all(x["median_m"] in (pytest.approx(-2.0), pytest.approx(0.0))
                        for x in runs)


def test_the_riders_on_the_plan_are_read_against_top_and_floor():
    fr = DS.Frame(LAT, LON)
    r = DCV.cover_raster(_island())
    cls = DCV.classes(r)
    mesh = _Mesh(fr, lambda e, n: np.full(np.shape(e), 2.0))

    def row(k, e, n, path):
        lat, lon = fr.leave(e, n)
        return (k, types.SimpleNamespace(lat=float(lat), lon=float(lon), def_path=path,
                                         kind="OBJECT"), "/pack", "+00+000")
    rows = [row(1, 5.0, 5.0, "tree.obj"), row(2, 20.0, 20.0, "lamp.obj"),
            row(3, 80.0, 80.0, "far.obj"), row(4, 6.0, 6.0, "islandBase.obj")]
    got = DCV._riders(rows, None, r, cls, fr, mesh, "islandbase")
    by = {x["def"]: x for x in got}
    assert set(by) == {"tree.obj", "lamp.obj"}
    assert by["tree.obj"]["vs_top_m"] == pytest.approx(-1.0)
    assert by["lamp.obj"]["vs_top_m"] == pytest.approx(-7.0)
    assert by["lamp.obj"]["vs_floor_m"] == pytest.approx(-1.0)


def test_drawn_site_cover_hands_over(monkeypatch):
    seen = {}
    monkeypatch.setattr(DCV, "main", lambda argv: seen.setdefault("argv", argv) and 0)
    DS.main(["--cover", "SBRJ", "--tag", "T", "--object", "x"])
    assert seen["argv"] == ["SBRJ", "--tag", "T", "--object", "x"]
