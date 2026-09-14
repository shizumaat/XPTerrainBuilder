"""Known-answer twins for ``tools/mesh_region_tris.py --area-bands``.

Instrument-truth (RULINGS 2026-08-06): the sliver count this reports is
load-bearing evidence (the density audit's rank-1 finding and the
sliver-repair spec's phase-B pre-registration both turn on it), so it
needs a case whose answer is computable by hand.

The mesh below is written in the MEDIT text form Triangle4XP emits, with
triangles of DELIBERATE areas at HECA's latitude: one ~0.02 m^2 sliver,
one ~0.5 m^2, one ~200 m^2, and one of each outside the bbox.
"""
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import mesh_region_tris as MRT  # noqa: E402


LAT0, LAT1 = 30.0940, 30.1429
LON0, LON1 = 31.3717, 31.4531
MID = 0.5 * (LAT0 + LAT1)
M_LAT = math.pi * MRT.R_EARTH_M / 180.0
M_LON = M_LAT * math.cos(math.radians(MID))


def _tri_at(lat, lon, leg_m):
    """A right triangle with legs ``leg_m`` — area ``leg^2 / 2``."""
    dlat = leg_m / M_LAT
    dlon = leg_m / M_LON
    return [(lon, lat), (lon + dlon, lat), (lon, lat + dlat)]


def _write_mesh(path, tris):
    verts = []
    faces = []
    for t in tris:
        base = len(verts) + 1
        verts.extend(t)
        faces.append((base, base + 1, base + 2))
    lines = ["MeshVersionFormatted 1", "Dimension 3", "Vertices",
             str(len(verts))]
    lines += [f"{lon:.9f} {lat:.9f} 0.0 0" for lon, lat in verts]
    lines += ["Triangles", str(len(faces))]
    lines += [f"{a} {b} {c} 0" for a, b, c in faces]
    lines += ["End", ""]
    Path(path).write_text("\n".join(lines))


@pytest.fixture
def mesh(tmp_path):
    inside = (0.5 * (LAT0 + LAT1), 0.5 * (LON0 + LON1))
    outside = (LAT1 + 0.01, LON1 + 0.01)
    tris = [
        _tri_at(*inside, 0.2),    # area 0.02 m^2   -> sliver band
        _tri_at(*inside, 0.2),    # area 0.02 m^2   -> sliver band
        _tri_at(*inside, 1.0),    # area 0.5 m^2    -> 0.1-1 band
        _tri_at(*inside, 2.0),    # area 2.0 m^2    -> 1 m^2 - texel^2
        _tri_at(*inside, 20.0),   # area 200 m^2    -> visible
        _tri_at(*outside, 0.2),   # a sliver OUTSIDE the box
    ]
    p = tmp_path / "t.mesh"
    _write_mesh(p, tris)
    return p


def test_the_bbox_split_and_the_area_bands_are_hand_computable(mesh, capsys,
                                                               tmp_path):
    out = tmp_path / "o.json"
    MRT.main(["--mesh", str(mesh),
              "--bbox", f"{LAT0},{LAT1},{LON0},{LON1}",
              "--area-bands", "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["triangles_tile"] == 6
    assert d["triangles_in_bbox"] == 5
    # bands: [<0.1, 0.1-1, 1-texel^2, >=texel^2]
    assert d["area_bands_in_bbox"] == [2, 1, 1, 1]
    assert d["area_bands_outside"] == [1, 0, 0, 0]
    # the sliver band's GROUND COVER is the point of the class: two
    # 0.02 m^2 triangles carry 0.04 m^2 between them.
    assert d["area_bands_ground_m2_in_bbox"][0] == pytest.approx(0.04,
                                                                 rel=1e-3)
    assert d["area_bands_ground_m2_in_bbox"][3] == pytest.approx(200.0,
                                                                 rel=1e-3)


def test_the_texel_is_the_published_number(mesh):
    """ZL16 at HECA's mid-latitude is 2.0662 m / 4.269 m^2 — the value
    every sliver table in this campaign is stated against."""
    assert MRT.texel_m(30.118, 16) == pytest.approx(2.0662, abs=5e-4)
    assert MRT.texel_m(0.0, 16) == pytest.approx(2.3887, abs=5e-4)
    assert MRT.texel_m(MID, 16) ** 2 == pytest.approx(4.269, abs=2e-3)


def test_band_edges_may_be_given_explicitly(mesh, tmp_path):
    out = tmp_path / "o.json"
    MRT.main(["--mesh", str(mesh),
              "--bbox", f"{LAT0},{LAT1},{LON0},{LON1}",
              "--area-bands", "1", "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["area_band_edges_m2"] == [1.0]
    assert d["area_bands_in_bbox"] == [3, 2]   # <1 m^2: 0.02,0.02,0.5


def test_no_bands_asked_no_bands_reported(mesh, tmp_path):
    out = tmp_path / "o.json"
    MRT.main(["--mesh", str(mesh),
              "--bbox", f"{LAT0},{LAT1},{LON0},{LON1}",
              "--json", str(out)])
    d = json.loads(out.read_text())
    assert "area_bands_in_bbox" not in d
    assert d["triangles_in_bbox"] == 5


@pytest.mark.parametrize("spec,why", [
    ("1,0.1", "must ASCEND"),
    ("0,1", "must be positive"),
    ("", "at least one edge"),
    ("a,b", "not a list"),
])
def test_it_refuses_a_bad_band_spec(spec, why):
    with pytest.raises(SystemExit) as e:
        MRT.parse_area_bands(spec)
    assert why in str(e.value)


def test_band_index_is_half_open_upward():
    edges = [0.1, 1.0, 4.269]
    assert MRT.band_index(0.0, edges) == 0
    assert MRT.band_index(0.099, edges) == 0
    assert MRT.band_index(0.1, edges) == 1      # the edge belongs UP
    assert MRT.band_index(4.269, edges) == 3
    assert MRT.band_index(1e6, edges) == 3


# ── --aspect: the LONG-TRIANGLE class an area band cannot see ───────────
# Added 2026-08-08 (fabricA, THE FABRIC MODEL Phase A): the acceptance is
# "no new long-triangle artifact class", and a needle and an equilateral
# of the same area sit in the SAME area band — so the bands alone cannot
# answer it.  Ratio = longest edge / (2 x inradius); 1.0 = equilateral.

def _needle_at(lat, lon, long_m, short_m):
    """A right triangle with legs ``long_m`` x ``short_m`` — same AREA as
    an equilateral of side sqrt(2*long*short/sqrt(3)), different SHAPE."""
    return [(lon, lat),
            (lon + long_m / M_LON, lat),
            (lon, lat + short_m / M_LAT)]


def test_aspect_is_one_for_equilateral_and_large_for_a_needle(tmp_path):
    lat, lon = 0.5 * (LAT0 + LAT1), 0.5 * (LON0 + LON1)
    side = 10.0
    equi = [(lon, lat),
            (lon + side / M_LON, lat),
            (lon + 0.5 * side / M_LON, lat + (side * 3 ** 0.5 / 2) / M_LAT)]
    p = tmp_path / "e.mesh"
    _write_mesh(p, [equi])
    out = tmp_path / "e.json"
    MRT.main(["--mesh", str(p), "--bbox", f"{LAT0},{LAT1},{LON0},{LON1}",
              "--aspect", "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["aspect_in_bbox"]["n"] == 1
    assert d["aspect_in_bbox"]["max"] == pytest.approx(1.0, rel=2e-3)

    p2 = tmp_path / "n.mesh"
    _write_mesh(p2, [_needle_at(lat, lon, 40.0, 0.5)])
    out2 = tmp_path / "n.json"
    MRT.main(["--mesh", str(p2), "--bbox", f"{LAT0},{LAT1},{LON0},{LON1}",
              "--aspect", "--json", str(out2)])
    d2 = json.loads(out2.read_text())
    # 40 x 0.5 right triangle: longest edge 40.003, area 10, s = 40.2515
    # -> 40.003 * 40.2515 / (2*sqrt(3) * 10) ~= 46.48
    assert d2["aspect_in_bbox"]["max"] == pytest.approx(46.48, rel=0.02)


def test_aspect_separates_shape_from_size(tmp_path):
    """THE POINT: two triangles of the SAME area land in one area band and
    in very different aspect classes."""
    lat, lon = 0.5 * (LAT0 + LAT1), 0.5 * (LON0 + LON1)
    fat = _needle_at(lat, lon, 4.0, 5.0)        # area 10 m^2
    thin = _needle_at(lat, lon, 40.0, 0.5)      # area 10 m^2
    p = tmp_path / "b.mesh"
    _write_mesh(p, [fat, thin])
    out = tmp_path / "b.json"
    MRT.main(["--mesh", str(p), "--bbox", f"{LAT0},{LAT1},{LON0},{LON1}",
              "--area-bands", "1", "--aspect", "--aspect-flag", "20",
              "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["area_bands_in_bbox"] == [0, 2]          # one band, both
    assert d["aspect_in_bbox"]["needles"] == 1        # only the needle
    assert d["aspect_flag"] == 20.0


def test_aspect_counts_only_in_bbox_and_is_absent_unasked(tmp_path):
    inside = (0.5 * (LAT0 + LAT1), 0.5 * (LON0 + LON1))
    outside = (LAT1 + 0.01, LON1 + 0.01)
    p = tmp_path / "c.mesh"
    _write_mesh(p, [_needle_at(*inside, 40.0, 0.5),
                    _needle_at(*outside, 40.0, 0.5)])
    out = tmp_path / "c.json"
    MRT.main(["--mesh", str(p), "--bbox", f"{LAT0},{LAT1},{LON0},{LON1}",
              "--aspect", "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["aspect_in_bbox"]["n"] == 1
    out2 = tmp_path / "d.json"
    MRT.main(["--mesh", str(p), "--bbox", f"{LAT0},{LAT1},{LON0},{LON1}",
              "--json", str(out2)])
    assert "aspect_in_bbox" not in json.loads(out2.read_text())


# ── THE EDGE AUDIT (owner RULINGS 2026-09-10g) ────────────────────────
#
# The area read that replaced the terrain edge's one-transect bar.  Its
# three classes are planted here by hand, and the CLEAN mesh beside them
# is the instrument's own proof: a class the audit reports on a mesh with
# nothing planted in it is the audit's artefact, not the change's.
EA_LAT, EA_LON = 60.6968, -135.0556
EA_M_LAT = math.pi * MRT.R_EARTH_M / 180.0
EA_M_LON = EA_M_LAT * math.cos(math.radians(EA_LAT))


def _ea_ll(dx_m, dy_m):
    return (EA_LON + dx_m / EA_M_LON, EA_LAT + dy_m / EA_M_LAT)


def _write_mesh_z(path, tris):
    """A MEDIT mesh from ``(lon, lat, z_m)`` triples (z is stored /1e5)."""
    verts, faces = [], []
    for t in tris:
        base = len(verts) + 1
        verts.extend(t)
        faces.append((base, base + 1, base + 2))
    lines = ["MeshVersionFormatted 1", "Dimension 3", "Vertices",
             str(len(verts))]
    lines += [f"{lo:.9f} {la:.9f} {z / 100000.0:.12f} 0" for lo, la, z in verts]
    lines += ["Triangles", str(len(faces))]
    lines += [f"{a} {b} {c} 0" for a, b, c in faces]
    lines += ["End", ""]
    path.write_text("\n".join(lines))
    return path


def _flat_tri(dx, dy, leg, z):
    return [(*_ea_ll(dx, dy), z), (*_ea_ll(dx + leg, dy), z),
            (*_ea_ll(dx, dy + leg), z)]


def test_edge_audit_reads_zero_on_a_clean_mesh(tmp_path, capsys):
    """THE INSTRUMENT'S PROOF: level triangles at the DEM's own height
    report no overlapping pair, no wall and no difference past the edge."""
    tris = [_flat_tri(dx, 0.0, 10.0, 700.0) for dx in (0.0, 20.0, 40.0)]
    mesh = _write_mesh_z(tmp_path / "Data+60-136.mesh", tris)
    out = MRT.edge_audit(str(mesh), (EA_LAT, EA_LON, 150.0))
    capsys.readouterr()
    assert out["triangles_near"] == 3
    assert out["overlapping_pairs"] == 0
    assert out["walls"] == 0


def test_edge_audit_finds_a_planted_overlapping_pair(tmp_path, capsys):
    """Two vertices 0.2 m apart in plan and 9 m apart in z — the owner's
    'overlapping nodes at different elevations'."""
    tris = [_flat_tri(0.0, 0.0, 10.0, 700.0),
            [(*_ea_ll(0.2, 0.0), 709.0), (*_ea_ll(0.2, 12.0), 709.0),
             (*_ea_ll(10.0, 12.0), 709.0)]]
    mesh = _write_mesh_z(tmp_path / "Data+60-136.mesh", tris)
    out = MRT.edge_audit(str(mesh), (EA_LAT, EA_LON, 150.0))
    capsys.readouterr()
    assert out["overlapping_pairs"] == 1
    assert out["overlapping_worst_dz_m"] == pytest.approx(9.0, abs=0.01)
    # widen the identity spacing and it is no longer one position
    tight = MRT.edge_audit(str(mesh), (EA_LAT, EA_LON, 150.0), dz_m=20.0)
    capsys.readouterr()
    assert tight["overlapping_pairs"] == 0


def test_edge_audit_excuses_a_wall_the_dem_itself_has(tmp_path, capsys,
                                                     monkeypatch):
    """A triangle falling 20 m over 10 m is a WALL — unless the DEM under
    the same footprint falls with it, which is a cliff, not a defect."""
    tris = [[(*_ea_ll(0.0, 0.0), 700.0), (*_ea_ll(0.0, 10.0), 700.0),
             (*_ea_ll(10.0, 0.0), 680.0)]]
    mesh = _write_mesh_z(tmp_path / "Data+60-136.mesh", tris)

    class _Alt:
        def __init__(self, steep):
            self.steep = steep

        def elevation_at(self, lat, lon):
            dx = (lon - EA_LON) * EA_M_LON
            return 700.0 - (2.0 * dx if self.steep else 0.0)

    flat = MRT.edge_audit(str(mesh), (EA_LAT, EA_LON, 150.0))
    capsys.readouterr()
    assert flat["steep_triangles"] == 1 and flat["walls"] == 1

    monkeypatch.setattr(MRT, "_alt_reader",                # DEM is that steep
                        lambda *_a, **_k: _Alt(True))
    excused = MRT.edge_audit(str(mesh), (EA_LAT, EA_LON, 150.0),
                             alt_path="x", tile=(60, -136))
    capsys.readouterr()
    assert excused["steep_triangles"] == 1 and excused["walls"] == 0
    monkeypatch.setattr(MRT, "_alt_reader",                # DEM is level
                        lambda *_a, **_k: _Alt(False))
    flagged = MRT.edge_audit(str(mesh), (EA_LAT, EA_LON, 150.0),
                             alt_path="x", tile=(60, -136))
    capsys.readouterr()
    assert flagged["walls"] == 1
    assert flagged["past_edge_over_bar"] >= 1              # (c) sees the drop


def test_edge_audit_refuses_an_unbounded_read(tmp_path):
    mesh = _write_mesh_z(tmp_path / "Data+60-136.mesh",
                         [_flat_tri(0.0, 0.0, 10.0, 700.0)])
    with pytest.raises(SystemExit, match="AREA read"):
        MRT.main(["--mesh", str(mesh), "--edge-audit"])


# ── THE NODE -> MESH CROSS-REFERENCE (owner RULINGS 2026-09-13cp) ──────
#
# A hand-built pair the numbers can be read off by eye: a unit square
# PATCH RING at 600 m whose four corners the mesh honours exactly, one
# bare-INTERP_ALT ROAD RIBBON node the ``.node`` carries at 589 m and the
# mesh emits at 568 (the LEMD canyon, 21 m), and one DUMMY node the mesh
# moved 0.4 m.  The identity join is verified, never trusted.

def _write_xref_inputs(tmp_path, ribbon_mesh_z):
    """``(prefix, mesh_path)`` — a 6-node .node/.poly and its mesh."""
    import mesh_region_tris as MRT

    ring = [(0.000, 0.000), (0.001, 0.000), (0.001, 0.001), (0.000, 0.001)]
    ribbon = [(0.0004, 0.0005), (0.0006, 0.0005)]
    nodes = ring + ribbon
    z_node = [600.0] * 4 + [589.0, 589.0]
    prefix = tmp_path / "Data+40-004"
    (prefix.with_suffix(".node")).write_text(
        "6 2 1 0\n" + "".join(
            f"{i + 1} {x:.9f} {y:.9f} {z:.9f}\n"
            for i, ((x, y), z) in enumerate(zip(nodes, z_node))))
    segments = [(i + 1, (i + 1) % 4 + 1, MRT.PATCH_RING_MARKER)
                for i in range(4)]
    segments.append((5, 6, MRT.INTERP_ALT_BIT))
    (prefix.with_suffix(".poly")).write_text(
        "0 2 1 0\n\n" + f"{len(segments)} 1\n"
        + "".join(f"{k + 1} {a} {b} {m}\n"
                  for k, (a, b, m) in enumerate(segments))
        + "\n0\n\n0\n")
    # the MESH: input vertices FIRST and in order (Triangle's own rule),
    # then one Steiner vertex OUTSIDE the ring standing 12 m low — the
    # cliff at the patch edge.
    z_mesh = [600.0] * 4 + [ribbon_mesh_z, ribbon_mesh_z] + [588.0]
    verts = [(x - 4.0, y + 40.0, z)
             for (x, y), z in zip(nodes + [(0.0015, 0.0005)], z_mesh)]
    faces = [(1, 2, 5), (2, 3, 6), (3, 4, 5), (2, 6, 7), (3, 7, 6)]
    lines = ["MeshVersionFormatted 1", "Dimension 3", "Vertices",
             str(len(verts))]
    lines += [f"{lo:.9f} {la:.9f} {z / 100000.0:.12f} 0"
              for lo, la, z in verts]
    lines += ["Triangles", str(len(faces))]
    lines += [f"{a} {b} {c} 8" for a, b, c in faces]
    lines += ["End", ""]
    mesh = tmp_path / "Data+40-004.mesh"
    mesh.write_text("\n".join(lines))
    return (str(prefix), str(mesh))


def test_node_xref_splits_the_ribbons_from_the_rings(tmp_path, capsys):
    """The 1.0.329 signature: PATCH_RING exact, the ribbons 21 m off."""
    import mesh_region_tris as MRT

    (prefix, mesh) = _write_xref_inputs(tmp_path, 568.0)
    payload = MRT.node_mesh_xref(mesh, prefix, 40, -4, bar_m=2.0)
    out = capsys.readouterr().out
    ring = payload["classes"]["PATCH_RING"]
    assert ring["n"] == 4 and ring["over_bar"] == 0 and ring["max"] == 0.0
    ribbon = payload["classes"]["INTERP_ALT"]
    assert ribbon["n"] == 2 and ribbon["over_bar"] == 2
    assert ribbon["max"] == pytest.approx(21.0)
    assert "PATCH_RING" in out and "INTERP_ALT" in out


def test_node_xref_reads_the_patch_edge_step(tmp_path):
    """THE CLIFF the bank exists to grade: a ring vertex at 600 m beside
    an OUTSIDE mesh vertex at 588 is a 12 m step, and it is reported."""
    import mesh_region_tris as MRT

    (prefix, mesh) = _write_xref_inputs(tmp_path, 589.0)
    payload = MRT.node_mesh_xref(mesh, prefix, 40, -4)
    step = payload["patch_edge_step"]
    assert step["n"] >= 1
    assert step["max"] == pytest.approx(12.0)
    assert step["over_3m"] >= 1


def test_node_xref_REFUSES_when_the_identity_join_is_broken(tmp_path):
    """A cross-reference with no identity join prints coincidences."""
    import mesh_region_tris as MRT

    (prefix, mesh) = _write_xref_inputs(tmp_path, 589.0)
    text = open(mesh).read().replace("-4.000000000 40.000000000",
                                     "-3.900000000 40.000000000")
    open(mesh, "w").write(text)
    with pytest.raises(SystemExit) as caught:
        MRT.node_mesh_xref(mesh, prefix, 40, -4)
    assert "did not preserve the input vertex order" in str(caught.value)
