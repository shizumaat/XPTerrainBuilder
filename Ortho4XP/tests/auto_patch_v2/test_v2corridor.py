"""Lane v2corridor twins (RULINGS 2026-09-10u; spec ``docs/specs/
auto-patch-v2/othh-terminal-ramps-spec.md`` §12): a Law C wall band is
admitted on AUTHORED depth — its lowest vertex at least
``cutout.wall_corridor.min_wall_depth_m`` below the OBJECT'S OWN local
zero — never on rendered depth under a placement whose anchor plane sits
under the terrain.

(RULINGS 2026-09-10ad, round 5: the depth is read in the object's SEATED
frame — the rebake puts the object's zero on the LOCAL GROUND, so a
component renders at ``dem(its own centroid) + agl + authored y``, and the
FLOOR and the ramp beyond a mouth carry the AUTHORED depth.  The 10z
groundside-mouth clause (b'') is refuted and DELETED, key and all: the
mouth's surroundings admit and refuse nothing.)

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

import dataclasses as _dc
import math

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.wall_corridors import CLASS_LEVEL, read_wall_corridors
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.wall_corridor_ramps import wall_corridor_groups

from auto_patch_v2.model.airport import OsmWay

from test_v2wallcorridor import _corridor_obj, _vwall
from test_tunnel_objects import _rect
from auto_patch_v2.classify.roles import Cell, Classification
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
        # RULINGS 2026-09-10ad: a door authored 2.6 m under the object's
        # zero — the owner's LEMD witness depth — and the SAME door
        # authored 300 m from the object's origin (the shared-datum pack:
        # Aerosoft anchors LEMD's components up to 4 km from one point)
        "door26": _corridor_obj(d / "door26.obj", depth=2.6),
        "door26_far": _far_corridor_obj(d / "door26_far.obj"),
        # RULINGS 2026-09-10ab: the round-4 probe fixtures — the SAME
        # corridor 6 m under its serving road, and one carrying a FLOOR
        # SLAB between its walls at the wall bottom
        "deep6": _corridor_obj(d / "deep6.obj", depth=6.0),
        "slabbed": _floor_slab_obj(d / "slabbed.obj"),
        # RULINGS 2026-09-10af: a SKIRTED SHED — four walls carried 2 m
        # under the object's zero (the author's slope affordance) with a
        # roof over them: the LEMD cargo-dock shape the owner described
        # as "just foundations"
        "skirt": _skirt_shed(d / "skirt.obj"),
    }


def _skirt_shed(path, width=12.0, depth=2.0, top=8.0, thick=0.3, half_len=40.0):
    """A shed whose WHOLE bottom stands ``depth`` under its own zero —
    two long walls ``width`` apart, two end walls, a roof (RULINGS
    2026-09-10af: foundations, not a corridor)."""
    vt: list = []
    tris: list = []
    hw = width / 2.0
    _vwall(vt, tris, -hw - thick, -hw, -half_len, half_len, -depth, -depth, top)
    _vwall(vt, tris, hw, hw + thick, -half_len, half_len, -depth, -depth, top)
    _vwall(vt, tris, -hw - thick, hw + thick, -half_len - thick, -half_len, -depth, -depth, top)
    _vwall(vt, tris, -hw - thick, hw + thick, half_len, half_len + thick, -depth, -depth, top)
    # the roof stands clear of the wall tops: welded to them it would be
    # ONE component carrying a wide horizontal face, which rule 1 skips
    _slab(vt, tris, -hw - thick, hw + thick, -half_len - thick, half_len + thick,
          top + 0.5, top + 0.8)
    return _write(path, vt, tris)


def _floor_slab_obj(path, width=10.0, depth=2.0, thick=0.3, half_len=40.0):
    """The Law C corridor with a horizontal FLOOR PLATE spanning the
    inner faces at the wall bottom over its whole length — the shape
    RULINGS 2026-09-10ab (ii) looks for (a sheet: its vertices are its
    own, so it is a component of its own, and it carries no vertical
    face that could read as a third band between the kerbs)."""
    vt: list = []
    tris: list = []
    hw = width / 2.0
    _vwall(vt, tris, -hw - thick, -hw, -half_len, half_len, -depth, -depth, 0.5)
    _vwall(vt, tris, hw, hw + thick, -half_len, half_len, -depth, -depth, 0.5)
    b = len(vt)
    x, z = hw - 0.05, half_len - 0.5          # inside the inner faces: its
    vt += [(-x, -depth, -z), (x, -depth, -z),  # vertices are its own, so the
           (x, -depth, z), (-x, -depth, z)]    # plate is its own component
    tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    return _write(path, vt, tris)


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


#: The fixture corridor runs along ±y with its mouths at y = ±40; a kerb
#: road passes 8 m BEYOND each mouth at 90° to the axis.  It admits
#: nothing since RULINGS 2026-09-10ad deleted (b''); the round-4 PROBE
#: still reads it (its level against the floor).
def _kerb_roads(offset: float = 8.0):
    y = 40.0 + offset
    return (OsmWay(-601, "airport_small_roads", ((-300.0, y), (300.0, y)), False,
                   {"highway": "service"}),
            OsmWay(-602, "airport_small_roads", ((-300.0, -y), (300.0, -y)), False,
                   {"highway": "service"}))


def _apron_at_both_mouths(gap: float = 3.0):
    """An AIRSIDE apron face ``gap`` m beyond each mouth — nearer than the
    kerb road, so the mouth opens onto apron (the owner's "it's just apron
    up to the building": LEMD's Aerosoft foundations)."""
    y = 40.0 + gap
    return Classification((
        Cell(10, "apron", "apronN", _rect(-100.0, y, 100.0, 400.0), (), None, None,
             "airside", "pavement", {}),
        Cell(11, "apron", "apronS", _rect(-100.0, -400.0, 100.0, -y), (), None, None,
             "airside", "pavement", {}),
    ), (), {}, ())


def _far_corridor_obj(path, off=300.0, width=10.0, depth=2.6, top=0.5, thick=0.3,
                      deck_y=2.6, half_len=40.0):
    """The SHARED-DATUM shape (RULINGS 2026-09-10ad): the same two kerb
    bands and deck as ``_corridor_obj``, authored ``off`` m along +x from
    the object's ORIGIN — the anchor the pack places it by is that far
    away, on ground 8 m lower."""
    vt: list = []
    tris: list = []
    hw = width / 2.0
    _vwall(vt, tris, off - hw - thick, off - hw, -half_len, half_len, -depth, -depth, top)
    _vwall(vt, tris, off + hw, off + hw + thick, -half_len, half_len, -depth, -depth, top)
    _slab(vt, tris, off - hw - 2.0, off + hw + 2.0, -half_len + 10.0, half_len - 10.0,
          deck_y, deck_y + 0.3)
    return _write(path, vt, tris)


class _SharedDatumDem:
    """The Aerosoft LEMD class (RULINGS 2026-09-10ad): the pack's ANCHOR
    POINT stands on ground 8 m LOWER than the components it places 300 m
    away — one datum plane for geometry the reader meets kilometres from
    it.  The placement's ``anchor_z`` is 692; every wall, station and
    mouth of its corridor stands on ground at 700."""

    provenance = {"synthetic": "a shared anchor datum 8 m under the components"}

    def z(self, x: float, y: float) -> float:
        return 692.0 if x < 150.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _corridors(objs, law, name, agl=None, ways=None, classification=None, dem=None):
    """The wall corridors of one placement; ``agl`` (an ``OBJECT_AGL``
    offset) sinks the placement's anchor plane under the DEM; ``ways``
    (default: a kerb road 8 m past each mouth) states the mouth roads;
    ``classification`` states the pavement faces the mouths open onto."""
    kind = "OBJECT" if agl is None else "OBJECT_AGL"
    airport = _airport(objs, law, [(name, (0.0, 0.0), 0.0, agl, kind)],
                       _kerb_roads() if ways is None else ways)
    if dem is not None:
        airport = _dc.replace(airport, dem=dem)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    return read_wall_corridors(airport, objects, cache, law, classification, measure=True)


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


# ── RULINGS 2026-09-10ab: the round-4 discriminators, MEASURED ───────────
# The instrument the round-4 table was read on (spec §12c): NEITHER
# separates LEMD from OTHH, so neither is law — these twins hold the
# READING honest for whoever measures next.

def test_the_floor_road_probe_states_the_level_minus_the_floor(objs, law):
    """(i): the fixture's kerb road runs on the plane DEM at the corridor
    (700.0 m); the walls are authored 2 m under the object's zero, whose
    anchor is that same plane — so the probe reads the road 2 m above the
    floor, names the levelled profile that answered and the road, and
    fails a 1.5 m tolerance.  The same corridor 6 m down reads +6."""
    _r, st = _corridors(objs, law, "deep")
    row = st.floor_probe[0]
    assert row["delta_m"] == pytest.approx(2.0, abs=0.05), row
    assert row["road_level_z"] == pytest.approx(700.0, abs=0.05)
    assert row["road_source"].startswith("levelled") and "-601" in row["road_witness"]
    assert row["within_tol"] is False
    _r6, st6 = _corridors(objs, law, "deep6")
    row6 = st6.floor_probe[0]
    assert row6["delta_m"] == pytest.approx(6.0, abs=0.05), row6
    assert row6["within_tol"] is False


def test_the_floor_slab_probe_finds_a_slab_only_where_one_is_authored(objs, law):
    """(ii): a corridor whose walls carry a horizontal plate between them
    at the wall bottom reads a slab over its whole length; the same
    corridor with only a DECK over it (the OTHH and LEMD shape — both
    packs read 0.00 in the round-4 table) reads none."""
    _r, st = _corridors(objs, law, "slabbed")
    assert st.floor_probe, (st.refused, st.pairs, st.bands)
    row = st.floor_probe[0]
    assert row["slab"] is True and row["slab_cover"] >= 0.9, row
    assert "slabbed.obj" in row["slab_witness"]
    _r2, st2 = _corridors(objs, law, "deep")
    assert st2.floor_probe[0]["slab"] is False
    assert st2.floor_probe[0]["slab_cover"] == 0.0


# ── RULINGS 2026-09-10af: the NARROW-CUT reading, MEASURED ───────────────
# Round 6's instrument (spec §12e).  It states the wall pair's SPACING,
# the placement's BELOW-ZERO PERIMETER FRACTION and the cut's width
# across the axis against the footprint's.  It separates NOTHING: a
# free-standing kerb corridor (OTHH's own shape) reads the SAME fraction
# 1.0 as a foundation skirt, because a kerb wall's footprint IS the wall.
# These twins hold that refutation honest.

def test_the_narrow_cut_probe_states_the_spacing_and_the_fraction(objs, law):
    """The fixture kerb corridor: inner faces 10 m apart (road scale) and
    a below-zero perimeter fraction of 1.0 — the walls ARE the object, so
    every metre of their footprint's perimeter is authored below zero."""
    _r, st = _corridors(objs, law, "deep")
    assert st.narrow_cut, (st.refused, st.pairs, st.bands)
    row = st.narrow_cut[0]
    assert row["spacing_m"] == pytest.approx(10.0, abs=0.05), row
    assert row["width_m"] == pytest.approx(10.0, abs=0.1), row
    assert row["fraction"] >= 0.9, row
    assert row["admitted"] is True


def test_a_foundation_skirt_reads_the_same_fraction_as_a_kerb_corridor(objs, law):
    """RULINGS 2026-09-10af asked whether a foundation skirt is separable
    by the perimeter fraction.  It is NOT: a shed whose whole bottom is
    2 m under its zero reads ≈ 1.0 — and so does the free-standing kerb
    corridor above, because a kerb wall's footprint IS the wall (spec
    §12e; OTHH's `TerminalRoads_Parking_004` 1.00, `Bridge_02` 1.00,
    `Terminal_Base_2_5` 0.99 against LEMD's cargo docks at 1.00).  No
    threshold on the fraction keeps OTHH's 43 and refuses LEMD's docks;
    the clause is not law, and this twin fails the day one is written on
    the fraction alone.

    The IDEAL skirt is already refused for another reason — its ring
    closes both ends (a sunken yard, 08n).  LEMD's cargo docks survive
    because their skirt walls are single SHEETS whose pairs run past the
    shed's ends: ends cover 0 %/1 % there (spec §12e)."""
    recs, st = _corridors(objs, law, "skirt")
    assert st.narrow_cut, (st.refused, st.pairs, st.bands)
    row = st.narrow_cut[0]
    assert row["fraction"] >= 0.9, row
    assert row["spacing_m"] == pytest.approx(12.0, abs=0.05), row
    _r2, st2 = _corridors(objs, law, "deep")
    assert abs(row["fraction"] - st2.narrow_cut[0]["fraction"]) < 0.2, (
        row, st2.narrow_cut[0])
    assert not recs and st.corridors == 0
    assert any("no mouth" in r for r in st.refused), st.refused


# ── RULINGS 2026-09-10ad: the SEATED frame ───────────────────────────────

def test_a_shared_datum_anchor_no_longer_deepens_the_corridor(objs, law):
    """The owner's LEMD question: a door authored 2.6 m below the object's
    zero, placed by a SHARED-DATUM pack whose anchor point reads 8 m under
    the local ground.  Read against that anchor plane the wall stood
    10.6 m "below ground" and its ramp needed 212 m at 5 %; in the SEATED
    frame (the rebake puts the zero on the local ground) the floor stands
    at the authored −2.6 m, the depth IS 2.6 m and the ramp is 52 m."""
    wc = law.tables.structures.cutout.wall_corridor
    recs, st = _corridors(objs, law, "door26_far", dem=_SharedDatumDem())
    assert st.corridors == 1 and len(recs) == 2, st.refused
    for r in recs:
        # the placement's own anchor plane is 8 m under the ground at the
        # corridor — the reading no longer uses it
        assert r.anchor_dem_z == pytest.approx(692.0, abs=0.01)
        assert r.mouth_dem_z == pytest.approx(700.0, abs=0.05)
        assert r.floor_z == pytest.approx(700.0 - 2.6, abs=0.05)
        assert r.depth_m == pytest.approx(2.6, abs=0.05)
        # the ramp the planner will build beyond the mouth: rise / grade,
        # plus the mouth allowance the floor overlap adds
        rise = r.mouth_dem_z - r.floor_z
        allow = law.tables.structures.cutout.floor_overlap_m
        assert rise / wc.ramp_grade <= 2.6 / wc.ramp_grade + allow + 1e-6
        assert rise / wc.ramp_grade < 60.0            # was 212 m (10ad)
    groups = wall_corridor_groups(recs, law)
    assert len(groups) == 2 and all(g.max_grade == wc.ramp_grade for g in groups)


def test_an_anchor_at_grade_reads_exactly_as_the_rendered_frame_did(objs, law):
    """OTHH's case: the anchor plane IS the local ground (its DEM is a
    constant 3.96 m), so the seated frame and the old rendered frame are
    the same plane and every number is unchanged — the 43 corridors must
    come out identical."""
    recs, st = _corridors(objs, law, "door26")
    assert st.corridors == 1 and len(recs) == 2, st.refused
    for r in recs:
        assert r.anchor_dem_z == pytest.approx(r.mouth_dem_z, abs=0.05)
        assert r.floor_z == pytest.approx(r.anchor_dem_z - 2.6, abs=0.05)
        assert r.depth_m == pytest.approx(2.6, abs=0.05)
        assert r.cls == CLASS_LEVEL and r.width_m == pytest.approx(10.0, abs=0.05)
        assert r.length_m == pytest.approx(40.0, abs=0.05)
        # the deck at +2.6 over a floor at -2.6
        assert r.headroom_m == pytest.approx(5.5, abs=0.05)


def test_the_mouths_surroundings_admit_and_refuse_nothing(objs, law):
    """(b'') is DELETED (10ad): the same corridor with every road pushed
    far beyond the old 15 m window AND an airside apron face at both
    mouths — the two shapes round 3 refused — is admitted."""
    recs, st = _corridors(objs, law, "door26", ways=_kerb_roads(offset=200.0),
                          classification=_apron_at_both_mouths())
    assert st.corridors == 1 and len(recs) == 2, st.refused
    assert not any("mouth" in r for r in st.refused), st.refused


# ── RULINGS 2026-09-10ao round 7: the WALL'S HEIGHT ABOVE ZERO ───────────

def _wc_law(law, **kw):
    """The law with ``[cutout.wall_corridor]`` keys overridden."""
    co = law.tables.structures.cutout
    return _dc.replace(law, tables=_dc.replace(
        law.tables, structures=_dc.replace(
            law.tables.structures, cutout=_dc.replace(
                co, wall_corridor=_dc.replace(co.wall_corridor, **kw)))))


def _cargo_shed_wall(path, width=10.0, depth=2.0, top=8.0, thick=0.3, half_len=40.0):
    """LEMD's cargo dock (spec §12f): two foundation SHEETS 2 m under the
    object's zero that are the bottom of BUILDING walls rising to a roof
    at +8 — the shape 10ao expected the height clause to separate from a
    kerb corridor.  The pair's ends stay OPEN (the sheets run past the
    shed, §12e), so Law C admits it today."""
    vt: list = []
    tris: list = []
    hw = width / 2.0
    _vwall(vt, tris, -hw - thick, -hw, -half_len, half_len, -depth, -depth, top)
    _vwall(vt, tris, hw, hw + thick, -half_len, half_len, -depth, -depth, top)
    return _write(path, vt, tris)


def test_the_wall_height_above_zero_is_read_in_the_objects_own_frame(objs, law, tmp_path):
    """The instrument (``below_zero.read_wall_height``): a kerb wall
    authored from −2.0 to +0.5 reads own_m +0.5; a cargo shed's
    foundation sheet rising to a roof at +8 reads +8.  The reading is the
    object's OWN frame — the placement's anchor plane never enters it."""
    shed = _cargo_shed_wall(tmp_path / "shed.obj")
    objs2 = dict(objs, shed=shed)
    _r, st = _corridors(objs, law, "deep")
    assert st.narrow_cut and st.narrow_cut[0]["wall_own_m"] == pytest.approx(0.5, abs=0.05)
    _r2, st2 = _corridors(objs2, law, "shed")
    assert st2.narrow_cut and st2.narrow_cut[0]["wall_own_m"] == pytest.approx(8.0, abs=0.05)
    # and sinking the placement 8 m does not move either number
    _r3, st3 = _corridors(objs2, law, "shed", agl=-0.3)
    assert st3.narrow_cut[0]["wall_own_m"] == pytest.approx(8.0, abs=0.05)


def test_the_wall_height_separates_nothing_at_the_real_airports(objs, law):
    """RULINGS 2026-09-10ao's premise — "a kerb wall rises to its deck and
    no further; a building wall rises 6–12 m" — is FALSE at OTHH itself
    (spec §12f, measured on the same replay as §12e): only 9 of its 43
    accepted corridors stand at low kerbs (0.40–1.40 m); the other 34
    stand at walls 5.91–9.82 m high (`Bridge_06` 8.10–9.48,
    `TerminalRoads_03_004` 9.78, `Terminal_Parking_VCN_004` 9.60–9.82) —
    exactly the range of LEMD's cargo walls (`NEWCO` 6.63–10.45,
    `GAVIA` 2.29–10.83, `LEMD64` 10.46).  `own_m` at OTHH's own maximum
    + 0.5 keeps 64 of the 73 cargo candidates.  Nothing in law reads the
    height; this twin fails the day a height clause is written, and the
    numbers to re-measure are in §12f."""
    wc = law.tables.structures.cutout.wall_corridor
    assert not hasattr(wc, "corridor_wall_max_height_m")
    recs, st = _corridors(objs, law, "deep")
    assert st.corridors == 1 and len(recs) == 2, st.refused


# ── RULINGS 2026-09-10ac-1 (A): TERMINALS ONLY, gated OFF ───────────────

def _terminal_way(x0=-30.0, y0=60.0, x1=30.0, y1=120.0, wid=-900):
    """An ``aeroway=terminal`` outline of the airports feed."""
    return OsmWay(wid, "airports", ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)),
                  True, {"aeroway": "terminal", "building": "yes", "name": "T1"})


def test_the_terminal_clause_ships_off_and_only_reports_its_witness(objs, law):
    """The gate is OFF in ``structures.toml`` (spec §12f): a corridor with
    NO terminal anywhere near it is admitted exactly as before, and the
    admission line carries the witness so the owner can read the
    distances.  At OTHH the clause at 60 m would keep 7 of the owner's
    own 43 — that is why it ships off."""
    wc = law.tables.structures.cutout.wall_corridor
    assert wc.corridor_terminal_only is False and wc.corridor_terminal_m > 0.0
    recs, st = _corridors(objs, law, "door26")
    assert st.corridors == 1 and len(recs) == 2, st.refused
    line = [a for a in st.admission if "ADMITTED" in a]
    assert line and "(e) terminal" in line[0] and "[gate off]" in line[0], st.admission
    assert "no aeroway=terminal" in line[0], line[0]


def test_the_terminal_clause_admits_and_refuses_when_the_owner_turns_it_on(objs, law):
    """With the key on: the same corridor is REFUSED where the airport
    maps no terminal, and ADMITTED where an ``aeroway=terminal`` way lies
    within ``corridor_terminal_m`` of a mouth (the fixture's mouths sit at
    y = ±40; the terminal outline starts at y = 60, 20 m away)."""
    on = _wc_law(law, corridor_terminal_only=True, corridor_terminal_m=60.0)
    recs, st = _corridors(objs, on, "door26")
    assert recs == [] and st.corridors == 0
    assert any("no aeroway=terminal within corridor_terminal_m" in r for r in st.refused), \
        st.refused
    ways = _kerb_roads() + (_terminal_way(),)
    recs2, st2 = _corridors(objs, on, "door26", ways=ways)
    assert st2.corridors == 1 and len(recs2) == 2, st2.refused
    assert any("(e) terminal T1" in a and "ADMITTED" in a for a in st2.admission), \
        st2.admission
    # ...and a terminal beyond the radius refuses it again
    far = _kerb_roads() + (_terminal_way(y0=200.0, y1=260.0),)
    recs3, st3 = _corridors(objs, on, "door26", ways=far)
    assert recs3 == [] and st3.corridors == 0, st3.admission
