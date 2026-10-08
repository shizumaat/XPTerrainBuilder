"""Spec §56 (10) R-F: a surplus PAD scrap its own stand-zone plateau
surrounds is re-roled as that plateau (``planar/pad_sliver.
rerole_plateau_scraps``) — one building face fewer, no vertex moved.
Hermetic."""
from __future__ import annotations

from shapely.geometry import Polygon, box

from auto_patch_v2.law import Law
from auto_patch_v2.planar.overlay import Region
from auto_patch_v2.planar.pad_sliver import rerole_plateau_scraps


def _r(role, ref, poly, side="airside"):
    return (poly, Region(role, ref, poly, None, None, side, "cell"))


def _faces():
    thin = box(104, 10, 105, 40)            # 1 x 30 m inside the plateau
    edge = box(110, 10, 111, 40)            # thin, but the open apron borders it
    wide = box(102, 60, 108, 90)            # enclosed, 6 m wide: not thin
    plateau = Polygon(box(100, 0, 110, 100).exterior.coords,
                      [thin.exterior.coords, wide.exterior.coords])
    apron = box(110, 0, 200, 100).difference(edge)
    return [_r("building", "u", box(0, 0, 100, 100)),
            _r("building", "u#1", thin), _r("building", "u#2", edge),
            _r("building", "u#3", wide),
            _r("apron", "pav#plateau:u", plateau), _r("apron", "pav", apron)]


def test_a_thin_scrap_its_own_plateau_surrounds_becomes_the_plateau():
    faces = _faces()
    counts: dict = {}
    out = rerole_plateau_scraps(faces, Law.load(), counts)
    assert [g.wkb for g, _r in out] == [g.wkb for g, _r in faces]   # no geometry moved
    by = {k: (r.role, r.ref) for k, (_g, r) in enumerate(out)}
    assert by[1] == ("apron", "pav#plateau:u")
    assert counts == {"pad_scraps_reroled": 1, "pad_scraps_reroled_m2": 30.0}


def test_the_pad_a_scrap_other_ground_borders_and_a_wide_piece_stay():
    out = rerole_plateau_scraps(_faces(), Law.load())
    refs = [r.ref for _g, r in out]
    assert refs[0] == "u"                  # the largest face is the pad
    assert refs[2] == "u#2"                # the open apron borders it
    assert refs[3] == "u#3"                # not under the thin-piece floor


def test_another_pads_plateau_is_no_witness():
    faces = _faces()
    g, r = faces[4]
    faces[4] = _r("apron", "pav#plateau:other", g)
    out = rerole_plateau_scraps(faces, Law.load())
    assert out[1][1].ref == "u#1"
