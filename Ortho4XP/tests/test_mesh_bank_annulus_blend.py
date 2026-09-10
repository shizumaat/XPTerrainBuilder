"""THE ENGINE BLENDS THE BANK (owner RULINGS 2026-09-09p (1) / 2026-09-09t;
spec ``docs/specs/auto-patch-v2/design-surface-spec.md`` §13).

A v2 patch stands off the raw DEM, so outside every boundary ring it emits
a 1:3 BANK down (or up) to a ``o4_feature=bank_foot`` ring ON the DEM.  The
ground between them is a RULED surface — linear in plan distance from ring
to foot — and ``interpolate_free_interior_altitudes`` is a GRAPH-harmonic
extension, which squeezes it against the inner ring (111 % of grade where
the bank is 33 %).  09f-1's answer, authoring the face with intermediate
LEVEL RINGS, re-emitted the foot's own edges wherever the bank was
narrower than a level's offset and hung Triangle's segment recovery; the
rings are deleted and the ENGINE interpolates the annulus instead.

This twin is the engine's own: a synthetic annulus between a square patch
ring at z 10 and a foot ring at z 0, with the mesh arrays, the ``.poly``
ring edges and the patch ``.osm`` the function actually reads.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Mesh_Utils as MESH  # noqa: E402

STRIDE = 6
VECTOR_COLUMN = 5
DEM_SENTINEL = 999.0

LAT, LON = 30, 31
DEG = 111120.0                      # metres per degree of latitude
SCALX = numpy.cos((LAT + 0.5) * numpy.pi / 180.0)

INNER_M = 100.0                     # the design ring: a 200 m square
BANK_M = 60.0                       # the bank's plan width
OUTER_M = INNER_M + BANK_M
RING_Z = 10.0                       # the design ring's altitude
FOOT_Z = 0.0                        # the foot IS the DEM
SLOPE = (RING_Z - FOOT_Z) / BANK_M  # the ring-to-foot slope, 1:6 here


class _Tile:
    lat, lon = LAT, LON
    auto_patch = "All"


def _square(half_m, step_m):
    """A closed square ring of side ``2*half_m``, sampled every
    ``step_m``, in METRES (the isotropic frame)."""
    n = int(round(2 * half_m / step_m))
    side = [-half_m + 2 * half_m * k / n for k in range(n)]
    pts = ([(x, -half_m) for x in side]
           + [(half_m, y) for y in side]
           + [(-x, half_m) for x in side]
           + [(-half_m, -y) for y in side])
    return pts


def _to_ll(x_m, y_m):
    return (LAT + y_m / DEG, LON + x_m / (DEG * SCALX))


def _write_patch_osm(path, inner, outer):
    lines = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<osm version='0.6' generator='twin'>"]
    nid = 0
    ids = {}
    for name, ring, z in (("inner", inner, RING_Z), ("outer", outer, FOOT_Z)):
        ids[name] = []
        for (x, y) in ring:
            nid -= 1
            lat, lon = _to_ll(x, y)
            lines.append(f"  <node id='{nid}' action='modify' visible='true' "
                         f"lat='{lat:.11f}' lon='{lon:.11f}'>")
            lines.append(f"    <tag k='alt_abs' v='{z:.3f}' />")
            lines.append("  </node>")
            ids[name].append(nid)
    wid = -10000
    for name, tags in (("inner", [("o4_feature", "graded_surface"),
                                  ("role", "apron")]),
                       ("outer", [("o4_feature", "bank_foot"),
                                  ("ref", "bank:0")])):
        wid -= 1
        lines.append(f"  <way id='{wid}' action='modify' visible='true'>")
        for v in ids[name] + [ids[name][0]]:
            lines.append(f"    <nd ref='{v}' />")
        for k, val in tags:
            lines.append(f"    <tag k='{k}' v='{val}' />")
        lines.append("  </way>")
    lines.append("</osm>")
    path.write_text("\n".join(lines) + "\n")


def _write_poly(path, edges):
    out = ["0 2 0 0", f"{len(edges)} 1"]
    for k, (a, b) in enumerate(edges, start=1):
        out.append(f"{k} {a + 1} {b + 1} {MESH.PATCH_RING_MARKER}")
    out.append("0")
    path.write_text("\n".join(out) + "\n")


@pytest.fixture()
def annulus(tmp_path, monkeypatch):
    """The whole fixture: mesh arrays, a ``.poly`` of the two rings and a
    patch ``.osm`` naming which of them is the foot."""
    inner = _square(INNER_M, 20.0)
    outer = _square(OUTER_M, 20.0)

    rows = [(x, y, RING_Z) for (x, y) in inner]
    rows += [(x, y, FOOT_Z) for (x, y) in outer]
    n_inner, n_outer = len(inner), len(outer)
    ring_count = n_inner + n_outer

    # free interior vertices: a grid over the annulus, at the DEM
    free_xy = []
    step = 7.5
    k = int(OUTER_M / step)
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            x, y = i * step, j * step
            if max(abs(x), abs(y)) <= INNER_M + 1.0:
                continue                         # inside the design ring
            if max(abs(x), abs(y)) >= OUTER_M - 1.0:
                continue                         # outside the foot
            free_xy.append((x, y))
    rows += [(x, y, DEM_SENTINEL) for (x, y) in free_xy]

    vertices = numpy.zeros(STRIDE * len(rows))
    for index, (x, y, z) in enumerate(rows):
        lat, lon = _to_ll(x, y)
        vertices[STRIDE * index] = lon - LON          # tile-relative
        vertices[STRIDE * index + 1] = lat - LAT
        vertices[STRIDE * index + 2] = z
        vertices[STRIDE * index + VECTOR_COLUMN] = z

    # a Delaunay triangulation of the whole point set, kept where the
    # triangle's centroid is in the annulus
    from scipy.spatial import Delaunay
    pts = numpy.array([(x, y) for (x, y, _z) in rows])
    tri = Delaunay(pts)
    triangles = []
    for simplex in tri.simplices:
        cx, cy = pts[simplex].mean(axis=0)
        r = max(abs(cx), abs(cy))
        if INNER_M < r < OUTER_M:
            triangles.append(tuple(int(v) for v in simplex))
    assert triangles

    edges = [(i, (i + 1) % n_inner) for i in range(n_inner)]
    edges += [(n_inner + i, n_inner + (i + 1) % n_outer)
              for i in range(n_outer)]

    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    _write_patch_osm(patch_dir / "TWIN_auto.patch.osm", inner, outer)
    poly = tmp_path / "twin.poly"
    _write_poly(poly, edges)
    monkeypatch.setattr(MESH.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(MESH.FNAMES, "input_poly_file",
                        lambda tile: str(poly))
    return (_Tile(), vertices, triangles, set(range(ring_count)),
            pts, ring_count)


def _expected(x, y):
    """The bank's own altitude at a FLANK station: linear in the plan
    distance beyond the design ring."""
    return RING_Z - SLOPE * (max(abs(x), abs(y)) - INNER_M)


class TestTheEngineBlendsTheBank:
    def test_every_free_vertex_in_the_annulus_takes_the_linear_value(
            self, annulus):
        (tile, vertices, triangles, patch_valued, pts, ring_count) = annulus
        blend = MESH.bank_annulus_blend_values(
            tile, vertices, triangles, patch_valued)
        assert blend, "the annulus was not identified at all"
        free = {v for t in triangles for v in t if v >= ring_count}
        missed = sorted(free - set(blend))
        assert not missed, f"{len(missed)} annulus vertex(es) unblended"
        worst = 0.0
        n_flank = 0
        for index, z in blend.items():
            x, y = pts[index]
            # the FLANK: the nearest point of the design ring is on a
            # straight side, so the linear value is analytic.  (In a
            # corner fan the law is still the formula, but its plan
            # distance runs diagonally and no closed form is asserted.)
            if min(abs(x), abs(y)) > INNER_M:
                continue
            worst = max(worst, abs(z - _expected(x, y)))
            n_flank += 1
        assert n_flank > 100, n_flank        # the assertion is not vacuous
        assert worst <= 0.05, worst

    def test_no_triangle_is_steeper_than_the_ring_to_foot_slope(
            self, annulus):
        (tile, vertices, triangles, patch_valued, pts, _n) = annulus
        blend = MESH.bank_annulus_blend_values(
            tile, vertices, triangles, patch_valued)
        for index, z in blend.items():
            vertices[STRIDE * index + VECTOR_COLUMN] = z
        worst = 0.0
        for (a, b, c) in triangles:
            for (u, v) in ((a, b), (b, c), (c, a)):
                run = float(numpy.hypot(*(pts[u] - pts[v])))
                if run < 1.0e-6:
                    continue
                rise = abs(vertices[STRIDE * u + VECTOR_COLUMN]
                           - vertices[STRIDE * v + VECTOR_COLUMN])
                worst = max(worst, rise / run)
        assert worst <= SLOPE * 1.02, worst

    def test_a_tile_with_no_bank_foot_ring_is_a_no_op(self, annulus, tmp_path,
                                                      monkeypatch):
        """H12: a v1 patch, a manual patch or no patch at all has no
        ``bank_foot`` way, so the blend writes nothing and the harmonic
        extension runs exactly as it does today."""
        (tile, vertices, triangles, patch_valued, _pts, _n) = annulus
        empty = tmp_path / "nobank"
        empty.mkdir()
        monkeypatch.setattr(MESH.FNAMES, "patch_dir",
                            lambda lat, lon: str(empty))
        assert MESH.bank_annulus_blend_values(
            tile, vertices, triangles, patch_valued) == {}

    def test_the_annulus_excludes_the_design_coverage(self, annulus):
        """The blend never touches a vertex inside the patch: the annulus
        is ``banked − design coverage`` and nothing else."""
        (tile, vertices, triangles, patch_valued, pts, _n) = annulus
        blend = MESH.bank_annulus_blend_values(
            tile, vertices, triangles, patch_valued)
        for index in blend:
            x, y = pts[index]
            assert max(abs(x), abs(y)) > INNER_M - 1.0e-6, (x, y)
        assert not (set(blend) & set(patch_valued))


# ── THE MESH MUST HAVE VERTICES TO CARRY THE BLEND ─────────────────────
# (owner RULINGS 2026-09-09x; spec §13.8)
#
# Round 1 measured the blend EXACT (4.7 mm over 11,153 annulus vertices at
# HECA) and useless: only 40 of those vertices were FREE, so the bank was
# the ring-to-foot triangulation.  The ruling's answer is a Triangle
# REGION with a maximum triangle area of ``(w / bank_triangle_divisions)
# ** 2``.  These are that construction's twin.

class TestTheAnnulusIsARegionWithAMaximumArea:
    def test_the_area_is_the_local_bank_width_over_the_law_s_divisions(
            self, annulus):
        """The sizing law, in metres: a 60 m bank at 3 divisions asks for
        20 m triangles, i.e. 400 m2."""
        (tile, _v, _t, _pv, pts, _n) = annulus
        from auto_patch_v2.law import tables as law_tables
        divisions = float(law_tables.load_default()
                          .tables.emit.design.bank_triangle_divisions)

        # one seed at the middle of each flank of the annulus
        mid = INNER_M + BANK_M / 2.0
        seeds_m = [(mid, 0.0), (-mid, 0.0), (0.0, mid), (0.0, -mid)]
        seeds = []
        for (x_m, y_m) in seeds_m:
            lat, lon = _to_ll(x_m, y_m)
            seeds.append((lon - LON, lat - LAT))

        areas = MESH.bank_annulus_region_areas(tile, seeds)
        assert set(areas) == {0, 1, 2, 3}, areas

        # .poly units are lon x lat degrees; back to m2
        to_m2 = SCALX * DEG * DEG
        expected = (BANK_M / divisions) ** 2
        # TIGHT (2 %), and deliberately so: this is the FRAME assertion.
        # ``_bank_rings_from_patches`` already returns the isotropic frame
        # ``(x * scalx, y)``, so scaling it a second time reads a bank
        # 1/scalx too narrow across and passes a 10 % bar at this latitude
        # (measured: 51.7 m for a 60 m bank, 297 m2 for 400).
        for index, area in areas.items():
            assert abs(area * to_m2 - expected) <= 0.02 * expected, (
                index, area * to_m2, expected)

    def test_a_seed_outside_the_annulus_is_not_sized(self, annulus):
        """Only the bank gets an area: a seed inside the design coverage
        and one out beyond the foot are both left unconstrained."""
        (tile, _v, _t, _pv, _pts, _n) = annulus
        seeds = []
        for (x_m, y_m) in ((0.0, 0.0),                      # inside the patch
                           (OUTER_M + 50.0, 0.0)):          # beyond the foot
            lat, lon = _to_ll(x_m, y_m)
            seeds.append((lon - LON, lat - LAT))
        assert MESH.bank_annulus_region_areas(tile, seeds) == {}

    def test_a_tile_with_no_bank_foot_ring_sizes_nothing(
            self, annulus, tmp_path, monkeypatch):
        (tile, _v, _t, _pv, _pts, _n) = annulus
        empty = tmp_path / "nobank_regions"
        empty.mkdir()
        monkeypatch.setattr(MESH.FNAMES, "patch_dir",
                            lambda lat, lon: str(empty))
        lat, lon = _to_ll(INNER_M + BANK_M / 2.0, 0.0)
        assert MESH.bank_annulus_region_areas(
            tile, [(lon - LON, lat - LAT)]) == {}

    def test_the_poly_writer_writes_the_fifth_field_only_where_sized(
            self, tmp_path):
        """Every other region record stays byte-identical: the area is a
        fifth field on the sized seed alone."""
        import O4_Vector_Utils as VECT

        vector_map = VECT.Vector_Map()
        vector_map.seeds["INTERP_ALT"] = [numpy.array([0.25, 0.25]),
                                          numpy.array([0.75, 0.75])]
        vector_map.seed_areas[("INTERP_ALT", 1)] = 4.0e-8
        path = tmp_path / "regions.poly"
        vector_map.write_poly_file(str(path))
        records = [line.split() for line in path.read_text().splitlines()
                   if line.strip()][-2:]
        assert len(records[0]) == 4, records[0]      # unsized: unchanged
        assert len(records[1]) == 5, records[1]
        assert float(records[1][4]) == pytest.approx(4.0e-8, rel=1e-9)

    def test_the_regional_area_flag_rides_with_the_attribute_flag(self):
        """``-a`` is read from the ``.poly`` only when NOT refining; with
        ``-r`` Triangle4XP demands an ``.area`` file and exits 1."""
        source = (SRC / "O4_Mesh_Utils.py").read_text()
        assert 'regional_areas = "a" if do_refine == "A" else ""' in source
        assert '"-pq" + "{:.9g}".format(tile.min_angle) + do_refine + ' \
               'regional_areas +' in source


# ── THE END-TO-END TWIN: DOES TRIANGLE ACTUALLY REFINE THE ANNULUS? ────
#
# REFUTED AS RULED (lane v2bankblend round 2, measured 2026-09-09).  The
# ruling calls the region area "a standard Triangle facility".  It is —
# in Jonathan Shewchuk's ``triangle.c``, whose ``testtriangle`` compares a
# triangle's area against ``areabound(*testtri)`` at line 7336.  THIS FORK
# HAS NO SUCH LINE: ``Utils/src/Triangle4XP.c`` rewrote ``testtriangle``
# around the DEM-curvature criterion and dropped the area test with it.
# ``grep areabound Triangle4XP.c`` returns only the macro, the propagation
# copies and a debug printf — the value is stored, spread by
# ``regionplague`` and never read by any quality test.  A SECOND,
# independent blocker sits on top of it: ``testtriangle`` opens with
# ``if (attribute >= 8) return;`` ("Refinement in INTERP_ALT tris is
# useless"), and the bank annulus is INTERP_ALT.
#
# MEASURED on this very fixture (30 m band, 3 divisions, max area 9.4e-9
# deg2, ~100 m2): the SHIPPED Utils/mac/Triangle4XP takes 184 input
# vertices to 184 output vertices — zero Steiner points, byte-identical
# with and without ``-a``, at attribute 8 and at attribute 0 alike, while
# the annulus triangles are ~150 m2.  Triangle prints "Spreading regional
# attributes and area constraints", so the flag IS parsed and the area IS
# read; nothing consumes it.
#
# THE COUNTERFACTUAL, also measured: Triangle4XP.c with the stock area
# test restored ahead of the INTERP_ALT exemption (nine lines) takes the
# same fixture to 314 vertices — 130 free vertices inside the 30 m band —
# and the ruled blend then rides on a maximum triangle slope of 0.333,
# exactly the ring-to-foot slope, 0 % over slope + 0.02.  With no region
# carrying an area the patched binary is identical to the shipped one, so
# the change is inert everywhere else.
#
# So the Python side below is right and complete, and the mechanism is
# blocked in the VENDORED BINARY.  This test is the tripwire: it is
# ``xfail(strict=True)``, so the day Triangle4XP is rebuilt it FAILS as
# unexpectedly-passing and this whole comment gets deleted.
BANK_REGION_MIN_FREE_VERTICES = 40      # for the 30 m band below


@pytest.mark.xfail(strict=True, reason=(
    "the vendored Triangle4XP dropped the stock regional-area quality test "
    "(triangle.c:7336) and exempts attribute >= 8 from refinement, so -a is "
    "inert: 184 -> 184 vertices, measured — RULINGS 2026-09-09x, lane "
    "v2bankblend round 2"))
def test_triangle_puts_vertices_inside_a_region_that_asks_for_them(tmp_path):
    """THE BAR (RULINGS 2026-09-09x): a bank annulus written as a region
    with ``max_area = (w / bank_triangle_divisions) ** 2`` comes back with
    interior vertices to carry the blend."""
    import subprocess

    from auto_patch_v2.law import tables as law_tables
    divisions = float(law_tables.load_default()
                      .tables.emit.design.bank_triangle_divisions)

    inner_m, bank_m, step_m = 100.0, 30.0, 10.0
    inner = _square(inner_m, step_m)
    outer = _square(inner_m + bank_m, step_m)

    def rel(x_m, y_m):
        lat, lon = _to_ll(x_m, y_m)
        return (lon - LON + 0.5, lat - LAT + 0.5)

    pts = [rel(x, y) for (x, y) in inner] + [rel(x, y) for (x, y) in outer]
    zs = [RING_Z] * len(inner) + [FOOT_Z] * len(outer)
    n_in, n_out = len(inner), len(outer)

    base = tmp_path / "annulus"
    with open(str(base) + ".node", "w") as handle:
        handle.write(f"{len(pts)} 2 1 0\n")
        for index, ((x, y), z) in enumerate(zip(pts, zs), start=1):
            handle.write(f"{index} {x:.9f} {y:.9f} {z:.9f}\n")

    marker = 8                                   # INTERP_ALT, as the tile
    edges = [(i, (i + 1) % n_in) for i in range(n_in)]
    edges += [(n_in + i, n_in + (i + 1) % n_out) for i in range(n_out)]
    scalx = float(numpy.cos((LAT + 0.5) * numpy.pi / 180.0))
    max_area = ((bank_m / divisions) / DEG) ** 2 / scalx
    seed_x, seed_y = rel(inner_m + bank_m / 2.0, 0.0)
    with open(str(base) + ".poly", "w") as handle:
        handle.write("0 2 1 0\n\n")
        handle.write(f"{len(edges)} 1\n")
        for k, (a, b) in enumerate(edges, start=1):
            handle.write(f"{k} {a + 1} {b + 1} {marker}\n")
        handle.write("\n0\n\n1\n")
        handle.write(f"1 {seed_x:.15f} {seed_y:.15f} {marker} "
                     f"{max_area:.15g}\n")

    alt = tmp_path / "alt.raw"
    numpy.zeros((101, 101), dtype=numpy.float32).tofile(str(alt))
    weight = tmp_path / "weight.raw"
    numpy.ones((1001, 1001), dtype=numpy.float32).tofile(str(weight))

    cmd = [MESH.Triangle4XP_cmd.strip(), "-pq30AauYBQS500000",
           "{:.9g}".format(DEG * scalx), "{:.9g}".format(DEG),
           "101", "101", "0", "0", "1", "1", "-32768", "10",
           str(alt), str(weight), str(base) + ".poly"]
    if not os.path.isfile(cmd[0]):
        pytest.skip(f"no Triangle4XP at {cmd[0]}")
    subprocess.run(cmd, check=True, capture_output=True, cwd=str(tmp_path))

    out_nodes = Path(str(base) + ".1.node").read_text().splitlines()
    produced = int(out_nodes[0].split()[0])
    free = produced - len(pts)
    assert free >= BANK_REGION_MIN_FREE_VERTICES, (
        f"Triangle put {free} vertex(es) inside a {bank_m:.0f} m annulus "
        f"whose region asked for {max_area:.3g} deg2 triangles "
        f"({produced} out of {len(pts)} in)")
