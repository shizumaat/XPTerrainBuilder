"""Lane v2corridor twins (RULINGS 2026-09-10u; spec ``docs/specs/
auto-patch-v2/othh-terminal-ramps-spec.md`` §12): a Law C wall band is
admitted on AUTHORED depth — its lowest vertex at least
``cutout.wall_corridor.min_wall_depth_m`` below the OBJECT'S OWN local
zero — never on rendered depth under a placement whose anchor plane sits
under the terrain.

* a wall authored at y −2 under a deck → a level corridor (admitted);
* the SAME shape authored at y +0.9 (nothing under its own zero) placed
  with its anchor plane 8 m UNDER the DEM → refused, and the refusal
  names the authored frame.  Under the rendered clause it read 7 m
  "below ground" and minted a corridor: the Aerosoft LEMD class.

The fixture objects and the synthetic airport come from the Law C twins
(``test_v2wallcorridor``); law values are read from the tables.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.wall_corridors import CLASS_LEVEL, read_wall_corridors
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import read_objects

from auto_patch_v2.model.airport import OsmWay

from test_v2wallcorridor import _corridor_obj, _vwall
from test_tunnel_objects import _airport, _slab, _write


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("packc") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    return {
        "dir": d,
        # authored 2 m under its own zero, a deck at +2.6 over it
        "deep": _corridor_obj(d / "deep.obj", depth=2.0),
        # RULINGS 2026-09-10w (c): the same corridor with NO deck over it
        "open_air": _corridor_obj(d / "open_air.obj", depth=2.0, deck_y=None),
        # the same two bands authored ENTIRELY ABOVE the object's zero
        # (bottom +0.9, top +12.0, deck +14.0): nothing dug in, and tall
        # enough that the ground-contact clause cannot be what refuses it
        "shallow": _shallow_with_a_deep_decoy(d / "shallow.obj"),
    }


def _shallow_with_a_deep_decoy(path):
    """The LEMD shape: two kerb bands authored ENTIRELY ABOVE the
    object's zero (bottom +0.9, top +12, a deck at +14 — tall enough that
    the ground-contact clause is not what refuses them), plus ONE
    isolated band 200 m away authored 2 m below the zero.  The decoy is
    why the placement pre-screen (``y_range``) passes: the resource does
    reach below its origin somewhere, just not at the "corridor" (the
    Aerosoft pack's foundations vs its cargo kerbs).  It pairs with
    nothing (200 m > ``max_width_m``)."""
    vt: list = []
    tris: list = []
    _vwall(vt, tris, -5.3, -5.0, -40.0, 40.0, 0.9, 0.9, 12.0)
    _vwall(vt, tris, 5.0, 5.3, -40.0, 40.0, 0.9, 0.9, 12.0)
    _slab(vt, tris, -7.0, 7.0, -30.0, 30.0, 14.0, 14.3)
    _vwall(vt, tris, 200.0, 200.3, -5.0, 5.0, -2.0, -2.0, 0.0)
    return _write(path, vt, tris)


#: RULINGS 2026-09-10w (b): a service way down the corridor's own axis
#: (the fixture bands span authored z −40..40 at heading 0) ENTERS both
#: mouths — the road the corridor exists for.
def _axis_road():
    return (OsmWay(-601, "airport_small_roads", ((0.0, -300.0), (0.0, 300.0)), False,
                   {"highway": "service"}),)


def _corridors(objs, law, name, agl=None, ways=None):
    """The wall corridors of one placement; ``agl`` (an ``OBJECT_AGL``
    offset) sinks the placement's anchor plane under the DEM; ``ways``
    (default: a road entering both mouths) states the mouth roads."""
    kind = "OBJECT" if agl is None else "OBJECT_AGL"
    airport = _airport(objs, law, [(name, (0.0, 0.0), 0.0, agl, kind)],
                       _axis_road() if ways is None else ways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    return read_wall_corridors(airport, objects, cache, law)


def test_a_band_authored_under_its_own_zero_is_admitted(objs, law):
    """A wall authored 2 m below the object's local zero under a deck is
    a Law C corridor — OTHH's accepted kerbs (y −1.888..+0.587 under a
    deck at +2.61) are this case."""
    wc = law.tables.structures.cutout.wall_corridor
    recs, st = _corridors(objs, law, "deep")
    assert 2.0 > wc.min_wall_depth_m          # the fixture is a real band
    assert st.bands == 2 and st.pairs == 1 and st.corridors == 1, st.refused
    assert st.by_class == {CLASS_LEVEL: 2} and len(recs) == 2
    for r in recs:
        assert r.cls == CLASS_LEVEL and r.width_m == pytest.approx(10.0, abs=0.05)


def test_a_band_authored_above_its_own_zero_is_refused_however_deep_it_renders(objs, law):
    """RULINGS 2026-09-10u: the placement's anchor plane 8 m under the
    DEM renders the bands 7 m "below ground" — the rendered clause
    admitted them (LEMD: 17 spurious corridors).  On authored depth
    there is nothing under the object's zero: no band, no corridor."""
    recs, st = _corridors(objs, law, "shallow", agl=-8.0)
    assert recs == [] and st.corridors == 0 and st.pairs == 0
    assert st.bands == 0, st.refused                # never even a band
    # and the same shape, its anchor plane ON the ground, is refused too:
    # admission does not depend on the terrain at all
    recs0, st0 = _corridors(objs, law, "shallow")
    assert recs0 == [] and st0.bands == 0


def test_the_anchor_plane_does_not_move_the_admission_but_burial_still_refuses(objs, law):
    """The other half of the ruling: DEPTH is read in the object's own
    frame, so sinking the placement neither mints nor deepens a band —
    the dug-in wall is admitted with its anchor 0.3 m under the DEM
    exactly as at grade.  What the terrain still decides is CONTACT: a
    placement sunk 8 m renders the whole band under the ground and the
    ground-contact clause (``basin.contact_band_m``) refuses it as
    buried — a terrain relation, kept as one."""
    recs, st = _corridors(objs, law, "deep", agl=-0.3)
    assert st.bands == 2 and st.corridors == 1, st.refused
    assert len(recs) == 2
    buried, stb = _corridors(objs, law, "deep", agl=-8.0)
    assert buried == [] and stb.bands == 0


# ── RULINGS 2026-09-10w: the three-part admission ────────────────────────

def test_a_road_entering_the_mouth_under_a_deck_admits_the_corridor(objs, law):
    """(a) + (b) + (c) together: walls authored 2 m under the object's
    zero, a service way running down the axis through both mouths, a
    deck over the trench — the OTHH case Law C was written for.  The
    admission line names each clause and its witness."""
    recs, st = _corridors(objs, law, "deep")
    assert st.corridors == 1 and st.roads == 1 and len(recs) == 2, st.refused
    assert st.refused_no_road == 0 and st.refused_no_deck == 0
    line = "\n".join(st.admission)
    assert "(a) admitted" in line and "osm way -601" in line and "ADMITTED" in line
    assert "(c) admitted — deck" in line


def test_no_road_within_the_law_window_refuses_the_corridor(objs, law):
    """(b): the SAME walls under the SAME deck with the only road pushed
    beyond ``corridor_mouth_road_m`` of either mouth — a below-grade
    foundation beside an apron, not a road underpass (LEMD's Aerosoft
    cargo kerbs).  The refusal names the clause and the witness search."""
    wc = law.tables.structures.cutout.wall_corridor
    far = wc.corridor_mouth_road_m + 10.0
    away = (OsmWay(-602, "airport_small_roads",
                   ((-300.0, 40.0 + far), (300.0, 40.0 + far)), False,
                   {"highway": "service"}),)
    recs, st = _corridors(objs, law, "deep", ways=away)
    assert recs == [] and st.corridors == 0 and st.refused_no_road == 1
    assert st.pairs == 1, st.refused                    # the pair still forms
    assert any("no road enters its mouth" in r for r in st.refused), st.refused
    line = "\n".join(st.admission)
    assert "(b) REFUSED" in line and "nearest:" in line and "(c) not read" in line
    # ...and a road that PASSES the mouth sideways does not enter it
    across = (OsmWay(-603, "airport_small_roads", ((-300.0, 45.0), (300.0, 45.0)), False,
                     {"highway": "service"}),)
    recs2, st2 = _corridors(objs, law, "deep", ways=across)
    assert recs2 == [] and st2.refused_no_road == 1
    assert any("off" in r for r in st2.admission)


def test_a_road_at_the_mouth_but_open_air_refuses_the_corridor(objs, law):
    """(c): the same walls, the same road entering, NO deck over the
    trench — 10 of LEMD's 17 read open air.  Open air is a REFUSAL, not
    a pass: (b) is admitted with its witness and (c) refuses by name."""
    recs, st = _corridors(objs, law, "open_air")
    assert recs == [] and st.corridors == 0
    assert st.roads == 1 and st.refused_no_deck == 1 and st.refused_no_road == 0
    assert any("open air over the trench" in r for r in st.refused), st.refused
    line = "\n".join(st.admission)
    assert "(b) admitted" in line and "(c) REFUSED — open air" in line
