"""A PART NO GROUND HOLDS IS NO BASIN WITNESS (issue #1685).

KIAH's AeroX ground markings (``Ground/Markings_any/18A.obj``) are a
4.77 x 5.05 m box whose lid is the marking at y = +0.02 and whose walls
and floor run to y = -2029.11 — a stray authoring part, rendered but never
seen.  Read as a pit, the basin cut its floor to -2001 m and the solve put
8 vertices 2 km outside the airport's ground envelope (refused patch).

The rule: a component whose floor stands more than
``emit.cockpit.sentinel_drop_m`` (the margin of the solve's ground
envelope, ``solve/ground_band.py``) under the local ground is not a
witness and not a deep part; it is NAMED among rule 1's refusals.  A pit
shallower than that bound is unchanged.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.basin_witness import read_objects
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import build_basins
from test_m4b import _box_obj
from test_v2basinfix import _airport, _cells, _FlatDem


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("basin1685_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text(
        "I\n1000 Version\n", encoding="utf-8", newline="")
    drop = float(law.tables.emit.cockpit.sentinel_drop_m)
    return {"dir": d,
            # the KIAH marking's shape: a lidded box to -2029.11 m
            "stray": _box_obj(d / "stray.obj", hx=2.385, hz=2.525, depth=2029.11,
                              top=0.02, lid=True),
            # the control: the same footprint, a floor just inside the bound
            "pit": _box_obj(d / "pit.obj", hx=2.385, hz=2.525, depth=drop - 5.0)}


def _read(objs, law, name):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    a = _airport(objs, law, name, _FlatDem(), hx=2.385, hz=2.525)
    objects, rep = read_objects(a, law, cache)
    _cl, basins, stats = build_basins(a, Classification(tuple(_cells()), (), {}, ()),
                                      law, (), objects, cache=cache, report=rep)
    return objects, rep, basins, stats


def test_a_part_deeper_than_the_ground_envelope_is_no_witness_and_is_named(objs, law):
    objects, rep, basins, stats = _read(objs, law, "stray")
    assert not any(o.witnesses for o in objects)
    assert all(o.solid_min_z is None for o in objects)      # no depth reaches anyone
    assert basins == ()
    (n, depth), = [v for k, v in rep.implausible_depth.items() if k.endswith("stray.obj")]
    assert n == 1 and depth == pytest.approx(-2029.11, abs=0.01)
    assert any("stray.obj x1" in r and "2029.11 m" in r and "#1685" in r
               for r in stats.refused), stats.refused


def test_a_pit_inside_the_bound_stays_a_basin(objs, law):
    objects, rep, basins, stats = _read(objs, law, "pit")
    assert [o.id for o in objects if o.witnesses] == ["dsf:obj0"]
    assert len(basins) == 1, stats.refused
    assert not rep.implausible_depth
