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
