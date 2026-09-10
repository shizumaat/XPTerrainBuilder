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
# RULED AND LANDED (RULINGS 2026-09-09aa; lane v2bankblend round 3).  The
# ruling of 09x called the region area "a standard Triangle facility".  It
# is — in Jonathan Shewchuk's ``triangle.c``, whose ``testtriangle``
# compares a triangle's area against ``areabound(*testtri)`` at line 7336.
# THE FORK HAD NO SUCH LINE: ``Utils/src/Triangle4XP.c`` rewrote
# ``testtriangle`` around the DEM-curvature criterion and dropped the area
# test with it, so ``-a`` and the ``.poly``'s fifth region field were
# INERT (measured on this fixture: 184 input vertices -> 184 output
# vertices, byte-identical with and without ``-a``, at attribute 8 and at
# attribute 0 alike, while the annulus triangles were ~150 m2).  A second
# blocker sat on top of it: ``testtriangle`` opens with
# ``if (attribute >= 8) return;`` ("Refinement in INTERP_ALT tris is
# useless"), and the bank annulus is INTERP_ALT.
#
# 09aa RULED the vendored SOURCE patched: the stock area test is restored
# AHEAD of the INTERP_ALT exemption and ``Utils/mac/Triangle4XP`` is
# rebuilt from it (``cc -O2 -arch arm64 -arch x86_64``, universal, as the
# shipped binary is) and committed with the source.  This fixture now
# reads 306 vertices — 122 free vertices inside the 30 m band — and the
# ruled blend rides on a maximum triangle slope of 0.333, exactly the
# ring-to-foot slope, 0 % over slope + 0.02.  With no region carrying an
# area the patched binary is identical to the shipped one, so the change
# is inert on every tile that has no bank.
#
# THE WIN/LIN BINARIES ARE NOT REBUILT HERE — the release CI owns them
# (docs/DEFERRED_VERIFICATION.md).  Until it does, the fifth ``.poly``
# field is inert there, so this twin is a HARD twin on macOS ONLY and
# skips elsewhere with that reason.
BANK_REGION_MIN_FREE_VERTICES = 40      # for the 30 m band below

# The identity of the binary the twin above is measuring.  It is recorded
# HERE so that a later rebuild that forgets the 09aa patch (or a merge
# that restores the vendored binary) fails loudly instead of silently
# putting the bank back on the ring-to-foot triangulation.  Update it in
# the SAME commit as any deliberate Triangle4XP rebuild.
TRIANGLE4XP_MAC_SHA1 = "7ca193114522035fb0449432431b14db02fe37e1"


@pytest.mark.skipif(sys.platform != "darwin", reason=(
    "only Utils/mac/Triangle4XP carries the 09aa area-test patch; the "
    "win/lin binaries are rebuilt by the release CI (owed, recorded in "
    "docs/DEFERRED_VERIFICATION.md) and the fifth .poly field is inert "
    "there"))
def test_the_shipped_mac_triangle4xp_is_the_patched_binary():
    """The mac binary in the tree IS the one built from the patched
    ``Utils/src/Triangle4XP.c`` (RULINGS 2026-09-09aa)."""
    import hashlib

    binary = Path(MESH.Triangle4XP_cmd.strip())
    if not binary.is_file():
        pytest.skip(f"no Triangle4XP at {binary}")
    digest = hashlib.sha1(binary.read_bytes()).hexdigest()
    assert digest == TRIANGLE4XP_MAC_SHA1, (
        f"{binary} is sha1 {digest}, not the 09aa-patched binary "
        f"{TRIANGLE4XP_MAC_SHA1}: rebuild it from Utils/src/Triangle4XP.c "
        f"(cc -O2 -arch arm64 -arch x86_64 ... -lm) and record the new "
        f"sha1 here in the same commit")


@pytest.mark.skipif(sys.platform != "darwin", reason=(
    "the 09aa area-test patch is built into Utils/mac/Triangle4XP only; "
    "the win/lin binaries are the release CI's (docs/"
    "DEFERRED_VERIFICATION.md) and the fifth .poly field is inert there"))
def test_triangle_puts_vertices_inside_a_region_that_asks_for_them(tmp_path):
    """THE BAR (RULINGS 2026-09-09x, met by 2026-09-09aa): a bank annulus written as a region
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


# ── THE PINCHED ANNULUS ───────────────────────────────────────────────
# (owner RULINGS 2026-09-09ab; spec §13.8)
#
# 09t's field divided by ``d_in + d_out`` — the distance to the nearest
# ring plus the distance to the nearest FOOT, which in a pinch are two
# DIFFERENT ring stations.  Measured on the HECA transect: three stations
# whose nearest annulus boundary was the design ring at 0.5-7 m while
# their foot stood ~57 m away read 0.459 / 0.533 / 0.533 against the 0.35
# bar — steep by construction of the field.
#
# THIS FIXTURE IS THAT SITE.  Two design bodies at DIFFERENT altitudes
# stand 4 m apart; their banks merge, so the 4 m gap between them is
# annulus with NO foot in it and a foot 57 m away outside.  A vertex in
# the gap took the near body's ring altitude and the far body's foot
# altitude — 20 m of difference over 57 m of ratio, spent in the first
# half metre.  The ruled field runs along the RING'S NORMAL, so both ends
# of the ratio belong to ONE ray and the slope out of the ring is the
# ring-to-foot slope wherever the vertex stands.

PINCH_SLOPE = 1.0 / 3.0             # the 1:3 design bank
PINCH_FOOT_M = 57.0                 # the daylight foot's distance
PINCH_A_Z = 10.0                    # body A's design altitude
PINCH_B_Z = 30.0                    # body B's, 20 m above it
PINCH_GAP_M = 4.0                   # the band where the annulus pinches


def _rect(x0, y0, x1, y1, step_m):
    """A closed rectangle ring sampled every ``step_m``, in metres."""
    pts = []
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1),
                             (x1, y1, x0, y1), (x0, y1, x0, y0)):
        n = max(1, int(round(numpy.hypot(bx - ax, by - ay) / step_m)))
        for k in range(n):
            pts.append((ax + (bx - ax) * k / n, ay + (by - ay) * k / n))
    return pts


def _write_rings_osm(path, rings):
    """``rings`` is a list of ``(points, per-point z, tags)``."""
    lines = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<osm version='0.6' generator='twin'>"]
    nid, wid = 0, -10000
    ways = []
    for (pts, zs, _tags) in rings:
        ids = []
        for (x, y), z in zip(pts, zs):
            nid -= 1
            lat, lon = _to_ll(x, y)
            lines.append(f"  <node id='{nid}' action='modify' visible='true' "
                         f"lat='{lat:.11f}' lon='{lon:.11f}'>")
            lines.append(f"    <tag k='alt_abs' v='{z:.3f}' />")
            lines.append("  </node>")
            ids.append(nid)
        ways.append(ids)
    for ids, (_pts, _zs, tags) in zip(ways, rings):
        wid -= 1
        lines.append(f"  <way id='{wid}' action='modify' visible='true'>")
        for v in ids + [ids[0]]:
            lines.append(f"    <nd ref='{v}' />")
        for k, val in tags:
            lines.append(f"    <tag k='{k}' v='{val}' />")
        lines.append("  </way>")
    lines.append("</osm>")
    path.write_text("\n".join(lines) + "\n")


@pytest.fixture()
def pinched(tmp_path, monkeypatch):
    from shapely import geometry, ops

    body_a = _rect(-100.0, -100.0, 100.0, 100.0, 10.0)
    bx0 = 100.0 + PINCH_GAP_M
    body_b = _rect(bx0, -20.0, bx0 + 40.0, 20.0, 5.0)
    poly_a = geometry.Polygon(body_a)
    poly_b = geometry.Polygon(body_b)
    coverage = ops.unary_union([poly_a, poly_b])
    foot_poly = coverage.buffer(PINCH_FOOT_M, quad_segs=8)
    # DENSIFIED: the foot is a CONSTRAINED EDGE carrying z at both ends,
    # so a 200 m edge across a daylight jump would mean something the
    # daylight walk never authors (RULINGS 2026-09-09g (4))
    foot = list(foot_poly.exterior.segmentize(5.0).coords)[:-1]

    # the foot IS the DEM: each foot station 1:3 below ITS OWN body
    def foot_z(x, y):
        da = poly_a.exterior.distance(geometry.Point(x, y))
        db = poly_b.exterior.distance(geometry.Point(x, y))
        z_body = PINCH_A_Z if da <= db else PINCH_B_Z
        return z_body - min(da, db) * PINCH_SLOPE

    rings = [
        (body_a, [PINCH_A_Z] * len(body_a),
         [("o4_feature", "graded_surface"), ("role", "apron")]),
        (body_b, [PINCH_B_Z] * len(body_b),
         [("o4_feature", "graded_surface"), ("role", "apron")]),
        (foot, [foot_z(x, y) for (x, y) in foot],
         [("o4_feature", "bank_foot"), ("ref", "bank:0")]),
    ]

    rows, edges, base = [], [], 0
    for (pts, zs, _t) in rings:
        rows.extend((x, y, z) for (x, y), z in zip(pts, zs))
        edges.extend((base + i, base + (i + 1) % len(pts))
                     for i in range(len(pts)))
        base += len(pts)
    ring_count = base

    annulus = foot_poly.difference(coverage)
    free_xy = []
    minx, miny, maxx, maxy = annulus.bounds
    grid = [(x, y)
            for x in numpy.arange(minx, maxx, 3.0)
            for y in numpy.arange(miny, maxy, 3.0)]
    grid += [(x, y)                                  # the pinch, sampled fine
             for x in numpy.arange(98.0, 108.0, 0.5)
             for y in numpy.arange(-24.0, 24.0, 1.0)]
    rng = numpy.random.default_rng(20260909)
    for (x, y) in grid:
        x = float(x) + float(rng.uniform(-0.05, 0.05))
        y = float(y) + float(rng.uniform(-0.05, 0.05))
        pnt = geometry.Point(x, y)
        if not annulus.contains(pnt):
            continue
        if annulus.exterior.distance(pnt) < 0.25:
            continue
        if any(h.distance(pnt) < 0.25 for h in annulus.interiors):
            continue
        free_xy.append((x, y))
    assert len(free_xy) > 2000, len(free_xy)
    rows += [(x, y, DEM_SENTINEL) for (x, y) in free_xy]

    vertices = numpy.zeros(STRIDE * len(rows))
    for index, (x, y, z) in enumerate(rows):
        lat, lon = _to_ll(x, y)
        vertices[STRIDE * index] = lon - LON
        vertices[STRIDE * index + 1] = lat - LAT
        vertices[STRIDE * index + 2] = z
        vertices[STRIDE * index + VECTOR_COLUMN] = z

    from scipy.spatial import Delaunay
    pts = numpy.array([(x, y) for (x, y, _z) in rows])
    tri = Delaunay(pts)
    centroids = pts[tri.simplices].mean(axis=1)
    import shapely as _sh
    keep = _sh.contains_xy(annulus, centroids[:, 0], centroids[:, 1])
    triangles = [tuple(int(v) for v in s) for s in tri.simplices[keep]]
    assert triangles

    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    _write_rings_osm(patch_dir / "PNCH_auto.patch.osm", rings)
    poly = tmp_path / "pinched.poly"
    _write_poly(poly, edges)
    monkeypatch.setattr(MESH.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(MESH.FNAMES, "input_poly_file",
                        lambda tile: str(poly))
    return (_Tile(), vertices, triangles, set(range(ring_count)), pts,
            ring_count, poly_a, poly_b,
            numpy.asarray(foot, float), numpy.asarray(rings[2][1], float))




def _rays(pts, indices, poly_a, poly_b, foot_xy, foot_z):
    """THE RULED RAY at each vertex, computed independently here:
    ``(d, z_ring(p), D(p), z_foot(p))`` — the nearest DESIGN ring
    segment's projection ``p``, the first FOOT EDGE crossing of THAT
    SEGMENT'S OUTWARD NORMAL through it, and that edge's own carried
    altitude interpolated at the crossing."""
    # the design ring's segments, each with the body altitude it carries
    rax, ray_, rbx, rby, rz = [], [], [], [], []
    for poly, z in ((poly_a, PINCH_A_Z), (poly_b, PINCH_B_Z)):
        cs = list(poly.exterior.coords)
        for k in range(len(cs) - 1):
            rax.append(cs[k][0])
            ray_.append(cs[k][1])
            rbx.append(cs[k + 1][0])
            rby.append(cs[k + 1][1])
            rz.append(z)
    rax = numpy.asarray(rax); ray_ = numpy.asarray(ray_)
    rbx = numpy.asarray(rbx); rby = numpy.asarray(rby)
    rz = numpy.asarray(rz)
    rdx, rdy = rbx - rax, rby - ray_
    rlen2 = rdx * rdx + rdy * rdy

    fax, fay = foot_xy[:, 0], foot_xy[:, 1]
    fbx, fby = numpy.roll(fax, -1), numpy.roll(fay, -1)
    fza, fzb = foot_z, numpy.roll(foot_z, -1)
    fsx, fsy = fbx - fax, fby - fay

    out = {}
    for index in indices:
        x, y = float(pts[index][0]), float(pts[index][1])
        t = numpy.clip(((x - rax) * rdx + (y - ray_) * rdy) / rlen2, 0.0, 1.0)
        qx, qy = rax + t * rdx, ray_ + t * rdy
        dd = numpy.hypot(x - qx, y - qy)
        d = float(dd.min())
        if d <= 0.0:
            continue
        # A CORNER FAN TIES: a vertex off a ring corner projects onto the
        # SAME point from both adjacent segments, whose normals are 90
        # apart.  Which station carries it is genuinely ambiguous, so
        # every tied candidate is returned and the assertions take the
        # one the engine chose.
        candidates = []
        for k in numpy.flatnonzero(dd <= d + 1.0e-9).tolist():
            px, py = float(qx[k]), float(qy[k])
            nlen = float(numpy.hypot(rdx[k], rdy[k]))
            ux, uy = -rdy[k] / nlen, rdx[k] / nlen
            if ux * (x - px) + uy * (y - py) < 0.0:
                ux, uy = -ux, -uy
            cross = ux * fsy - uy * fsx
            with numpy.errstate(divide="ignore", invalid="ignore"):
                cx, cy = fax - px, fay - py
                s_ray = (cx * fsy - cy * fsx) / cross
                t_seg = (cx * uy - cy * ux) / cross
            ok = ((cross != 0.0) & (s_ray > 0.0) & (t_seg >= 0.0)
                  & (t_seg <= 1.0))
            if not ok.any():
                continue
            m = int(numpy.flatnonzero(ok)[numpy.argmin(s_ray[ok])])
            candidates.append((d, float(rz[k]), float(s_ray[m]),
                               float(fza[m] + (fzb[m] - fza[m]) * t_seg[m])))
        if candidates:
            out[index] = candidates
    return out


class TestThePinchedAnnulusRunsAlongTheRingsNormal:
    def test_every_vertex_takes_the_ruled_value_along_its_own_normal(
            self, pinched):
        """THE LAW (09ab), asserted against an independent shapely
        ray-cast: ``z = z_ring(p) + (z_foot(p) - z_ring(p)) *
        min(1, d / D(p))``."""
        (tile, vertices, triangles, patch_valued, pts, _n,
         poly_a, poly_b, foot_xy, foot_z) = pinched
        blend = MESH.bank_annulus_blend_values(
            tile, vertices, triangles, patch_valued)
        assert blend, "the pinched annulus was not identified at all"
        rays = _rays(pts, sorted(blend), poly_a, poly_b, foot_xy, foot_z)
        assert len(rays) > 2000, len(rays)
        worst, where = 0.0, None
        for index, cands in rays.items():
            miss = min(abs(blend[index]
                           - (z_ring + (z_foot - z_ring) * min(1.0, d / big_d)))
                       for (d, z_ring, big_d, z_foot) in cands)
            if miss > worst:
                worst, where = miss, pts[index]
        assert worst <= 0.05, (worst, where)

    def test_no_vertex_is_steeper_than_its_own_ring_to_foot_slope(
            self, pinched):
        """THE BAR: the slope ALONG THE NORMAL out of the design ring is
        the ring-to-foot slope of that very ray — never steeper, however
        narrow the band is where the vertex stands."""
        (tile, vertices, triangles, patch_valued, pts, _n,
         poly_a, poly_b, foot_xy, foot_z) = pinched
        blend = MESH.bank_annulus_blend_values(
            tile, vertices, triangles, patch_valued)
        rays = _rays(pts, sorted(blend), poly_a, poly_b, foot_xy, foot_z)
        worst, where = 0.0, None
        for index, cands in rays.items():
            ratios = [abs(blend[index] - z_ring) / d
                      / (abs(z_foot - z_ring) / big_d)
                      for (d, z_ring, big_d, z_foot) in cands
                      if z_foot != z_ring]
            if ratios and min(ratios) > worst:
                worst, where = min(ratios), pts[index]
        assert worst <= 1.02, (worst, where)

    def test_the_pinch_itself_is_sampled(self, pinched):
        """The 4 m band between the two bodies — annulus with NO foot in
        it and a foot tens of metres away — is where 09t's field paired a
        near ring with a far, unrelated foot."""
        (tile, vertices, triangles, patch_valued, pts, _n,
         poly_a, poly_b, foot_xy, foot_z) = pinched
        blend = MESH.bank_annulus_blend_values(
            tile, vertices, triangles, patch_valued)
        gap = [i for i in blend
               if 100.0 < pts[i][0] < 100.0 + PINCH_GAP_M
               and abs(pts[i][1]) < 20.0]
        assert len(gap) > 100, len(gap)
        rays = _rays(pts, sorted(gap), poly_a, poly_b, foot_xy, foot_z)
        assert len(rays) > 100, len(rays)
        for index, cands in rays.items():
            ok = [abs(blend[index] - z_ring) / d
                  <= abs(z_foot - z_ring) / big_d * 1.02 + 1.0e-9
                  for (d, z_ring, big_d, z_foot) in cands]
            assert any(ok), (pts[index], blend[index], cands)

    def test_the_nearest_boundary_field_fails_this_fixture(self, pinched):
        """THE TRIPWIRE: 09t's own formula, computed here on the same
        geometry, breaks the bar the twin above holds — so that twin
        measures the ruled change and not the fixture."""
        (tile, vertices, triangles, patch_valued, pts, ring_count,
         poly_a, poly_b, foot_xy, foot_z) = pinched
        from shapely import geometry, ops
        cov = ops.unary_union([poly_a, poly_b])
        foot = cov.buffer(PINCH_FOOT_M, quad_segs=8).exterior
        free = sorted({v for t in triangles for v in t if v >= ring_count})
        rays = _rays(pts, free, poly_a, poly_b, foot_xy, foot_z)
        worst = 0.0
        for index, cands in rays.items():
            (d_in, z_in, big_d, z_foot) = cands[0]
            v = geometry.Point(float(pts[index][0]), float(pts[index][1]))
            q = ops.nearest_points(foot, v)[0]
            d_out = v.distance(q)
            qa, qb = poly_a.exterior.distance(q), poly_b.exterior.distance(q)
            z_out = ((PINCH_A_Z if qa <= qb else PINCH_B_Z)
                     - min(qa, qb) * PINCH_SLOPE)
            z = z_in + (z_out - z_in) * d_in / (d_in + d_out)
            bound = abs(z_foot - z_in) / big_d
            if bound > 0.0:
                worst = max(worst, abs(z - z_in) / d_in / bound)
        assert worst > 1.5, worst
