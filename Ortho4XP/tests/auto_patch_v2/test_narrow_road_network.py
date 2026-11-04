"""Owner sim read 2026-11-04 (HECA ``dsf:objpav1``, 30.1072,31.4204):
"This shape is a service road (which should be obvious from width alone)
why is it being classified and graded as an apron?"

The face was 20.9 km of 5.6 m pavement over 7.0 x 4.7 km, and ONE taxi
centreline crossed it.  The corridor ladder read its mean width off that
10 m crossing (11,855 m: not a corridor), §43 found no wide lobe to cut,
and the crossing was its apron evidence — so all of it came out apron.
``open_default.narrow_road``: pavement that is road-wide THROUGHOUT (no
point of ``corridor.max_width_m`` local width, mean width at most
``service.free_max_width_m``) and holds no stand is a service road; the
crossing taxi route still mints its junction.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.classify import classify, load_rules  # noqa: E402
from auto_patch_v2.classify.open_default import narrow_road  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import Pavement, Startup, Surface, TaxiEdge, TaxiNode  # noqa: E402
from test_classify import _rect, _synthetic  # noqa: E402

#: an L of 6 m road: 550 m north-south, then 300 m west, west of the field
_NET = Polygon([(-103.0, 150.0), (-97.0, 150.0), (-97.0, 700.0), (-403.0, 700.0),
                (-403.0, 694.0), (-103.0, 694.0)])


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _airport(stand: bool = False):
    """The M1 synthetic airport plus the road network, which taxiway Q
    (off the parallel's west end) crosses at its south end."""
    a = _synthetic(gate=True)
    net = Pavement("net", Surface.ASPHALT, tuple(_NET.exterior.coords)[:-1], ())
    nodes = dict(a.taxi_nodes)
    nodes[30] = TaxiNode(30, (-100.0, 112.5), "both")
    nodes[31] = TaxiNode(31, (-100.0, 200.0), "both")
    edges = a.taxi_edges + (TaxiEdge(20, 30, "Q", False, False, "C"),
                            TaxiEdge(30, 31, "Q", False, False, "C"))
    starts = a.startups + ((Startup("Stand 9", (-100.0, 400.0), 0.0, "tie_down"),)
                           if stand else ())
    return _dc.replace(a, pavements=a.pavements + (net,), taxi_nodes=nodes,
                       taxi_edges=edges, startups=starts)


def _net_roles(cl):
    out: dict[str, float] = {}
    for c in cl.cells:
        if c.ref == "net":
            out[c.role] = out.get(c.role, 0.0) + Polygon(c.ring, c.holes).area
    return out


def test_a_road_wide_network_crossed_by_a_taxiway_is_a_service_road(law):
    roles = _net_roles(classify(_airport(), law))
    assert roles, "the network made no cell"
    assert "apron" not in roles, roles
    # the crossing is the taxi route's junction; the rest is the road
    assert set(roles) <= {"service_road", "junction"}, roles
    assert roles.get("service_road", 0.0) > 0.8 * _NET.area, roles


def test_a_stand_keeps_the_narrow_pavement_apron(law):
    """A 1300 startup is where an aircraft parks: the width rung yields."""
    roles = _net_roles(classify(_airport(stand=True), law))
    assert "service_road" not in roles, roles


def test_the_width_reading_itself():
    rules = load_rules()
    w = narrow_road(_NET, rules)
    assert w is not None and 5.0 < w < 7.0
    # a 60 m-wide stand row is not road-wide: it has a wide lobe
    assert narrow_road(Polygon(_rect(0.0, 0.0, 300.0, 60.0)), rules) is None
    # a 30 m x 400 m strip has no 50 m lobe but is wider than a road
    assert narrow_road(Polygon(_rect(0.0, 0.0, 400.0, 30.0)), rules) is None
