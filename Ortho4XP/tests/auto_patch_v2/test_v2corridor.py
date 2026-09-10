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


def _corridors(objs, law, name, agl=None):
    """The wall corridors of one placement; ``agl`` (an ``OBJECT_AGL``
    offset) sinks the placement's anchor plane under the DEM."""
    kind = "OBJECT" if agl is None else "OBJECT_AGL"
    airport = _airport(objs, law, [(name, (0.0, 0.0), 0.0, agl, kind)])
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
