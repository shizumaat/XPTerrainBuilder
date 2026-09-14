"""§41 (4) A SLIVER ZONE STRIP IS DISSOLVED (owner RULINGS 2026-09-14c item
4; attributed RULINGS 2026-09-14g item 4) — lane ``v2slivers``.

A zone face under ``emit.terrace.strip_min_m2`` or narrower than
``emit.terrace.strip_min_width_m`` at its widest place has nowhere to put
the transition it exists to carry: HECA shape 1035
(``adjacent_ground:taxi:E:zone1#38``, 15.7 m2, 2.16 m inscribed, hole 0 of
``cross_connector:pav115`` at 30.1110278, 31.4062316) stood at 105.86-106.01
inside a taxiway at 104.4 — the owner's hump.  It is dissolved into the face
it borders at the arrangement, so it is never emitted and the host's hole is
never cut.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.law import Law
from auto_patch_v2.planar.overlay import (Region, dissolve_sliver_zones,
                                          inscribed_width_m)

HOSTS = ("apron", "junction", "cross_connector")


@pytest.fixture
def law():
    return Law.for_airport("CYXY")


def _cell(role: str, ref: str, poly: Polygon):
    return (poly, Region(role, ref, poly, None, None, "airside", "cell"))


def _zone(ref: str, poly: Polygon):
    return (poly, Region("graded_strip", ref, poly, None, None, "groundside",
                         "zone", 1))


def _rect(x0, y0, x1, y1) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def test_inscribed_width_is_the_widest_place_not_two_area_over_perimeter():
    """RULINGS 2026-09-14g item 4: ``2 A / P`` is a MEAN-width proxy and
    over-counted 57 HECA zone faces to 153.  A pan-handle shape holds a
    6 m disc and the proxy calls it 2.6 m."""
    fat = _rect(0.0, 0.0, 6.0, 6.0)
    handle = _rect(6.0, 2.9, 30.0, 3.1)
    p = fat.union(handle)
    assert inscribed_width_m(p) == pytest.approx(6.0, abs=0.05)
    assert 2.0 * p.area / p.length < 3.0


def test_sliver_zone_is_unioned_into_the_pavement_it_borders(law):
    host = _cell("apron", "pav1", _rect(0.0, 0.0, 40.0, 40.0))
    sliver = _zone("adjacent_ground:taxi:E:zone1#38",
                   _rect(40.0, 0.0, 42.0, 5.0))          # 10 m2, 2 m wide
    faces, dissolved, dropped, area, rows = dissolve_sliver_zones(
        [host, sliver], law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m, HOSTS)
    assert (dissolved, dropped) == (1, 0)
    assert area == pytest.approx(10.0)
    assert [r[3] for r in rows] == ["apron:pav1"]
    assert len(faces) == 1
    poly, region = faces[0]
    assert region.role == "apron" and region.ref == "pav1"
    assert poly.area == pytest.approx(1610.0)             # the host GREW by it


def test_a_zone_face_over_both_thresholds_is_untouched(law):
    host = _cell("apron", "pav1", _rect(0.0, 0.0, 40.0, 40.0))
    band = _zone("adjacent_ground:taxi:E:zone2#1", _rect(40.0, 0.0, 50.0, 40.0))
    faces, dissolved, dropped, _a, _r = dissolve_sliver_zones(
        [host, band], law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m, HOSTS)
    assert (dissolved, dropped) == (0, 0)
    assert len(faces) == 2


def test_a_wide_enough_strip_that_is_merely_small_goes_on_area(law):
    """400 m2 is over the area floor and 4 m is over the width floor — but a
    3 m x 12 m strip (36 m2) is under the AREA floor alone and goes."""
    host = _cell("junction", "pav2", _rect(0.0, 0.0, 40.0, 40.0))
    narrow = _zone("z", _rect(40.0, 0.0, 43.0, 12.0))
    assert inscribed_width_m(narrow[0]) == pytest.approx(3.0, abs=0.02)
    faces, dissolved, _d, _a, _r = dissolve_sliver_zones(
        [host, narrow], law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m, HOSTS)
    assert dissolved == 1 and len(faces) == 1


def test_a_long_narrow_strip_over_the_area_floor_goes_on_width(law):
    """200 m2 — over ``strip_min_m2`` — but 2 m wide: it still carries no
    transition (HECA shape 332: 6.6 m2 over a 38 m contact, 0.35 m wide)."""
    host = _cell("apron", "pav1", _rect(0.0, 0.0, 200.0, 40.0))
    strip = _zone("z", _rect(0.0, 40.0, 100.0, 42.0))
    assert strip[0].area == 200.0 > law.tables.emit.terrace.strip_min_m2
    faces, dissolved, _d, _a, rows = dissolve_sliver_zones(
        [host, strip], law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m, HOSTS)
    assert dissolved == 1 and len(faces) == 1
    assert rows[0][2] == pytest.approx(2.0, abs=0.02)


def test_a_sliver_that_borders_nothing_is_dropped(law):
    """9 of HECA's 57 touch no face at all: there is no host to dissolve
    into, so the DEM owns them — as it owns every face no region claims."""
    lonely = _zone("adjacent_ground:taxi:E:zone2#37", _rect(0.0, 0.0, 2.0, 2.0))
    faces, dissolved, dropped, _a, rows = dissolve_sliver_zones(
        [lonely], law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m, HOSTS)
    assert (dissolved, dropped, faces) == (0, 1, [])
    assert rows[0][3] is None


def test_the_pavement_host_wins_over_a_longer_non_pavement_contact(law):
    """The host is the PAVEMENT it borders (``emit.terrace.shape_roles``),
    even when a road or another strip shares more of its boundary."""
    road = _cell("service_road", "route4", _rect(0.0, 10.0, 30.0, 20.0))
    pav = _cell("apron", "pav1", _rect(0.0, 0.0, 6.0, 10.0))
    sliver = _zone("z", _rect(0.0, 8.0, 30.0, 10.0))      # 60 m2, 2 m wide
    faces, dissolved, _d, _a, rows = dissolve_sliver_zones(
        [road, pav, sliver], law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m, HOSTS)
    assert dissolved == 1
    assert rows[0][3] == "apron:pav1"
    assert {r.ref for _p, r in faces} == {"route4", "pav1"}


def test_the_host_hole_is_never_cut(law):
    """THE SITE (HECA shape 1035, hole 0 of ``cross_connector:pav115``): the
    sliver sits in a HOLE of its host, and dissolving it fills the hole — so
    no ``gap_interior_ring`` is ever cut for it and no consumer downstream
    sees either the strip or the hole."""
    ring = _rect(0.0, 0.0, 40.0, 40.0)
    hole = _rect(18.0, 18.0, 20.0, 22.0)                  # 8 m2, 2 m wide
    host = _cell("cross_connector", "pav115",
                 Polygon(ring.exterior.coords, [hole.exterior.coords]))
    faces, dissolved, _d, _a, _r = dissolve_sliver_zones(
        [host, _zone("adjacent_ground:taxi:E:zone1#38", hole)],
        law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m, HOSTS)
    assert dissolved == 1 and len(faces) == 1
    poly, _region = faces[0]
    assert list(poly.interiors) == []
    assert poly.area == pytest.approx(1600.0)


def test_disarmed_by_zero_thresholds(law):
    host = _cell("apron", "pav1", _rect(0.0, 0.0, 40.0, 40.0))
    sliver = _zone("z", _rect(40.0, 0.0, 42.0, 5.0))
    faces, dissolved, dropped, _a, _r = dissolve_sliver_zones(
        [host, sliver], 0.0, 0.0, HOSTS)
    assert (dissolved, dropped, len(faces)) == (0, 0, 2)


def test_a_rigid_pad_is_never_a_host(law):
    """A building pad is ONE level for the body that stands on it: welding
    4.4 m2 of adjacent ground onto its footprint (CYXY shapes 130/131,
    ``adjacent_ground:taxi:D:zone1#12`` against ``building:building1``)
    would author a pad nobody authored.  With no other neighbour the
    sliver is dropped instead."""
    pad = _cell("building", "building1", _rect(0.0, 0.0, 20.0, 20.0))
    sliver = _zone("adjacent_ground:taxi:D:zone1#12",
                   _rect(20.0, 0.0, 22.0, 10.0))
    faces, dissolved, dropped, _a, rows = dissolve_sliver_zones(
        [pad, sliver], law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m, HOSTS,
        refuse_roles=("building",))
    assert (dissolved, dropped) == (0, 1)
    assert rows[0][3] is None
    assert [r.ref for _p, r in faces] == ["building1"]
