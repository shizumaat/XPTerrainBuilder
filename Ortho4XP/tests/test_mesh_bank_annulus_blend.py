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
