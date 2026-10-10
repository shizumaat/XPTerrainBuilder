"""Lane `basins526` twins — pit / basin objects (owner RULINGS 2026-10-10h;
issues #526, #527, #528; design spec §47 (3) AMENDED, object spec §14 (2)
(a)/(b), §14a (2)).

Four general rules, each a twin that FAILED on main f5f11c81f and passes
with the fix (OTHH is the witness, never the scope):

* G — THE GAP: a pit shell with NO wall face at its rim (sloped banks,
  measured shell thickness under the thinnest solid) keeps its rim ON
  the object's outline and takes the wall band INSIDE it, under the
  banks; a bowl whose banks are narrower than the band keeps the outward
  yield (the degenerate rule).
* B1 (#526): a component stands in the ring its FEET stand in; the plan
  centroid decides only for a footless one (`anchor_rule.ring_of_part`,
  the ONE membership function).
* B2 (#527): the rim anchor stands the writer's own tolerance OUTSIDE
  the ring (`anchor_rule.rim_anchor_point`), clear of the wall band the
  DSF requantisation could put it on.
* B3 (#528): a piece carried by a BASIN body keeps that carrier
  (`footprint_carry.contents_seat`); a footless group inside a ring is
  never a §14a (2) floor member.

Law values are read from the tables, never retyped.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Point, Polygon

from auto_patch_v2.airport import anchor_rule as _ar
from auto_patch_v2.airport import footprint_carry as _fc
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.basin_witness import read_objects
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.placement import TOL_DEG
from auto_patch_v2.planar.basins import build_basins

from test_v2basinfix import _FlatDem, _airport, _cells

HX, HZ = 30.0, 20.0


def _bowl_obj(path, hx, hz, depth, bank, outlet=True):
    """A pit with SLOPED BANKS: the outline ``2hx x 2hz`` at y = 0, the
    floor plate inset ``bank`` all round at ``-depth``, four bank quads
    between them, and (``outlet``) a culvert floor at ``-depth`` running
    from the plate out to the +x outline — the witnessed class: the
    plate REACHES the outline somewhere (`shell_thickness_m` 0, no wall
    face) while the banks are ``bank`` wide elsewhere."""
    outer = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    inner = [(-hx + bank, -hz + bank), (hx - bank, -hz + bank),
             (hx - bank, hz - bank), (-hx + bank, hz - bank)]
    vt = []
    for x, z in outer:
        vt.append((x, 0.0, z))
    for x, z in inner:
        vt.append((x, -depth, z))
    tris = []
    for i in range(4):
        a, b = i, (i + 1) % 4
        tris += [(a, 4 + a, b), (4 + a, 4 + b, b)]
    tris += [(4, 6, 5), (4, 7, 6)]
    if outlet:
        # a ledge at -depth from the plate's +x edge (inner vertices 5, 6,
        # WELDED) out to the outline: the plate reaches the outline there
        vt.append((hx, -depth, -hz + bank))
        vt.append((hx, -depth, hz - bank))
        tris += [(5, 8, 9), (5, 9, 6)]
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {3 * len(tris)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    idx = [i for t in tris for i in t]
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
    d = tmp_path_factory.mktemp("basins526_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text(
        "I\n1000 Version\n", encoding="utf-8", newline="")
    dd = law.tables.structures.basin.admission_depth_m
    return {
        "dir": d,
        # wide banks (6 m): the band fits under them
        "bowl": _bowl_obj(d / "bowl.obj", HX, HZ, 2.0 * dd, 6.0),
        # a well 1.6 m wide: the band inside would leave no floor
        "cup": _bowl_obj(d / "cup.obj", 0.8, 5.0, 2.0 * dd, 0.2),
    }


def _basin_of(objs, law, name, hx, hz):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    a = _airport(objs, law, name, _FlatDem(), hx=hx, hz=hz)
    objects, rep = read_objects(a, law, cache)
    _cl, basins, stats = build_basins(a, Classification(tuple(_cells()), (), {}, ()),
                                      law, (), objects, cache=cache, report=rep)
    assert len(basins) == 1, stats.refused
    return basins[0], stats


# ── G: THE GAP ────────────────────────────────────────────────────────────

def test_a_bank_sided_pit_keeps_its_rim_on_the_outline_and_the_band_inside(objs, law):
    """§47 (3) AMENDED (RULINGS 2026-10-10h (2)): no wall face -> the rim
    IS the outline (within the identity lattice) and the floor ring
    stands the band inside it.  On main the rim stood ``ring_floor_m``
    OUTSIDE the outline: a slot 0.71 m wide and the pit's depth deep all
    round the object."""
    co = law.tables.structures.cutout
    grid = law.tables.emit.identity.min_distinct_spacing_m
    b, stats = _basin_of(objs, law, "bowl", HX, HZ)
    region = Polygon(b.region)
    rim = Polygon(b.wall_path)
    floor = Polygon(b.ring)
    assert stats.bank_bands and not stats.rim_yields, (stats.bank_bands, stats.rim_yields)
    # every rim vertex within half a lattice diagonal of the outline
    ext = region.exterior
    assert max(ext.distance(Point(p)) for p in b.wall_path) <= grid * math.sqrt(2) / 2 + 1e-6
    # no slot: the ground cut outside the object is the lattice residue only
    assert rim.difference(region).area / ext.length < 0.2
    # the floor ring stands the band inside the outline
    assert floor.distance(ext) >= co.ring_floor_m - grid * math.sqrt(2) / 2 - 1e-6
    assert region.contains(floor)


def test_a_bowl_whose_banks_cannot_hold_the_band_keeps_the_outward_yield(objs, law):
    """THE DEGENERATE RULE: banks narrower than the band — the band
    inside would leave no floor — keep §47 (3)'s outward yield, named."""
    co = law.tables.structures.cutout
    b, stats = _basin_of(objs, law, "cup", 0.8, 5.0)
    assert stats.rim_yields and not stats.bank_bands, (stats.rim_yields, stats.bank_bands)
    assert "DEGENERATE" in stats.rim_yields[0]
    region = Polygon(b.region)
    rim = Polygon(b.wall_path)
    assert rim.area > region.area
    # the rim yielded outward by the band, the floor at the outline
    assert Polygon(b.ring).distance(region.exterior) <= co.ring_floor_m


# ── B2 (#527): the rim anchor stands clear of the band ────────────────────

def _square_deg(lat0=25.25, lon0=51.62, side=0.001):
    return ((lat0, lon0), (lat0, lon0 + side), (lat0 + side, lon0 + side), (lat0 + side, lon0))


def test_the_rim_anchor_stands_a_writer_tolerance_outside_the_ring():
    ring = _square_deg()
    ml, mo = _ar._m_per_deg(ring[0][0])
    for i in range(len(ring)):
        la, lo = _ar.rim_anchor_point(ring, i)
        assert not _ar._inside(ring, la, lo)
        v = ring[i]
        d = math.hypot((la - v[0]) * ml, (lo - v[1]) * mo)
        assert d == pytest.approx(TOL_DEG * max(ml, mo), rel=1e-4)
        # and still clear after a full quantum of requantisation drift
        # in the worst direction (toward the ring) on each axis
        q = TOL_DEG / 4.0
        for dlat in (-q, q):
            for dlon in (-q, q):
                assert not _ar._inside(ring, la + dlat, lo + dlon)


def test_the_basin_anchor_is_the_nearest_vertex_pushed_outward():
    ring = _square_deg()
    rim = _ar.RimRing("basin_wall:0", ring)
    lat0, lon0 = ring[0]
    geom = _ar.BodyGeometry(((lat0 + 0.0004, lon0 + 0.0004, -3.0,
                              ((lat0 + 0.0004, lon0 + 0.0004, -3.0),)),),
                            lat0 + 0.0001, lon0 + 0.0001)
    a = _ar._basin_rim_anchor(geom, lambda la, lo: 3.96, [rim])
    assert a is not None and a.body_class == _ar.BASIN
    assert not _ar._inside(ring, a.lat, a.lon)
    assert a.lat < lat0 and a.lon < lon0           # outward from vertex 0


