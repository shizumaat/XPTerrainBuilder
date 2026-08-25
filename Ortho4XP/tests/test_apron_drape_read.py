"""Known-answer twin for ``tools/apron_drape_read.py``.

The tool reports a SHAPE, not a law, so the twin's job is that each of the
three numbers is the arithmetic it claims to be on a ring whose answer can
be computed by hand — and that the tool refuses rather than substitutes
when the DEM it was asked for is not there.

Headless: the DEM is a stub, so nothing reads or writes the shared corpus.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import apron_drape_read as ADR                                 # noqa: E402


class _FlatDem:
    """A DEM at a constant elevation over the whole tile — so
    ``height_above_dem`` is exactly the emitted elevation minus it."""

    nodata = -32768.0
    x0, x1 = 0.0, 1.0
    y0, y1 = 0.0, 1.0

    def __init__(self, value: float):
        self._v = float(value)

    def alt(self, xy):
        return self._v


def _patch(tmp_path: Path, elevs, *, lat0=30.0, lon=31.0, name="TEST") -> Path:
    """A one-apron-ring patch whose vertices march EAST at ~11.132 m
    spacing (1e-4 deg of longitude at the equator-ish latitude used), so a
    50 m window reaches ~4 vertices each side."""
    nodes, nds = [], []
    for i, e in enumerate(elevs):
        nid = -(100 + i)
        nodes.append(
            f"  <node id='{nid}' lat='{lat0:.7f}' "
            f"lon='{lon + i * 1e-4:.7f}'>"
            f"<tag k='alt_abs' v='{e}'/></node>")
        nds.append(f"    <nd ref='{nid}'/>")
    nds.append(f"    <nd ref='{-(100)}'/>")
    xml = ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
           + "\n".join(nodes) + "\n"
           + "  <way id='-1'>\n" + "\n".join(nds) + "\n"
           + "    <tag k='role' v='apron'/>\n"
           + "    <tag k='aeroway' v='apron'/>\n"
           + "    <tag k='ref' v='apron1'/>\n"
           + "  </way>\n</osm>\n")
    p = tmp_path / f"{name}_auto.patch.osm"
    p.write_text(xml)
    return p


@pytest.fixture()
def stub_dem(monkeypatch):
    def _install(value: float):
        monkeypatch.setattr(
            ADR, "_load_dem",
            lambda tl, tn, icao, src: (_FlatDem(value), "stub", "stub"))
    return _install


def test_height_above_dem_is_elevation_minus_dem(tmp_path, stub_dem):
    stub_dem(100.0)
    # Ten vertices at 102 m over a DEM at 100 m: every height is 2.0.
    p = _patch(tmp_path, [102.0] * 10)
    r = ADR.read_one(p, dem_source="base")
    assert r["apron_rings"] == 1
    assert r["apron_vertices"] == 10
    assert r["vertices_uncovered_by_dem"] == 0
    assert r["height_above_dem_median_m"] == pytest.approx(2.0)
    # A perfectly flat plateau has NO relief and NO local amplitude —
    # which is the shape the back-edge rescope is meant to restore.
    assert r["ring_relief_median_m"] == pytest.approx(0.0)
    assert r["amp50_median_m"] == pytest.approx(0.0)


def test_ring_relief_is_the_p95_minus_p05_of_the_height(tmp_path, stub_dem):
    stub_dem(0.0)
    elevs = [float(i) for i in range(21)]        # 0 … 20
    p = _patch(tmp_path, elevs)
    r = ADR.read_one(p, dem_source="base")
    lo = ADR._pct(elevs, ADR.RELIEF_LO_PCT)
    hi = ADR._pct(elevs, ADR.RELIEF_HI_PCT)
    assert r["ring_relief_median_m"] == pytest.approx(hi - lo)
    assert r["height_above_dem_median_m"] == pytest.approx(10.0)


def test_amp50_reads_only_within_its_along_ring_window(tmp_path, stub_dem):
    """The window is a WALK ALONG THE RING, and it is BOUNDED: a spike far
    enough away in ring-arc terms must not enter a vertex's amplitude.

    40 vertices at ~9.6 m spacing is ~385 m of ring, so a single +50 m
    spike is seen by the ~5 vertices each side of it (11 of 40, above the
    p95 mark) and by nobody past ~50 m — the vertex diametrically
    opposite is 192 m away along the ring in either direction and must
    read 0.  Both halves matter: an UNBOUNDED window would make every
    amplitude 50, and a broken walk would make them all 0.
    """
    n = 40
    elevs = [0.0] * n
    elevs[0] = 50.0
    p = _patch(tmp_path, elevs)
    stub_dem(0.0)
    r = ADR.read_one(p, dem_source="base")
    # The far half of the ring cannot see the spike, so the MEDIAN is 0…
    assert r["amp50_median_m"] == pytest.approx(0.0)
    # …while the vertices inside the window see the whole 50 m.
    assert r["amp50_p95_m"] == pytest.approx(50.0)


def test_a_missing_dem_refuses_rather_than_substituting(tmp_path, monkeypatch):
    """Two arms taken on two DEM surfaces are not comparable, so the tool
    must never quietly fall back to the other one."""
    monkeypatch.setattr(ADR, "_load_dem",
                        lambda tl, tn, icao, src: (None, None, None))
    p = _patch(tmp_path, [1.0] * 5)
    with pytest.raises(SystemExit) as e:
        ADR.read_one(p, dem_source="airport-inset")
    assert "refusing to substitute" in str(e.value)


def test_only_apron_rings_are_read(tmp_path, stub_dem):
    """The ruling is about APRONS; a taxiway ring in the same patch must
    not enter the reading."""
    stub_dem(0.0)
    p = _patch(tmp_path, [5.0] * 8)
    txt = p.read_text().replace(
        "</osm>",
        "  <node id='-900' lat='30.0000000' lon='31.0100000'>"
        "<tag k='alt_abs' v='999'/></node>\n"
        "  <node id='-901' lat='30.0010000' lon='31.0100000'>"
        "<tag k='alt_abs' v='999'/></node>\n"
        "  <node id='-902' lat='30.0010000' lon='31.0110000'>"
        "<tag k='alt_abs' v='999'/></node>\n"
        "  <way id='-2'>\n"
        "    <nd ref='-900'/><nd ref='-901'/><nd ref='-902'/>"
        "<nd ref='-900'/>\n"
        "    <tag k='role' v='primary_parallel'/>\n"
        "    <tag k='aeroway' v='taxiway'/>\n"
        "  </way>\n</osm>")
    p.write_text(txt)
    r = ADR.read_one(p, dem_source="base")
    assert r["apron_rings"] == 1
    assert r["apron_vertices"] == 8
    assert r["height_above_dem_median_m"] == pytest.approx(5.0)


def test_the_tool_is_in_the_index():
    """Tool discipline (RULINGS 7e90032): a tool absent from the index is
    treated as absent, and it lands with its index row in the same
    commit."""
    idx = (_ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "Ortho4XP/tools/apron_drape_read.py" in idx
