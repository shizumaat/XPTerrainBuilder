"""Issue #942 twins — A SHELL STANDING UP OUT OF ITS GROUND IS NEVER A PIT
(``planar/basin_datum.py``; 04i rule 1's rim read against the ground the
author placed it on as well as the centroid's, as 09ag rule 5b reads the
floor against the datum).

KSEZ (Sedona) is where it was found: the pack's rock formations are
terrain skins laid over real relief, ``OBJECT_MSL`` placed on the ground at
their anchors.  Read against the DEM under the component's centroid —
74 m over the anchor's for ``South_Airport_Ridge`` — the skin's low flank
read as a floor plate 2.5 m and more under the ground and its top as a 3 %
protrusion, so it was admitted as a covered pit 62 m deep and the relative
floor put the trench 63 m under the DEM (the solve's ``off_ground``).

The fixture is the same shape on a synthetic step DEM: the anchor on the
low ground, the skin's plateau under the high ground, a spike reaching
grade.  On main ``7e5ae9cc`` it is a basin; with the rule it is refused,
named, while a box pit stays a basin — level, and SUNK by a negative
``OBJECT_AGL`` with its walls topping out at the ground (VHHH's
``sea.obj`` class: the sink is the author's, the anchor's ground governs).
Law values are read from the tables, never retyped.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.basin_witness import read_objects
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import build_basins
from test_m4b import _box_obj
from test_v2basinfix import _airport, _cells, _FlatDem

LOW, RISE, RAMP_M = 700.0, 60.0, 20.0
SINK_M = 3.0


class _Step:
    """Low ground at the anchor, rising RISE over RAMP_M to a plateau."""

    provenance = {"synthetic": "step up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return LOW + RISE * min(1.0, max(0.0, x) / RAMP_M)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _skin_obj(path):
    """A heightfield skin from its anchor out along +x: a low flank at
    y = -5 (x <= 40), a plateau at y = +20 beyond x = 60, and one spike
    vertex at +62 that reaches the plateau ground."""
    xs = (0.0, 40.0, 60.0, 100.0, 140.0, 200.0)
    zs = (-50.0, 0.0, 50.0)
    vt = []
    for x in xs:
        for z in zs:
            y = -5.0 if x <= 40.0 else 20.0
            if x == 140.0 and z == 0.0:
                y = 62.0
            vt.append((x, y, z))
    nz = len(zs)
    tris = []
    for i in range(len(xs) - 1):
        for j in range(nz - 1):
            a, b, c, d = i * nz + j, i * nz + j + 1, (i + 1) * nz + j, (i + 1) * nz + j + 1
            tris += [(a, c, b), (b, c, d)]
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [k for t in tris for k in t]
    for k in range(0, len(idx), 10):
        chunk = idx[k:k + 10]
        lines.append(("IDX10 " if len(chunk) == 10 else "IDX ")
                     + " ".join(str(i) for i in chunk))
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return path


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("basin942_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text(
        "I\n1000 Version\n", encoding="utf-8", newline="")
    dd = law.tables.structures.basin.admission_depth_m
    return {"dir": d, "skin": _skin_obj(d / "skin.obj"),
            "pit": _box_obj(d / "pit.obj", hx=30.0, hz=20.0, depth=2.0 * dd),
            # walls from +SINK_M down: placed SINK_M under its anchor, the
            # rim stands at the ground
            "sunk": _box_obj(d / "sunk.obj", hx=30.0, hz=20.0, depth=2.0 * dd, top=SINK_M)}


def _basins(objs, law, name, dem, sink=0.0):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    a = _airport(objs, law, name, dem, hx=10.0, hz=10.0)
    if sink:
        a = _dc.replace(a, dsf_objects=tuple(
            _dc.replace(o, kind="OBJECT_AGL", y_offset_m=-sink) for o in a.dsf_objects))
    objects, rep = read_objects(a, law, cache)
    _cl, basins, stats = build_basins(a, Classification(tuple(_cells()), (), {}, ()),
                                      law, (), objects, cache=cache, report=rep)
    return objects, basins, stats


def test_a_terrain_skin_read_against_a_high_centroid_ground_is_not_a_pit(objs, law):
    objects, basins, stats = _basins(objs, law, "skin", _Step())
    # rule 1 still WITNESSES it (the reading other consumers see is unchanged)...
    assert [o.id for o in objects if o.witnesses] == ["dsf:obj0"]
    # ...but no pit is cut, and the refusal names the datum and the numbers
    assert basins == ()
    bl = law.tables.structures.basin
    line = next(r for r in stats.refused if "the ground it was placed on" in r)
    assert "dsf:obj0 skin.obj#0" in line
    assert f"rim_protrusion_max_fraction {bl.rim_protrusion_max_fraction:.0%}" in line


@pytest.mark.parametrize("name, sink", [("pit", 0.0), ("sunk", SINK_M)])
def test_a_pit_stays_a_basin_level_or_sunk_by_its_author(objs, law, name, sink):
    _objects, basins, stats = _basins(objs, law, name, _FlatDem(), sink)
    assert len(basins) == 1, stats.refused
    assert not any("the ground it was placed on" in r for r in stats.refused)
