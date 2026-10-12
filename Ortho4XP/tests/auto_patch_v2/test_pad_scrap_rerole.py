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
    assert counts == {"pad_scraps_reroled": 1, "pad_scraps_reroled_m2": 30.0,
                      "pad_scraps_merged": 1}
    # issue #546: ONE plateau face encloses the scrap, so it is no face of
    # its own — the plateau's hole closes over it and every other face is
    # the face it was
    assert [r.ref for _g, r in out] == ["u", "u#2", "u#3", "pav#plateau:u", "pav"]
    plateau = out[3][0]
    assert len(plateau.interiors) == 1 and plateau.area == faces[4][0].area + 30.0
    assert [g.wkb for g, _r in out[:3]] == [faces[k][0].wkb for k in (0, 2, 3)]
    assert out[4][0].wkb == faces[5][0].wkb


def test_the_pad_a_scrap_other_ground_borders_and_a_wide_piece_stay():
    out = rerole_plateau_scraps(_faces(), Law.load())
    refs = [r.ref for _g, r in out]
    assert refs[0] == "u"                  # the largest face is the pad
    assert "u#2" in refs                   # the open apron borders it
    assert "u#3" in refs                   # not under the thin-piece floor


def test_another_pads_plateau_is_no_witness():
    faces = _faces()
    g, r = faces[4]
    faces[4] = _r("apron", "pav#plateau:other", g)
    out = rerole_plateau_scraps(faces, Law.load())
    assert out[1][1].ref == "u#1"


def test_a_scrap_pinched_between_its_plateau_and_a_structure_becomes_the_plateau():
    """The measured class: a triangle between the plateau and a basin
    wall's band.  The wall keeps its own law; a scrap ONLY structures
    border has no plateau to become."""
    law = Law.load()
    scrap = box(100, 10, 101, 40)
    wall = box(99, 10, 100, 40)
    plateau = box(100, 0, 110, 100).difference(scrap)
    faces = [_r("building", "u", box(0, 0, 99, 100)), _r("building", "u#1", scrap),
             _r("retaining_wall", "basin_wall:1", wall),
             _r("apron", "pav#plateau:u", plateau)]
    counts: dict = {}
    out = rerole_plateau_scraps(faces, law, counts)
    assert (out[1][1].role, out[1][1].ref) == ("apron", "pav#plateau:u")
    # ... and KEEPS its face: a structure shares its boundary, so no one
    # plateau face encloses it (issue #546 dissolves only the enclosed)
    assert [g.wkb for g, _r in out] == [g.wkb for g, _r in faces]
    assert counts["pad_scraps_merged"] == 0
    lone = [_r("building", "u", box(0, 0, 99, 100)), _r("building", "u#1", scrap),
            _r("retaining_wall", "basin_wall:1", box(99, 9, 102, 41).difference(scrap))]
    assert rerole_plateau_scraps(lone, law)[1][1].ref == "u#1"


def test_scraps_two_plateau_faces_share_keep_their_face():
    """Issue #546's bound: only a scrap ONE plateau face encloses closes a
    hole.  A scrap standing between two faces of the plateau has no single
    host — it is re-roled and stays the face it was."""
    scrap = box(104, 10, 105, 40)
    left = box(100, 0, 104.5, 100).difference(scrap)
    right = box(104.5, 0, 110, 100).difference(scrap)
    faces = [_r("building", "u", box(0, 0, 100, 100)), _r("building", "u#1", scrap),
             _r("apron", "pav#plateau:u", left), _r("apron", "pav#plateau:u", right)]
    counts: dict = {}
    out = rerole_plateau_scraps(faces, Law.load(), counts)
    assert [g.wkb for g, _r in out] == [g.wkb for g, _r in faces]
    assert out[1][1].ref == "pav#plateau:u" and counts["pad_scraps_merged"] == 0


def test_scraps_touching_at_a_point_in_one_plateau_all_dissolve():
    """The measured KCLT shape (35.2202043, -80.946664): three scraps
    meeting corner to corner inside one plateau face — three holes, three
    unions, one face left."""
    a, b, c = box(104, 10, 105, 20), box(105, 20, 106, 30), box(104, 30, 105, 40)
    plateau = Polygon(box(100, 0, 110, 100).exterior.coords,
                      [a.exterior.coords, b.exterior.coords, c.exterior.coords])
    faces = [_r("building", "u", box(0, 0, 100, 100)), _r("building", "u#1", a),
             _r("building", "u#2", b), _r("building", "u#3", c),
             _r("apron", "pav#plateau:u", plateau)]
    counts: dict = {}
    out = rerole_plateau_scraps(faces, Law.load(), counts)
    assert [r.ref for _g, r in out] == ["u", "pav#plateau:u"]
    assert not out[1][0].interiors and out[1][0].area == 1000.0
    assert counts["pad_scraps_merged"] == 3
