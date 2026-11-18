"""#2120 S (spec ``sim-review/2120-S.md``): A BRIDGE OVER A PORTAL'S CUT
(``airport/cut_bridge``) stands its deck flush with the cover at its
cover-side end; one plate for every plated member; the placement stage
reads it as one bridge frame (``open_frame_seat.LEAD_PLATES``).

Synthetic: a plane at 300 m with a cut 20 m deep and 80 m wide along y; a
portal in it north of the deck; a deck 120 m long spanning the cut."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.anchor_rule import datum_of
from auto_patch_v2.airport.cut_bridge import cut_bridges
from auto_patch_v2.airport.cut_portal import CutPortal
from auto_patch_v2.airport.cut_portal_seat import CUT_BRIDGE_PLATE
from auto_patch_v2.law import Law
from auto_patch_v2.model.frame import Frame
from shapely.geometry import box
from test_tunnel_objects import _slab, _write

_DECK_Y = (-16.0, -4.0)        # the deck's frame y band (placed at (0, -10))


class _Dem:
    """300 m (``east`` m east of the cut) with a cut 280 m for |x| < 40."""

    provenance = {"synthetic": "a cut along y"}

    def __init__(self, east: float = 300.0):
        self.east = east

    def z_many(self, xs, ys):
        xs = np.asarray(xs, dtype=float)
        return np.where(np.abs(xs) < 40.0, 280.0, np.where(xs > 0.0, self.east, 300.0))

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    d = tmp_path_factory.mktemp("cutbridge")
    vt: list = []
    tris: list = []
    _slab(vt, tris, -60.0, 60.0, -6.0, 6.0, 18.0, 20.0)       # the deck, top y 20
    deck = _write(d / "deck.obj", vt, tris)
    vt, tris = [], []
    _slab(vt, tris, -2.0, 2.0, -2.0, 2.0, 0.0, 18.0)          # a pier under it
    pier = _write(d / "pier.obj", vt, tris)
    vt, tris = [], []
    _slab(vt, tris, 200.0, 210.0, -2.0, 2.0, 0.0, 6.0)        # a shed off every deck
    shed = _write(d / "shed.obj", vt, tris)
    return {"deck": str(deck), "pier": str(pier), "shed": str(shed)}


def _plate():
    fp = box(-60.0, _DECK_Y[0], 60.0, _DECK_Y[1])
    ends = (((-60.0, _DECK_Y[0]), (-60.0, _DECK_Y[1])), ((60.0, _DECK_Y[0]), (60.0, _DECK_Y[1])))
    return types.SimpleNamespace(footprint=fp, ends=ends, area_m2=fp.area, surface=None)


def _obj(oid, path, kind, plated=False):
    return types.SimpleNamespace(id=oid, path=path, resolved=path, xy=(0.0, -10.0),
                                 agl_m=0.0, heading_deg=0.0, deck_kind=kind,
                                 deck_plate=_plate() if plated else None)


def _airport(dem=None, paved=()):
    portal = CutPortal("dsf:obj9", "objects/portal.obj", box(-60.0, 25.0, 60.0, 45.0),
                       20.0, 0.0, 20.5, (-1,), 280.0, 300.0)
    return types.SimpleNamespace(icao="ZZZZ", dem=dem or _Dem(), cut_portals=(portal,),
                                 frame=Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11),
                                 pavements=tuple(paved), runways=())


_CUT = [(box(-40.0, -60.0, 40.0, 24.0), ("dsf:obj9",))]


def _run(law, objs, ap=None, regions=_CUT, taken=frozenset()):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    return cut_bridges(ap or _airport(), objs, regions, cache, 0.5, 5.0, taken)


def test_a_rider_frame_over_a_portals_cut_seats_its_deck_end_on_the_cover(law, files):
    objs = [_obj("dsf:obj1", files["deck"], "candidate", plated=True),
            _obj("dsf:obj2", files["pier"], "family")]
    got = _run(law, objs)
    assert len(got) == 1
    w = got[0]
    assert w.plated == ("dsf:obj1",) and set(w.members) == {"dsf:obj1", "dsf:obj2"}
    assert w.portal == "dsf:obj9" and abs(w.top_y - 20.0) < 1e-6
    # the stations stand on the deck's end edge on the cover, never in the cut
    assert w.stations and all(55.0 - 0.6 <= abs(x) <= 60.6 for x, _y in w.stations)
    assert all(_DECK_Y[0] - 0.6 <= y <= _DECK_Y[1] + 0.6 for _x, y in w.stations)
    m = types.SimpleNamespace(plate_y=w.top_y, plate_kind=CUT_BRIDGE_PLATE,
                              plate_stations=((1.0, 2.0),))
    d = datum_of(m)
    assert d is not None and d.y == 20.0 and "bridge over a portal's cut" in d.label
    assert "portal in a cut" not in d.label
    # taken by another rule: never entered (T5)
    assert _run(law, objs, taken={"dsf:obj2"}) == ()


def test_no_portal_cut_no_witness(law, files):
    objs = [_obj("dsf:obj1", files["deck"], "candidate", plated=True)]
    assert _run(law, objs, regions=[]) == ()
    assert _run(law, objs, regions=[(box(500.0, 500.0, 600.0, 600.0), ("dsf:obj9",))]) == ()
    ap = _airport()
    ap.cut_portals = ()
    assert _run(law, objs, ap=ap) == ()
    # a flag deck is class A's / the flag readers'
    assert _run(law, [_obj("dsf:obj1", files["deck"], "flag", plated=True)]) == ()


def test_a_frame_with_a_part_off_every_deck_is_not_admitted(law, files):
    objs = [_obj("dsf:obj1", files["deck"], "candidate", plated=True),
            _obj("dsf:obj2", files["shed"], "family")]
    assert _run(law, objs) == ()


def test_a_deck_over_airport_pavement_is_not_admitted(law, files):
    pav = types.SimpleNamespace(outer=((-100.0, -30.0), (100.0, -30.0), (100.0, 10.0),
                                       (-100.0, 10.0)), holes=())
    objs = [_obj("dsf:obj1", files["deck"], "candidate", plated=True)]
    assert _run(law, objs, ap=_airport(paved=(pav,))) == ()


def test_a_deck_with_no_end_on_the_cover_is_not_admitted(law, files):
    class _Sunk(_Dem):
        def z_many(self, xs, ys):
            return np.full(len(np.asarray(xs)), 280.0)
    objs = [_obj("dsf:obj1", files["deck"], "candidate", plated=True)]
    assert _run(law, objs, ap=_airport(dem=_Sunk())) == ()


def test_two_cover_ends_seat_at_the_higher_ground_less_top(law, files):
    objs = [_obj("dsf:obj1", files["deck"], "signature", plated=True)]
    got = _run(law, objs, ap=_airport(dem=_Dem(east=302.0)))
    assert len(got) == 1 and all(x > 0.0 for x, _y in got[0].stations)   # the east end
    got = _run(law, objs, ap=_airport(dem=_Dem(east=298.0)))
    assert len(got) == 1 and all(x < 0.0 for x, _y in got[0].stations)   # the west end


def test_the_cut_bridge_plate_leads_its_unit_at_its_own_bodys_reading():
    """The §16g unit pass seats a cut bridge's deck parts on its plate's
    datum (``open_frame_seat.LEAD_PLATES``), at the station the plate's own
    body anchors at -- one zero for the frame (KATL's split 0.17 m on an
    even station count before)."""
    from auto_patch_v2.airport.open_frame_seat import LEAD_PLATES, walled_unit_zero
    assert CUT_BRIDGE_PLATE in LEAD_PLATES
    m = types.SimpleNamespace(plate_kind=CUT_BRIDGE_PLATE, plate_y=19.32,
                              plate_stations=((1.0, 0.0), (2.0, 0.0), (3.0, 0.0), (4.0, 0.0)))
    z = {1.0: 301.9, 2.0: 302.0, 3.0: 302.2, 4.0: 302.3}
    assert walled_unit_zero([m], lambda la, lo: z[la]) == pytest.approx(302.2 - 19.32)
