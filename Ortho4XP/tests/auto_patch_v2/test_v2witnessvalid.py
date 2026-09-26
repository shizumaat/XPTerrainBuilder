"""Lane ``frameentry`` twins for spec §51 — PACK GEOMETRY IS VALID WHERE
IT ENTERS THE FRAME, AND A UNION OF PACK GEOMETRY NEVER ABORTS A TILE
(RULINGS 2026-09-18d (2) GEML; the TNCM capture of lane
``packreadprofile``).

T1  ``enter`` repairs the GEML free-hole ring (the polygon that aborted
    tile +35-003) to a valid polygonal 0.2736 m2 — NOT the 0.0 m2 the
    retired ``door_wells._union_below`` docstring claimed, which was an
    artefact of that function's one-level ``get_parts``.
T2  the TNCM offender: VALID inputs that GEOS's exact overlay still
    refuses; ``union`` returns and counts the rung.
T3  a footprint that repairs to empty is not a witness, and the drop is
    NAMED.
T4  PLATFORM TWIN: coordinates perturbed by +/- 1 ulp give byte-identical
    WKB out of ``enter``.
T5  ``q = 0`` skips the snap and NOTHING else.
T6  the partition cache refuses a v2 payload, and a ``frame_entry``
    source change moves the fingerprint.
T7  every ``enter`` output over a registered capture's placed footprints
    is valid.
G1  AST twin: no ``affine_transform`` / ``affinity.rotate`` in
    ``airport/`` or ``planar/`` outside ``frame_entry.py``.
G2  AST twin: the functions the §51 (4) census names UNION hold no bare
    ``unary_union`` / ``union_all``.
G3  ``enter`` is IDEMPOTENT — the convergence guard: a second pass
    changes nothing, so no consumer can need a belt.
"""
from __future__ import annotations

import ast
import os
import pathlib

import numpy as np
import pytest
import shapely
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport import frame_entry as fe
from auto_patch_v2.airport import obj8, partition_cache

from test_v2doorramp import GEML_FREE_HOLE_WKT

Q = 0.001                      # emit.identity.input_quantum_m, §46 (4)
_SRC = pathlib.Path(fe.__file__).resolve().parent.parent          # auto_patch_v2/
_HERE = pathlib.Path(__file__).resolve().parent


# ── T1 ────────────────────────────────────────────────────────────────────
def test_t1_geml_free_hole_enters_the_frame_valid():
    g = shapely.from_wkt(GEML_FREE_HOLE_WKT)
    assert not g.is_valid                                # what the affine minted
    with pytest.raises(GEOSException, match="unable to assign free hole"):
        unary_union([g])
    out = fe.enter([g], fe.IDENTITY, Q)
    assert out.shape == (1,)
    r = out[0]
    assert r is not None and r.is_valid
    assert r.geom_type in ("Polygon", "MultiPolygon")     # (d): no lines survive
    # the number the spec corrects: 0.2736 m2, not the retired docstring's 0.0
    assert r.area == pytest.approx(0.2736, abs=1e-3)
    assert unary_union([r]).is_valid                      # the consumer is safe now


def test_t1b_the_retired_union_below_claim_was_wrong():
    """``_union_below``'s 0.0 m2 docstring was a one-level ``get_parts``
    dropping ``make_valid``'s nested MultiPolygon — the ring carries area."""
    g = shapely.from_wkt(GEML_FREE_HOLE_WKT)
    assert shapely.make_valid(g).is_valid
    assert fe.enter([g], fe.IDENTITY, 0.0)[0].area > 0.27


# ── T2 — the TNCM offender ────────────────────────────────────────────────
_TNCM_WKB = _HERE / "data" / "tncm_wall_corridor_caps.wkb"


@pytest.mark.skipif(not _TNCM_WKB.is_file(),
                    reason="the TNCM offender dump is not in the tree")
def test_t2_tncm_valid_inputs_that_geos_refuses():
    """``wall_corridors._bands_of``'s ``caps``, verbatim from the capture
    that aborted at ``side location conflict at -557.635 254.363``.
    ``wall_geometry._plan_polys`` had ALREADY filtered these on
    ``is_valid & area`` — every operand is valid and the exact overlay
    still throws, which is why Law A alone is not enough."""
    caps = list(shapely.get_parts(shapely.from_wkb(_TNCM_WKB.read_bytes())))
    assert caps
    assert shapely.is_valid(np.array(caps, dtype=object)).all(), "inputs were VALID"
    with pytest.raises(GEOSException):
        unary_union(caps)
    fe.reset_rung_counts()
    u = fe.union(caps, "twin.tncm")
    assert u is not None and not u.is_empty
    rungs = fe.rung_counts()["twin.tncm"]
    assert rungs[0] >= 1, rungs                       # the grid rung carried it
    grid = shapely.union_all(caps, grid_size=1e-6)
    assert u.area == pytest.approx(grid.area, abs=1e-6)
    fe.reset_rung_counts()


def test_t2b_the_ladder_returns_when_the_exact_overlay_refuses():
    """The ladder itself, on an input the exact overlay refuses — the
    guarantee T2 pins on real geometry, held here with no capture."""
    fe.reset_rung_counts()
    bad = shapely.from_wkt(GEML_FREE_HOLE_WKT)        # raises under unary_union
    with pytest.raises(GEOSException):
        unary_union([bad])
    u = fe.union([bad], "twin.ladder")
    assert u is not None
    assert fe.rung_counts()["twin.ladder"][0] == 1
    assert "twin.ladder" in fe.rung_note()
    fe.reset_rung_counts()
    assert fe.rung_note() == ""


# ── T3 ────────────────────────────────────────────────────────────────────
def test_t3_a_footprint_that_repairs_to_nothing_is_not_a_witness():
    """``_witness`` returns ``None`` and the drop is NAMED — never silent
    (§51 (2) EMPTY)."""
    verts, tris = _sliver_mesh()
    geom = obj8.ObjGeometry("Objects/Sliver.OBJ", verts, tris,
                            np.zeros(tris.shape[0], dtype=np.int64),
                            np.zeros((0, 3), dtype=np.int64))
    comps = obj8.solid_components(geom)
    assert comps, "the fixture must make one solid component"
    drops: list[str] = []
    mat = obj8.placement_affine((0.0, 0.0), 0.0)
    w = obj8._witness(verts, comps[0], base=0.0, local=0.0, plane_below=1.0,
                      normal_y_min=0.5, mat=mat, comp_index=7, q=Q,
                      degenerate=drops, resource="Objects/Sliver.OBJ")
    assert w is None
    assert drops and "Sliver.OBJ#7" in drops[0] and "repairs to nothing" in drops[0]


def _sliver_mesh():
    """A closed solid whose PLAN area is a hundredth of a grid cell — the
    placed footprint repairs to nothing at the 1 mm quantum."""
    w = 1e-4
    verts = np.array([[0.0, -2.0, 0.0], [w, -2.0, 0.0], [w, -2.0, w], [0.0, -2.0, w],
                      [0.0, 0.0, 0.0], [w, 0.0, 0.0], [w, 0.0, w], [0.0, 0.0, w]],
                     dtype=float)
    tris = np.array([[0, 1, 2], [0, 2, 3],          # floor
                     [4, 6, 5], [4, 7, 6],          # roof
                     [0, 4, 5], [0, 5, 1],
                     [1, 5, 6], [1, 6, 2],
                     [2, 6, 7], [2, 7, 3],
                     [3, 7, 4], [3, 4, 0]], dtype=np.int64)
    return verts, tris


# ── T4 — the platform twin ────────────────────────────────────────────────
def test_t4_one_ulp_of_input_gives_byte_identical_output():
    """The snap is what makes the three platforms one programme: a
    coordinate perturbed by the last ulp — the measured PROJ/libm spread
    (§46 (2): 2.11e-9 m max) — leaves ``enter``'s WKB unchanged."""
    ring = shapely.from_wkt(GEML_FREE_HOLE_WKT)
    coords = shapely.get_coordinates(ring)
    sign = np.where(np.arange(coords.shape[0] * 2).reshape(coords.shape) % 2, 1, -1)
    nudged = shapely.set_coordinates(
        shapely.transform(ring, lambda c: c.copy()),
        np.nextafter(coords, coords + sign * np.inf))
    assert not np.array_equal(shapely.get_coordinates(nudged), coords)
    a = fe.enter([ring], fe.IDENTITY, Q)[0]
    b = fe.enter([nudged], fe.IDENTITY, Q)[0]
    assert shapely.to_wkb(a) == shapely.to_wkb(b)
    # and WITHOUT the snap the two differ — the snap is load-bearing
    a0 = fe.enter([ring], fe.IDENTITY, 0.0)[0]
    b0 = fe.enter([nudged], fe.IDENTITY, 0.0)[0]
    assert shapely.to_wkb(a0) != shapely.to_wkb(b0)


# ── T5 ────────────────────────────────────────────────────────────────────
def test_t5_q_zero_skips_the_snap_and_nothing_else():
    ring = shapely.from_wkt(GEML_FREE_HOLE_WKT)
    r = fe.enter([ring], fe.IDENTITY, 0.0)[0]
    assert r is not None and r.is_valid                       # the repair still ran
    # unsnapped: the coordinates are the affine's own doubles
    got = set(map(tuple, shapely.get_coordinates(r).tolist()))
    src = set(map(tuple, shapely.get_coordinates(ring).tolist()))
    assert got & src, "with q = 0 the input coordinates survive verbatim"
    # the standing 1e-9 floor, not q * q
    tiny = Polygon([(0, 0), (1e-5, 0), (1e-5, 1e-5), (0, 1e-5)])   # 1e-10 m2
    assert fe.enter([tiny], fe.IDENTITY, 0.0)[0] is None
    mid = Polygon([(0, 0), (1e-3, 0), (1e-3, 1e-3), (0, 1e-3)])    # 1e-6 m2 == q*q
    assert fe.enter([mid], fe.IDENTITY, 0.0)[0] is not None        # survives at q = 0
    assert fe.enter([mid], fe.IDENTITY, Q)[0] is None              # one grid cell: out


def test_enter_passes_none_and_empty_through():
    out = fe.enter([None, Polygon(), Polygon([(0, 0), (10, 0), (10, 10)])], fe.IDENTITY, Q)
    assert out[0] is None and out[1] is None
    assert out[2] is not None and out[2].area == pytest.approx(50.0, abs=1e-6)


def test_enter_places_where_affine_transform_placed():
    """The batched affine is the one the consumers replaced, to the ulp
    (checked with the snap OFF, which is the only difference)."""
    from shapely import affinity
    p = Polygon([(0, 0), (12.0, 0), (12.0, 7.0), (0, 7.0)])
    mat = obj8.placement_affine((123.456, -654.321), 37.5)
    assert shapely.to_wkb(fe.enter([p], mat, 0.0)[0]) == \
        shapely.to_wkb(affinity.affine_transform(p, mat))


# ── T6 — the cache ────────────────────────────────────────────────────────
def test_t6_cache_version_bumped_and_frame_entry_in_the_code_digest():
    assert partition_cache.CACHE_VERSION >= 3     # 5: packperf #27/#29 + surfacesettle solid height
    assert "auto_patch_v2.airport.frame_entry" in partition_cache._CODE_MODULES


def test_t6b_a_stale_payload_is_refused_and_a_frame_entry_change_moves_it(tmp_path,
                                                                          monkeypatch):
    """A payload written under another fingerprint is a MISS, never a
    repair-on-read (a repaired stale read would be a second entry site);
    and the ``frame_entry`` source is part of the fingerprint, so every
    v2-era reading invalidates by itself."""
    path = tmp_path / "part.cache"
    assert partition_cache.write(str(path), "fp-v3", {"hello": 1})
    assert partition_cache.read(str(path), "fp-v3") == {"hello": 1}
    assert partition_cache.read(str(path), "fp-v2") is None      # refused, not repaired

    monkeypatch.setattr(partition_cache, "_CODE_DIGEST", None)
    before = partition_cache.code_digest()
    other = tmp_path / "frame_entry.py"
    other.write_text(pathlib.Path(fe.__file__).read_text() + "\n# moved\n")
    monkeypatch.setattr(fe, "__file__", str(other))
    monkeypatch.setattr(partition_cache, "_CODE_DIGEST", None)
    assert partition_cache.code_digest() != before


# ── T7 — a registered capture's own footprints ────────────────────────────
_CAPTURES = pathlib.Path("/Users/noah/ortho4xp-captures")
_GEML_BELOW = _CAPTURES / "gemltopology" / "GEML.door_below.pkl"


@pytest.mark.skipif(not _GEML_BELOW.is_file(),
                    reason="the registered GEML capture is not on this machine")
def test_t7_every_enter_output_over_a_registered_capture_is_valid():
    """Lane ``gemltopology``'s registered GEML capture — the 449 placed
    sill footprints of ``Objects/CartelonAprox.OBJ``, 126 of them INVALID
    as the pre-§51 path minted them.  Re-entered: 0 of N invalid."""
    import pickle
    fams = pickle.loads(_GEML_BELOW.read_bytes())
    geoms = [shapely.from_wkb(bytes(row[-1]))
             for members in fams.values() for row in members]
    assert len(geoms) > 100, len(geoms)
    raw = np.array(geoms, dtype=object)
    assert (~shapely.is_valid(raw)).sum() > 0, "the capture must carry the defect"
    out = fe.enter(geoms, fe.IDENTITY, Q)
    live = out[~shapely.is_missing(out)]
    assert live.size
    assert int((~shapely.is_valid(live)).sum()) == 0
    assert fe.union(live.tolist(), "twin.t7") is not None


# ── G1 / G2 — the AST twins ───────────────────────────────────────────────
def _py_files():
    for pkg in ("airport", "planar"):
        for p in sorted((_SRC / pkg).glob("*.py")):
            yield p


def _attr_name(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def test_g1_no_placement_affine_outside_frame_entry():
    """§51 (2): ``frame_entry.enter`` is the ONLY place in ``airport/``
    and ``planar/`` that applies a placement affine to a polygon.  The
    allow-list is EMPTY: a site that only needs the affine (a line, a
    point) calls ``frame_entry.transform``, which spells it once."""
    bad = []
    for p in _py_files():
        if p.name == "frame_entry.py":
            continue
        for node in ast.walk(ast.parse(p.read_text(), str(p))):
            if not isinstance(node, ast.Call):
                continue
            name = _attr_name(node.func) if isinstance(node.func, ast.Attribute) \
                else (node.func.id if isinstance(node.func, ast.Name) else "")
            leaf = name.rsplit(".", 1)[-1]
            if leaf in ("affine_transform", "rotate") and "affinity" in name or \
                    leaf == "affine_transform":
                bad.append(f"{p.name}:{node.lineno} {name}")
    assert not bad, bad


#: The functions §51 (4) rules UNION.  A bare ``unary_union`` /
#: ``union_all`` inside one of them is the defect the law removes.
_UNION_FUNCTIONS = {
    ("obj8.py", "_transformed"),
    ("obj8.py", "_in_window"),
    ("obj8_clip.py", "_union_rings"),
    ("obj8_grade.py", "memo_union"),
    ("door_wells.py", "read_door_wells"),
    ("wall_corridors.py", "_bands_of"),
    ("basins.py", "_UnionClock"),
    # the sweep the coordinator added on the TFFJ abort (2026-09-18,
    # lane ``roadclampscope``): EVERY union whose operands are PLACED
    # pack geometry, not only the five the §51 (4) census tabled.
    ("sunken_roads.py", "read_sunken_roads"),
    ("deck_signature.py", "_spans"),
    ("deck_signature.py", "promote"),
    ("wall_geometry.py", "_straight_runs"),
    ("wall_geometry.py", "_merge_walls"),
    ("tunnel_objects.py", "signature"),
    ("tunnel_objects.py", "_bore_ends_at"),
    ("tunnel_objects.py", "shell_corridor"),
    ("basin_witness.py", "ramp_decks"),
}


def test_g2_the_union_sites_hold_no_bare_union():
    seen = set()
    bad = []
    for p in _py_files():
        tree = ast.parse(p.read_text(), str(p))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                continue
            key = (p.name, node.name)
            if key not in _UNION_FUNCTIONS:
                continue
            seen.add(key)
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                name = _attr_name(sub.func) if isinstance(sub.func, ast.Attribute) \
                    else (sub.func.id if isinstance(sub.func, ast.Name) else "")
                if name.rsplit(".", 1)[-1] in ("unary_union", "union_all"):
                    bad.append(f"{p.name}:{sub.lineno} {node.name} -> {name}")
    assert seen == _UNION_FUNCTIONS, f"the census moved: {_UNION_FUNCTIONS - seen}"
    assert not bad, bad


# ── G3 — the convergence guard ────────────────────────────────────────────
@pytest.mark.parametrize("q", [Q, 0.0])
def test_g3_enter_is_idempotent(q):
    """``enter(enter(g), I) == enter(g)`` bytewise: a second pass changes
    nothing, so no consumer can need a belt."""
    cases = [shapely.from_wkt(GEML_FREE_HOLE_WKT),
             Polygon([(0, 0), (30, 0), (30, 20), (0, 20)],
                     [[(5, 5), (5, 10), (10, 10), (10, 5)]]),
             Polygon([(0, 0), (4, 4), (4, 0), (0, 4)]),          # bow-tie
             shapely.union_all([Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
                                Polygon([(9, 9), (11, 9), (11, 11), (9, 11)])])]
    mat = obj8.placement_affine((512.25, -88.125), 61.0)
    once = fe.enter(cases, mat, q)
    twice = fe.enter(list(once), fe.IDENTITY, q)
    for a, b in zip(once, twice):
        assert (a is None) == (b is None)
        if a is not None:
            assert shapely.to_wkb(a) == shapely.to_wkb(b)


def test_build_time_impact_statement_is_measurable():
    """§51 (6): ~0.15 s per 10^5 five-vertex parts.  Held here as an ORDER
    bar only (CI machines vary): 100k parts under 3 s, so a per-geometry
    Python loop (the ``_rim_index`` 137 s class) cannot pass."""
    import time
    n = 100_000
    xs = np.arange(n, dtype=float) * 3.0
    rings = np.stack([np.stack([xs, xs + 2, xs + 2, xs, xs], axis=1),
                      np.zeros((n, 5)) + np.array([0.0, 0.0, 2.0, 2.0, 0.0])], axis=2)
    parts = shapely.polygons(rings)
    mat = obj8.placement_affine((10.0, -10.0), 33.0)
    t0 = time.perf_counter()
    out = fe.enter(parts, mat, Q)
    dt = time.perf_counter() - t0
    assert int(shapely.is_missing(out).sum()) == 0
    assert dt < 3.0, f"{dt:.2f} s for {n} parts — the vectorised form is required"
