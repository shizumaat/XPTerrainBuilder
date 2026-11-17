"""#2116 (d) (owner 2026-11-17T00:13Z): a road JUNCTION is not tied to a lot.

``airport/road_ramp.reach_contacts`` gives a road END within
``[road_contact] contact_reach_m`` of a contact face a one-way ceiling at
that face's level (§37 (10) (1)).  An end the road CARRIES ON from — a
vertex of its end group has a road-graph neighbour on another route (the
#2090 B7 / RULINGS 2026-11-14e witness, ``_carries_on``) — is a junction:
across a gap wider than one lane it takes no contact on a LOT (the
groundside ``extra_roles``).  Airside and pad contacts are unchanged.
MEASURED KDEN: the -3642/-18149 junction was held at lot ``dsf:pol32``'s
corner 11 m away (1641.0 against its 1644.9 ground).
"""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport.road_ramp import reach_contacts
from auto_patch_v2.law import Law


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("KCLT")


def _pm(face_role: str):
    """A 20 m square face at x 0..20 and two road routes meeting 12 m west
    of it: route 0 runs west from (-12, 10), route 1 south from there."""
    xy = {1: (0.0, 0.0), 2: (20.0, 0.0), 3: (20.0, 20.0), 4: (0.0, 20.0),
          10: (-12.0, 10.0), 11: (-40.0, 10.0), 12: (-12.0, 9.0), 13: (-12.0, -30.0)}
    verts = {v: types.SimpleNamespace(xy=p, key=(p[1] * 1e-5, p[0] * 1e-5),
                                      incident_faces=(0,) if v < 10 else ())
             for v, p in xy.items()}
    face = types.SimpleNamespace(role=face_role, ring=[1, 2, 3, 4], holes=(), ref="f")
    pm = types.SimpleNamespace(faces={0: face}, vertices=verts,
                               ring_vertices=lambda cyc: list(cyc))
    frame = {10: (0, 0.0, 0.0), 11: (0, 28.0, 0.0), 12: (1, 0.0, 0.0), 13: (1, 39.0, 0.0)}
    owned = {v: "service_road" for v in frame}
    return pm, owned, frame


def _contacts(law, role, junction: bool):
    pm, owned, frame = _pm(role)
    adj = {v: [] for v in frame}
    if junction:
        adj[10].append((12, 1.0))
        adj[12].append((10, 1.0))
    js: list = []
    out, _named = reach_contacts(pm, law, owned, {}, frame, 15.0, 4.0, adj=adj,
                                 junctions_out=js)
    return out, js


def test_a_road_end_within_reach_of_a_lot_takes_its_contact(law):
    out, js = _contacts(law, "parking_lot", junction=False)
    assert 10 in out and not js


def test_a_junction_within_reach_of_a_lot_takes_no_contact(law):
    out, js = _contacts(law, "parking_lot", junction=True)
    assert 10 not in out and 12 not in out
    assert js and js[0]["gap_m"] == pytest.approx(12.0)


def test_a_junction_keeps_its_airside_contact(law):
    out, _js = _contacts(law, "apron", junction=True)
    assert 10 in out


def test_a_junction_that_touches_the_lot_keeps_its_contact(law):
    pm, owned, frame = _pm("parking_lot")
    adj = {v: [] for v in frame}
    adj[10].append((12, 1.0))
    adj[12].append((10, 1.0))
    out, _named = reach_contacts(pm, law, owned, {}, frame, 15.0, 20.0, adj=adj)
    assert 10 in out                       # a gap within one lane is a touch
