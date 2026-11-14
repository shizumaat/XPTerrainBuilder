"""#2075: a split body is drawn exactly when its placement is
(``airport/drawn_anchor``).

X-Plane drops an object whose ANCHOR lies inside a ``sim/exclude_obj`` box
of a pack drawn above it.  A split body anchored inside such a box, of a
placement anchored outside it, vanished (KRNT: 26 bodies of the DD pack
under the Renton pack's boxes).  The twin asserts the rule both ways, that
a moved body keeps its drawn geometry and height, and that the plan stage
reads the boxes of the packs above the AUTHORED pack only."""
from __future__ import annotations

import dataclasses as _dc
import os
import types

from auto_patch_v2.airport import anchor_rule as _ar
from auto_patch_v2.airport import drawn_anchor as D
from auto_patch_v2.airport import exclusion as X
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport.placement_file import authored_offset
from auto_patch_v2.airport.placement_record import Body, Split

BOX = ("upper", (-122.21, 47.49, -122.20, 47.50))
TILE = (-123.0, 47.0, -122.0, 48.0)


def _body(lat, lon, *, pts=(), z=10.0, y0=0.0, lift=0.0, msl=None, seat=None):
    a = _ar.Anchor("generic", lat, lon, y0, "own feet", surface_z=z)
    return Body(0, "generic", (0,), a, "o/x__b0.obj", geom_pts=tuple(pts),
                lift_m=lift, msl_z=msl, seat=seat)


def _split(lat, lon, *bodies, heading=30.0):
    return Split(7, "dsf:obj7", "o/x.obj", "/p/o/x.obj", lat, lon, heading,
                 tuple(bodies))


def test_a_drawn_placements_body_under_a_box_moves_along_itself():
    # placement anchored outside the box, its body anchored inside it; the
    # body's own geometry reaches out of the box at 47.495, -122.2105
    b = _body(47.495, -122.205, pts=((47.495, -122.2050, 1.0),
                                     (47.495, -122.2105, 0.0),
                                     (47.495, -122.2150, 0.0)), lift=0.5)
    r = _split(47.495, -122.215, b)
    counts: dict = {}
    got = D.drawn_as_placed(r, [BOX], lambda la, lo: 12.0, TILE, counts)
    nb = got.bodies[0]
    assert (nb.anchor.lat, nb.anchor.lon) == (47.495, -122.2105)  # nearest drawn point
    assert X.excluder_of([BOX], nb.anchor.lon, nb.anchor.lat) is None
    # the geometry stays: the offset is the placement frame's at the new anchor
    assert nb.anchor.offset == authored_offset(47.495, -122.2105, 0.0,
                                               47.495, -122.215, 30.0)
    # ...and so does the height: the ground under the OLD anchor + its lift
    assert nb.msl_z == 12.5 and nb.lift_m == 0.0 and nb.anchor.surface_z == 12.5
    assert nb.anchor.reason.startswith(D.REASON)
    assert counts == {"exclusion_reanchored": 1}


def test_a_body_with_no_drawn_point_is_kept_with_its_placement():
    b = _body(47.495, -122.205, pts=((47.495, -122.205, 0.0),), msl=99.0)
    r = _split(47.495, -122.215, b)
    nb = D.drawn_as_placed(r, [BOX], None, TILE).bodies[0]
    assert (nb.anchor.lat, nb.anchor.lon) == (47.495, -122.215)
    assert nb.msl_z == 99.0                   # a row seat is kept as it is


def test_an_excluded_placements_body_is_excluded_with_it():
    b = _body(47.495, -122.215)                # drawn spot, placement in the box
    r = _split(47.495, -122.205, b)
    counts: dict = {}
    nb = D.drawn_as_placed(r, [BOX], None, TILE, counts).bodies[0]
    assert (nb.anchor.lat, nb.anchor.lon) == (47.495, -122.205)
    assert X.excluder_of([BOX], nb.anchor.lon, nb.anchor.lat) == "upper"
    assert counts == {"exclusion_with_placement": 1}


def test_bodies_already_drawn_as_placed_and_no_boxes_change_nothing():
    r = _split(47.495, -122.215, _body(47.495, -122.214), _body(47.48, -122.3))
    assert D.drawn_as_placed(r, [BOX], None, TILE) is r
    inside = _split(47.495, -122.215, _body(47.495, -122.205))
    assert D.drawn_as_placed(inside, [], None, TILE) is inside


def test_an_unseated_body_is_left_and_counted():
    r = _split(47.495, -122.215, _body(47.495, -122.2051, z=None))
    counts: dict = {}
    assert D.drawn_as_placed(r, [BOX], lambda la, lo: None, TILE, counts) is r
    assert counts == {"exclusion_unmoved": 1}


def test_a_tilted_body_keeps_its_drawn_geometry():
    """``R·(v − offset)`` about the anchor: every written vertex keeps its
    height exactly and its plan place to the cosine of the tilt."""
    import numpy as np

    from auto_patch_v2.airport import obj8_split as S
    from auto_patch_v2.airport.anchor_rule import _m_per_deg
    grad = (0.02, -0.01)
    seat = types.SimpleNamespace(applied=True, grad=grad)
    plat, plon, hdg = 47.495, -122.215, 30.0
    old_ll = (47.495, -122.205)
    new_ll = (47.495, -122.2105)
    b = _body(*old_ll, pts=((new_ll[0], new_ll[1], 0.0),), seat=seat)
    b = _dc.replace(b, anchor=_dc.replace(
        b.anchor, offset=authored_offset(*old_ll, 0.0, plat, plon, hdg)))
    nb = D.drawn_as_placed(_split(plat, plon, b, heading=hdg), [BOX],
                           lambda la, lo: 10.0, TILE).bodies[0]
    R = S.tilt_matrix(grad)
    ml, mo = _m_per_deg(plat)
    h = np.radians(hdg)

    def world(anchor_ll, row, off, v):
        x, y, z = R @ (np.asarray(v) - np.asarray(off))
        e = x * np.cos(h) - z * np.sin(h)
        n = -(x * np.sin(h) + z * np.cos(h))
        return np.asarray([anchor_ll[1] * mo + e, row + y, anchor_ll[0] * ml + n])
    move = np.hypot((new_ll[1] - old_ll[1]) * mo, (new_ll[0] - old_ll[0]) * ml)
    for v in ((0.0, 0.0, 0.0), (40.0, 3.0, -25.0), (-120.0, 0.5, 60.0)):
        was = world(old_ll, 10.0, b.anchor.offset, v)
        now = world((nb.anchor.lat, nb.anchor.lon), nb.msl_z, nb.anchor.offset, v)
        assert abs(was[1] - now[1]) < 1e-6             # height: exact
        # plan: the cosine of the tilt over the move (here 0.10 m in 413 m)
        assert np.hypot(*(was - now)[[0, 2]]) < 4e-4 * move


def test_a_body_off_the_tile_is_left_to_the_tile_guard():
    r = _split(47.495, -122.215, _body(47.495, -122.205))
    assert D.drawn_as_placed(r, [BOX], None, (-124.0, 47.0, -123.0, 48.0)) is r


def _scenery(tmp_path):
    import O4_DSF_Binary as DSFB
    import O4_World_Pack as WP
    scenery = os.path.join(str(tmp_path), "X-Plane", "Custom Scenery")
    for name, props in (("a upper", [("sim/exclude_obj",
                                      "-122.21/47.49/-122.20/47.50")]),
                        ("b lower", [])):
        path = os.path.join(scenery, name, WP.dsf_relpath(47, -123))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = DSFB.placeholder_bytes(47, -123, "WorldEditor")
        if props:
            data = DSFB.rewrite(data, props=lambda pairs, p=props: pairs + list(p))
        with open(path, "wb") as fh:
            fh.write(data)
    with open(os.path.join(scenery, "scenery_packs.ini"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("I\n1000 Version\nSCENERY\n\nSCENERY_PACK Custom Scenery/a upper/\n"
                 "SCENERY_PACK Custom Scenery/b lower/\n")
    return scenery


def test_the_plan_reads_the_boxes_above_the_authored_pack(tmp_path):
    scenery = _scenery(tmp_path)
    plan = types.SimpleNamespace(pack_root=os.path.join(scenery, "b lower"))
    assert PW._exclusions(plan, (47, -123), "") == [
        ("a upper", (-122.21, 47.49, -122.20, 47.50))]
    assert PW._exclusions(plan, None, "") == []        # no tile named


def test_a_pack_x_plane_does_not_load_has_nothing_above_it(tmp_path):
    scenery = _scenery(tmp_path)
    with open(os.path.join(scenery, "scenery_packs.ini"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("I\n1000 Version\nSCENERY\n\nSCENERY_PACK Custom Scenery/a upper/\n"
                 "SCENERY_PACK_DISABLED Custom Scenery/b lower/\n")
    assert X.boxes_above(os.path.join(scenery, "b lower"), 47, -123) == []
