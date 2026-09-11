"""Lane `v2skirt` twins — A SKIRTED BUILDING NEEDS NO PAD (owner RULINGS
2026-09-10ag over 10af; spec ``docs/specs/auto-patch-v2/
design-surface-spec.md`` §22).

* the READER (`airport/skirt.py`): a box on a 2 m foundation skirt reads
  ``is_skirt`` with ``skirt_depth`` 2.0 and a below-zero perimeter
  fraction at the whole rim; a road-width door well in the same box is
  NOT a skirt (its below-zero geometry meets the perimeter at one face
  only); a box with nothing under its authored zero is neither;
* the PAD (§22.2): the skirted box over 1.5 m of relief mints NO
  ``building`` pad and the ground under it stays the surrounding role;
  the same box over 3 m of relief (relief > s) keeps today's pad, and so
  does a skirt-less box;
* the SEAT (§22.3): a body every one of whose members is skirted seats at
  its LOW-side foot — the low wall foot touches the ground (nothing
  floating) and the high side buries by the relief — while an unskirted
  body keeps 10i's median.

Law values are read from the tables inside the tests, never retyped.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import obj8, skirt
from auto_patch_v2.airport.rebake_plan import plan as rebake_plan
from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.roles import classify
from auto_patch_v2.emit.rebake import seat
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Building, DsfObject, Pavement,
                                         Runway, RunwayEnd, SceneryPack)
from auto_patch_v2.model.frame import Frame

from test_tunnel_objects import _slab, _write

HX, HZ = 15.0, 10.0                     # the fixture building: 30 x 20 m


class _Slope:
    """A plane rising in x at a given grade (the airport frame)."""

    def __init__(self, grade: float) -> None:
        self.grade = grade
        self.provenance = {"synthetic": f"plane {grade:.3%} up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + self.grade * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


# ── the synthetic OBJ8s ──────────────────────────────────────────────────

def _box(path, skirt_depth=0.0, top=8.0):
    """Four walls and a roof over 30 x 20 m, from ``-skirt_depth`` to
    ``top``, plus the floor slab at the bottom: with a skirt the WHOLE
    footprint stands below the authored zero (the owner's "uniform across
    its bottom"), and without one nothing does."""
    vt: list = []
    tris: list = []
    _slab(vt, tris, -HX, HX, -HZ, HZ, -skirt_depth, top)
    if skirt_depth > 0.0:               # the foundation slab at the skirt's bottom
        b = len(vt)
        vt += [(-HX, -skirt_depth, -HZ), (HX, -skirt_depth, -HZ),
               (HX, -skirt_depth, HZ), (-HX, -skirt_depth, HZ)]
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    return _write(path, vt, tris)


def _box_with_well(path, width=3.7, depth=2.0, top=8.0):
    """The same box with NO skirt but a road-width well outside its south
    face — 10af's corridor / door well, which must never read as a
    skirt."""
    vt: list = []
    tris: list = []
    _slab(vt, tris, -HX, HX, -HZ, HZ, 0.0, top)
    hw, thick, out = width / 2.0, 0.25, 1.5
    _slab(vt, tris, -hw - thick, -hw, HZ, HZ + out + thick, -depth, 0.0)
    _slab(vt, tris, hw, hw + thick, HZ, HZ + out + thick, -depth, 0.0)
    _slab(vt, tris, -hw, hw, HZ + out, HZ + out + thick, -depth, 0.0)
    b = len(vt)
    vt += [(-hw - thick, -depth, HZ), (hw + thick, -depth, HZ),
           (hw + thick, -depth, HZ + out + thick), (-hw - thick, -depth, HZ + out + thick)]
    tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    return _write(path, vt, tris)


@pytest.fixture(scope="module")
def law():
    return Law.load()


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("skirt") / "objects"
    d.mkdir()
    return {"dir": d,
            "skirted": _box(d / "skirted.obj", skirt_depth=2.0),
            "flat": _box(d / "flat.obj"),
            "well": _box_with_well(d / "well.obj")}


def _cache(law):
    return obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)


# ── the reader ───────────────────────────────────────────────────────────

def test_uniform_below_zero_extent_is_a_skirt(objs, law):
    c = _cache(law)
    r = skirt.reading(c, str(objs["skirted"]), law)
    assert r.skirt and r.reason == "skirt"
    assert r.depth_m == pytest.approx(2.0)
    assert r.depth_min_m == pytest.approx(r.depth_max_m)
    # the below-zero geometry runs the WHOLE perimeter (the ruling's bar
    # is the law's fraction; the fixture is uniform, so it reads ~1)
    assert r.perimeter_fraction >= law.tables.structures.skirt.perimeter_fraction
    assert r.perimeter_fraction == pytest.approx(1.0, abs=0.02)
    assert r.footprint_perimeter_m == pytest.approx(2 * (2 * HX + 2 * HZ), rel=0.01)
    assert skirt.is_skirt(c, str(objs["skirted"]), law)
    assert skirt.skirt_depth(c, str(objs["skirted"]), law) == pytest.approx(2.0)


def test_road_width_cut_is_not_a_skirt(objs, law):
    """10af: "a relatively small, approximately road width extension to
    render the door or corridor walls below the surface" — a corridor,
    Law C's business, never a skirt here."""
    c = _cache(law)
    r = skirt.reading(c, str(objs["well"]), law)
    assert r.below_zero and not r.skirt
    assert r.perimeter_fraction < law.tables.structures.skirt.perimeter_fraction
    assert "narrow cut" in r.reason
    assert skirt.skirt_depth(c, str(objs["well"]), law) is None
    assert skirt.below_zero_perimeter_fraction(c, str(objs["well"]), law) == \
        pytest.approx(r.perimeter_fraction)


def test_no_below_zero_geometry_is_not_a_skirt(objs, law):
    c = _cache(law)
    r = skirt.reading(c, str(objs["flat"]), law)
    assert not r.skirt and not r.below_zero and r.depth_m is None
    assert r.reason == "no below-zero geometry"


# ── the pad (§22.2) ──────────────────────────────────────────────────────

def _airport(objs, law, name, grade):
    """The 30 x 20 building at the frame origin, one placement of
    ``name`` under it, on a plane of ``grade``."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", str(objs["dir"].parent / "Earth nav data" / "apt.dat"),
                       "0", (), ())
    ring = ((-HX, -HZ), (HX, -HZ), (HX, HZ), (-HX, HZ))
    bld = Building("dsf:object0", ring, (), "dsf:object:building", None, None)
    # an apron beside the building: the pad gate is "inside the boundary,
    # else near pavement" (``evidence._pads``), and the fixture has no
    # boundary
    apron = Pavement("pav1", 1, ((-120.0, -110.0), (120.0, -110.0),
                                 (120.0, -30.0), (-120.0, -30.0)), (), "apron")
    dsf = (DsfObject("dsf:obj0", f"objects/{name}.obj", (0.0, 0.0), 0.0, None, False,
                     None, 0.0, str(objs[name]), "OBJECT"),)
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (apron,), (), {}, (), (),
                   (), (), (), (bld,), dsf, pack, _Slope(grade), law.ruleset_key)


def _pads_of(objs, law, name, grade):
    a = _airport(objs, law, name, grade)
    cl = classify(a, law, load_rules(), cache=_cache(law))
    return [c for c in cl.cells if c.role == "building"], cl


def test_skirted_building_over_relief_within_the_skirt_mints_no_pad(objs, law):
    """§22.2: 1.5 m of relief across a 30 m footprint, a 2 m skirt — the
    building sits on the sloping ground and needs no pad."""
    pads, cl = _pads_of(objs, law, "skirted", 1.5 / (2 * HX))
    assert pads == []
    assert cl.stats.get("pads_skirted") == 1
    assert any("dropped (skirted)" in n for n in cl.notes)


def test_relief_beyond_the_skirt_keeps_todays_pad(objs, law):
    """"Where a skirted building's footprint relief exceeds s, the excess
    is handled as today" (10ag): 3 m of relief against a 2 m skirt."""
    pads, cl = _pads_of(objs, law, "skirted", 3.0 / (2 * HX))
    assert len(pads) == 1
    assert cl.stats.get("pads_skirted") == 0


def test_a_building_with_no_skirt_keeps_todays_pad(objs, law):
    """"A building without a skirt still gets the flat pad of 09c" —
    even on relief a skirt would have covered."""
    pads, cl = _pads_of(objs, law, "flat", 1.5 / (2 * HX))
    assert len(pads) == 1
    assert cl.stats.get("pads_skirted") == 0
    # ...and so does a road-width cut: a corridor is not a foundation
    pads, _cl = _pads_of(objs, law, "well", 1.5 / (2 * HX))
    assert len(pads) == 1


# ── the seat (§22.3) ─────────────────────────────────────────────────────

def _seat(objs, law, name, grade):
    a = _airport(objs, law, name, grade)
    cache = _cache(law)
    from auto_patch_v2.planar.basins import read_objects
    objects, _rep = read_objects(a, law, cache)
    p = rebake_plan(a, objects, cache, law)
    dem = a.dem
    to_xy = a.frame.transformers()[0]

    def sampler(lat, lon):
        x, y = to_xy(lon, lat)
        return (dem.z(x, y), False)
    return p, seat(p, sampler, law), a, dem, to_xy


def test_skirted_body_seats_at_its_low_side_foot(objs, law):
    """10ag (2): the low side's foot touches the ground and the high side
    buries up to the relief — never 10i's median, which would float the
    low side by half of it."""
    p, res, a, dem, _to_xy = _seat(objs, law, "skirted", 1.5 / (2 * HX))
    assert all(m.skirted for u in p.units for m in u.members)
    assert p.counts["skirted_members"] == 1
    lo, hi = dem.z(-HX, 0.0), dem.z(HX, 0.0)
    assert hi - lo == pytest.approx(1.5, abs=0.01)
    cl = [c for c in res.clusters if c.ground_m is not None]
    assert len(cl) == 1
    # the body's rendered y = 0 plane IS its seat ground; its skirt
    # bottom stands 2 m under that
    zero = cl[0].ground_m
    bottom = zero - 2.0
    assert bottom == pytest.approx(lo, abs=0.02)         # the LOW foot touches
    assert hi - bottom == pytest.approx(1.5, abs=0.02)   # the high side buries
    # ...and 10i's median over the same feet would have floated the low
    # corner by half the relief (the part's own ``target``, 702.0)
    assert zero == pytest.approx(min(
        dem.z(sx * HX, sz * HZ) + 2.0 for sx in (-1, 1) for sz in (-1, 1)), abs=0.02)
    assert zero == pytest.approx(lo + 2.0, abs=0.02)
    assert zero < (lo + hi) / 2.0 + 2.0 - 0.5
    # nothing floats: every wall foot of the body is at or under its ground
    for sx in (-1, 1):
        for sz in (-1, 1):
            assert bottom <= dem.z(sx * HX, sz * HZ) + 1e-6


def test_an_unskirted_body_keeps_the_median(objs, law):
    """Every other body is 10i's median exactly — the deviation is the
    skirted body's alone."""
    p, res, a, dem, _to_xy = _seat(objs, law, "flat", 1.5 / (2 * HX))
    assert not any(m.skirted for u in p.units for m in u.members)
    assert p.counts["skirted_members"] == 0
    cl = [c for c in res.clusters if c.ground_m is not None]
    assert len(cl) == 1
    # feet at the authored zero over ±0.75 m of relief: the median is the
    # mid-slope value, NOT the low corner
    assert cl[0].ground_m == pytest.approx(dem.z(0.0, 0.0), abs=0.02)
    assert cl[0].ground_m > dem.z(-HX, 0.0) + 0.5


def test_the_law_register(law):
    sk = law.tables.structures.skirt
    assert sk.perimeter_fraction == 0.5              # 10af proposes 0.5
    assert sk.drops_pad and sk.seat_low_side         # both halves of 10ag
    assert sk.min_depth_m > 0.0 and sk.depth_tolerance_m > 0.0
    assert 0.0 < sk.pad_cover_fraction <= 1.0
