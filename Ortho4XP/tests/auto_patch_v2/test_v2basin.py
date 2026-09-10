"""`v2basin` twins (RULINGS 2026-09-09ag, spec §13): THE BASIN ADMISSION
TEST — a basin is a SUNKEN SOLID, and its depth is AUTHORED.

Rule 1's local ground is the DEM at the component, so a pack authored as
ONE FLAT PLANE over real relief (LEMD: Aerosoft, 32 m under the terminal)
reads an ordinary ground-floor slab — authored 0.5 m under its own y = 0 —
as metres "under the local ground", with a genuine floor plate, a shell
topping out in the band and a CLOSED rim.  Rule 5b refuses it: the
witness's own render datum (``anchor_z + agl``) must stand at the ground
along the ring, ``R_est − datum <= [basin] datum_drop_max_m``.  A datum
ABOVE the ground is never refused — a pit on a slope is still a pit.

Law values are read from the tables inside the tests, never retyped.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import build_basins, read_objects

from test_m4b import _airport, _box_obj, _cells, _rect


class _StepDem:
    """A flat apron at 700 west of x = 10 and a PLATEAU 12 m higher east
    of it — the LEMD shape: the pack's anchor sits on the low ground, its
    terminal geometry on the high."""

    provenance = {"synthetic": "700 west of x = 10, 712 east"}
    step_m = 12.0

    def z(self, x: float, y: float) -> float:
        return 700.0 if x < 10.0 else 700.0 + self.step_m

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _FlatDem:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _KnollDem:
    """A mound: 703 inside a 15 m radius, 700 outside — the anchor's
    ground stands ABOVE the ring's, a pit dug through a rise."""

    provenance = {"synthetic": "703 inside r = 15, 700 outside"}
    rise_m = 3.0

    def z(self, x: float, y: float) -> float:
        return 700.0 + (self.rise_m if x * x + y * y < 15.0 * 15.0 else 0.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _offset_box(path, x0, x1, hz, depth, top):
    """A four-walled box with a floor, spanning authored x ``x0 … x1`` and
    z ``-hz … hz``, walls from ``top`` down to ``-depth`` and a floor at
    ``-depth`` — ``_box_obj``'s shape, moved OFF the anchor so the DEM at
    the anchor and the DEM under the body can differ."""
    corners = [(x0, -hz), (x1, -hz), (x1, hz), (x0, hz)]
    vt: list = []
    for x, z in corners:
        vt.append((x, top, z))
        vt.append((x, -depth, z))
    tris: list = []
    for i in range(4):
        a, b = 2 * i, 2 * ((i + 1) % 4)
        tris += [(a, a + 1, b), (a + 1, b + 1, b)]
    tris += [(1, 3, 5), (1, 5, 7)]
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
    for k in range(0, len(idx), 10):
        lines.append("IDX10 " + " ".join(str(i) for i in idx[k:k + 10])
                     if len(idx[k:k + 10]) == 10
                     else "IDX " + " ".join(str(i) for i in idx[k:k + 10]))
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("v2basin_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    dd = law.tables.structures.basin.admission_depth_m
    return {
        "dir": d,
        # a SUNKEN SOLID: walls from its own datum down to 2 x the
        # admission depth, a floor there — the OTHH pit shape
        "pit": _box_obj(d / "pit.obj", hx=30.0, hz=20.0, depth=2.0 * dd),
        # a GROUND-FLOOR SLAB standing on the plateau: its floor is
        # authored a fifth of the admission depth under its own datum and
        # its walls rise to the plateau's ground — the LEMD02 shape
        "slab": _offset_box(d / "slab.obj", 20.0, 80.0, 20.0,
                            depth=dd / 5.0, top=_StepDem.step_m),
    }


def _basins(objs, law, dem, placements, drop_max=None):
    """Read and admit, optionally with ``datum_drop_max_m`` overridden —
    the interventional arm: the ONLY thing that changes between them."""
    if drop_max is not None:
        bl = _dc.replace(law.tables.structures.basin, datum_drop_max_m=drop_max)
        st = _dc.replace(law.tables.structures, basin=bl)
        law = _dc.replace(law, tables=_dc.replace(law.tables, structures=st))
    airport = _dc.replace(_airport(objs, law, placements), dem=dem)
    objects, rep = read_objects(airport, law)
    cl = Classification(tuple(_cells()), (), {}, ())
    _cl, basins, stats = build_basins(airport, cl, law, (), objects, report=rep)
    return objects, basins, stats


def test_a_sunken_pit_is_admitted(objs, law):
    """The pit's floor is authored the whole depth under its OWN datum,
    which stands AT the ground: drop 0, admitted, and the note carries
    the authored share."""
    bl = law.tables.structures.basin
    objects, basins, stats = _basins(objs, law, _FlatDem(),
                                     [("pit", (0.0, 0.0), 0.0, 0.0)])
    assert [r for r in stats.refused if "rule 6" in r] == []
    assert len(basins) == 1
    b = basins[0]
    assert b.rim_estimate_m == pytest.approx(700.0)
    assert b.plate_y_m == pytest.approx(-2.0 * bl.admission_depth_m, abs=0.3)
    note, = [n for n in b.notes if "under the ring's ground" in n]
    assert "+0.00 m under the ring's ground" in note, note
    # the whole depth below grade is AUTHORED
    d = 700.0 - b.floor_z
    assert f"authored depth {d:.2f} of {d:.2f} m" in note, note


def test_a_slab_over_datum_relief_is_refused(objs, law):
    """The LEMD class: the slab's datum sits on the low ground while its
    body stands on the plateau, so rule 1 reads its 0.5 m ground floor as
    12 m "under the local ground".  Rule 5b refuses it, naming the drop
    and the authored share."""
    bl = law.tables.structures.basin
    dem = _StepDem()
    objects, basins, stats = _basins(objs, law, dem,
                                     [("slab", (0.0, 0.0), 0.0, 0.0)])
    # the slab IS a below-grade witness under every rule but 5b
    assert objects[0].witnesses and objects[0].solid_min_z is not None
    assert basins == ()
    refusal, = [r for r in stats.refused if "rule 6" in r]
    assert "slab.obj" in refusal and "datum relief, not a sunken solid" in refusal
    assert f"stands {dem.step_m:.2f} m UNDER the ground" in refusal, refusal
    assert f"AUTHORED only {bl.admission_depth_m / 5.0:.2f} m" in refusal, refusal


def test_the_refusal_is_the_datum_clause_and_nothing_else(objs, law):
    """The interventional arm: the SAME slab, the same reader, the same
    region — only ``datum_drop_max_m`` changes.  Raised past the drop it
    is admitted again, which is what makes 5b the clause that refuses it
    (and what the pre-09ag law did)."""
    dem = _StepDem()
    _o, basins, stats = _basins(objs, law, dem, [("slab", (0.0, 0.0), 0.0, 0.0)],
                                drop_max=dem.step_m + 1.0)
    assert [r for r in stats.refused if "rule 6" in r] == []
    assert len(basins) == 1
    assert basins[0].floor_z == pytest.approx(
        700.0 - law.tables.structures.basin.admission_depth_m / 5.0, abs=0.1)


def test_a_pit_whose_datum_stands_above_the_ground_is_still_admitted(objs, law):
    """One-sided by ruling: a pit dug where the anchor's ground is HIGHER
    than the ring's median is not the datum-relief artefact — only a datum
    sitting UNDER the terrain manufactures depth."""
    dem = _KnollDem()
    _o, basins, stats = _basins(objs, law, dem, [("pit", (0.0, 0.0), 0.0, 0.0)])
    assert [r for r in stats.refused if "rule 6" in r] == []
    assert len(basins) == 1
    b = basins[0]
    # the datum sits on the mound, the ring's median on the flat below it
    assert b.rim_estimate_m == pytest.approx(700.0)
    assert b.floor_z < b.rim_estimate_m
    note, = [n for n in b.notes if "under the ring's ground" in n]
    assert f"stands -{dem.rise_m:.2f} m under the ring's ground" in note, note


def test_the_gate_is_the_law_value_and_the_contact_band(law):
    """No literal in the code: the law carries it, and 09ag sets it to the
    ground-contact band rule 1's rim test already uses."""
    bl = law.tables.structures.basin
    assert bl.datum_drop_max_m == pytest.approx(bl.contact_band_m)
    assert 0.0 < bl.datum_drop_max_m < bl.admission_depth_m
