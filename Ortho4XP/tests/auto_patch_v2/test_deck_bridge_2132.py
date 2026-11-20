"""Twins of the generated deck as a bridge (#2132 spec 2132-design
section 4; #2141 items 1-3): ``airport/deck_structure`` (slab, beams,
kerbs, piers), ``deck_obj8`` (material rows, two LODs, strips),
``deck_skin`` (the page's WEATHER / DECAL_LIB / SURFACE rows, Laminar
first), ``deck_line_art`` (X-Plane's line pages), ``deck_pavement`` (the
carried surface's page) and ``deck_objects`` through the recipe.
Headless: ``tmp_path`` and a fake X-Plane install."""
from __future__ import annotations

import os

import numpy as np
import pytest
from auto_patch_v2.airport import deck_line_art, deck_pavement, deck_skin
from auto_patch_v2.airport import generated_pack as gen
from auto_patch_v2.airport.apt_dat import parse_airport_block
from auto_patch_v2.airport.deck_obj8 import DeckSkin, DeckStrip, deck_obj8_text, overlay_obj8_text
from auto_patch_v2.airport.deck_structure import Road, end_edges, structure_parts
from auto_patch_v2.airport.obj8 import parse_obj8
from auto_patch_v2.law.tables import load_default
from shapely.geometry import Polygon
from test_generated_2123 import _apt, _pub  # noqa: E402  (sibling twin)
from test_pack_edits_2123 import BLOCK  # noqa: E402

LAW = load_default()
G = LAW.tables.structures.deck_gen
RING = Polygon([(-20, -25), (20, -25), (20, 25), (-20, 25)])     # route along z
ENDS = [[(-18, -23), (18, -23)], [(-18, 23), (18, 23)]]           # the end lines


def _top(x, z):
    return 0.02 - 0.01 * z


def _check_obj8(text: str) -> None:
    """The structure X-Plane loads: counts agree, every TRIS in range, a
    header row before POINT_COUNTS, LOD blocks in order."""
    rows = [r.split() for r in text.splitlines() if r.strip()]
    assert [r[0] for r in rows[:3]] == ["I", "800", "OBJ"]
    pc = next(r for r in rows if r[0] == "POINT_COUNTS")
    nvt, nidx = int(pc[1]), int(pc[4])
    assert sum(1 for r in rows if r[0] == "VT") == nvt
    assert sum(len(r) - 1 for r in rows if r[0] in ("IDX", "IDX10")) == nidx
    for r in rows:
        if r[0] == "TRIS":
            assert int(r[1]) >= 0 and int(r[1]) + int(r[2]) <= nidx and int(r[2]) % 3 == 0
        if r[0] in ("IDX", "IDX10"):
            assert all(0 <= int(i) < nvt for i in r[1:])
    head = [r[0] for r in rows[:rows.index(pc)]]
    assert head.index("TEXTURE") < (head.index("TEXTURE_NORMAL") if "TEXTURE_NORMAL" in head
                                    else len(head))
    lods = [(float(r[1]), float(r[2])) for r in rows if r[0] == "ATTR_LOD"]
    assert lods == sorted(lods) and lods[0][0] == 0.0


def test_parts_kerb_the_sides_only_and_stay_in_the_envelope():
    parts = structure_parts(RING, ENDS, G)
    names = [p.name for p in parts]
    assert names[0] == "slab" and "beam" in names and "kerb" in names
    assert "column" not in names                       # no roads: no piers
    ends = end_edges(RING, ENDS, float(G.end_tol_m), float(G.end_angle_deg))
    assert {tuple(sorted(e)) for e in ends} == {((-20, -25), (20, -25)), ((-20, 25), (20, 25))}
    kerbs = [p for p in parts if p.name == "kerb"]
    for k in kerbs:                                    # never across an end
        assert k.poly.distance(Polygon([(-5, 24.9), (5, 24.9), (5, 25), (-5, 25)])) > 0.01
        assert k.top_m == pytest.approx(0.30) and k.bottom_m == 0.0
    assert sum(k.poly.area for k in kerbs) == pytest.approx(2 * 50 * 0.40, rel=0.05)
    for p in parts:                                    # inside today's 1.0 m slab
        assert -float(G.thickness_m) - 1e-9 <= p.bottom_m <= p.top_m <= float(G.kerb_h_m)
    beams = [p for p in parts if p.name == "beam"]
    xs = sorted(p.poly.centroid.x for p in beams)
    assert np.allclose(np.diff(xs), float(G.beam_spacing_m))


def test_piers_stand_at_the_floor_edges_never_on_a_road():
    road = Road(((-40.0, 0.0), (40.0, 0.0)), 3.5)       # across the deck
    parts = structure_parts(RING, ENDS, G, roads=[road], floor_y=-6.0)
    cols = [p for p in parts if p.name == "column"]
    assert cols and all(p.floor_y == pytest.approx(-6.0 - float(G.pier_foot_m)) for p in cols)
    edge = 3.5 + float(G.shoulder_m)
    for c in cols:
        assert abs(c.poly.centroid.y) == pytest.approx(edge + float(G.pier_col_m) / 2, abs=1e-6)
        assert abs(c.poly.centroid.y) - float(G.pier_col_m) / 2 >= edge - 1e-6
    gaps = np.diff(sorted(c.poly.centroid.x for c in cols if c.poly.centroid.y > 0))
    assert gaps.max() <= float(G.pier_gap_m) + 1e-6
    short = Polygon([(-20, -10), (20, -10), (20, 10), (-20, 10)])     # 20 m: no piers
    assert not [p for p in structure_parts(short, [], G, roads=[road], floor_y=-6.0)
                if p.name == "column"]


def _write(tmp_path, text, name="d.obj"):
    p = tmp_path / name
    p.write_text(text, encoding="ascii", newline="\n")
    return parse_obj8(str(p))


def test_two_lods_keep_the_hard_deck_byte_equal(tmp_path):
    skin = DeckSkin("a.dds", (18.0, 36.0), "n.png", "w.png", "lib/g10/decals/x.dcl", "asphalt")
    plain = deck_obj8_text(RING, _top, thickness_m=1.0, texture="t.png", skin=skin)
    full = deck_obj8_text(RING, _top, thickness_m=1.0, texture="t.png", skin=skin,
                          parts=structure_parts(RING, ENDS, G))
    _check_obj8(plain)
    _check_obj8(full)
    for text in (plain, full):
        head = text.split("POINT_COUNTS")[0].split("\n\n", 2)[-1].split()
        assert head == ["TEXTURE", "a.dds", "TEXTURE_NORMAL", "n.png", "NORMAL_METALNESS",
                        "DECAL_LIB", "lib/g10/decals/x.dcl", "WEATHER", "w.png",
                        "GLOBAL_specular", "1"]
        assert "ATTR_hard_deck asphalt" in text
    a, b = _write(tmp_path, plain, "a.obj"), _write(tmp_path, full, "b.obj")
    ta = sorted(tuple(np.round(a.vertices[t].ravel(), 4)) for t in a.hard_deck)
    tb = sorted(tuple(np.round(b.vertices[t].ravel(), 4)) for t in b.hard_deck)
    assert ta == tb                                     # the solve reads the same deck
    assert full.count("ATTR_LOD") == 2 and "ATTR_LOD 0 1200" in full
    far = full.split("ATTR_LOD 1200")[1]
    assert "ATTR_hard" not in far.replace("ATTR_no_hard", "")
    assert b.vertices[:, 1].min() >= _top(0, 25) - 1.0 - 1e-6       # no piers: in the envelope


def test_prism_faces_point_out(tmp_path):
    from auto_patch_v2.airport.deck_structure import Part
    box_ = Polygon([(0, 0), (2, 0), (2, 6), (0, 6)])
    text = deck_obj8_text(box_, lambda x, z: 0.0, thickness_m=1.0, texture="t.png",
                          parts=[Part("slab", box_, 0.0, -0.25),
                                 Part("beam", Polygon([(0.5, 1), (1.5, 1), (1.5, 5), (0.5, 5)]),
                                      -0.25, -1.0, ("bottom", "sides"))])
    g = _write(tmp_path, text)
    v = g.vertices
    near = [r.split() for r in text.splitlines() if r.startswith("TRIS")][:2]
    n_near = int(near[1][1]) + int(near[1][2])
    idx = np.array([int(i) for r in text.splitlines() if r.startswith("IDX")
                    for i in r.split()[1:]]).reshape(-1, 3)[:n_near // 3]
    for a, b, c in idx:
        n = np.cross(v[b] - v[a], v[c] - v[a])
        centre = (v[a] + v[b] + v[c]) / 3
        beam = 0.5 - 1e-6 <= centre[0] <= 1.5 + 1e-6 and 1 - 1e-6 <= centre[2] <= 5 + 1e-6 \
            and centre[1] < -0.25 - 1e-6
        mid = np.array([1.0, -0.6 if beam else -0.125, 3.0])
        out = centre - mid
        if abs(n[1]) > 0.5 * np.linalg.norm(n):
            out = np.array([0.0, np.sign(out[1]), 0.0])
        else:
            out[1] = 0.0
        assert float(np.dot(n, out)) < 0       # right-hand normal points in: CW from outside


def test_strip_mirrors_its_repeat_and_reaches_left_of_travel(tmp_path):
    st = DeckStrip(((0.0, 0.0), (0.0, -70.0)), 1.0, 2.0, (0.25, 0.5), 30.0, 0.01, True)
    text = overlay_obj8_text(lambda x, z: 0.0, texture="r.dds", strips=[st],
                             material=["WEATHER_TRANSPARENT"])
    _check_obj8(text)
    vts = [tuple(map(float, r.split()[1:9])) for r in text.splitlines() if r.startswith("VT")]
    vs = sorted({round(v[7], 6) for v in vts})
    assert vs == [0.0, 0.33333, 1.0]                   # 0 -> 1 at 30 m -> 0 at 60 m -> 1/3
    left = [v for v in vts if v[6] == 0.25]
    assert all(v[0] == pytest.approx(-1.0) for v in left)   # travel north (-z): left is west
    assert "GLOBAL_no_shadow" in text and "ATTR_poly_os" not in text
    assert all(v[1] == pytest.approx(0.01) for v in vts)     # the strip's own lift


def _install(tmp_path, override=False):
    root = tmp_path / "X-Plane"
    so = root / "Resources" / "default scenery" / "sim objects"
    for d in ("apt_pavement/pavement", "apt_pavement/textures", "apt_lines"):
        (so / d).mkdir(parents=True)
    (so / "apt_pavement/pavement/twy_a.pol").write_text(
        "A\n850\nDRAPED_POLYGON\nTEXTURE ../textures/a_ALB.png\n"
        "TEXTURE_NORMAL 1.0 ../textures/a_NML.png\nWEATHER ../textures/a_wm.png\n"
        "NORMAL_METALNESS\nDECAL_LIB lib/g10/decals/a.dcl\nSURFACE asphalt\nSCALE 18 36\n",
        encoding="utf-8", newline="\n")
    (so / "apt_pavement/pavement/c.pol").write_text(
        "A\n850\nDRAPED_POLYGON\nTEXTURE ../textures/c_ALB.png\nSCALE 22 44\n",
            encoding="utf-8", newline="\n")
    (so / "apt_pavement/pavement/r.pol").write_text(
        "A\n850\nDRAPED_POLYGON\nTEXTURE r.png\nSCALE 30 30\nWEATHER_TRANSPARENT\n",
        encoding="utf-8", newline="\n")
    for name, off in (("1_single_taxi.lin", "S_OFFSET 0 46 54 62\n"),
                      ("51_single_taxi_b.lin", "S_OFFSET 0 328 342 356\nS_OFFSET 1 46 54 62\n")):
        (so / "apt_lines" / name).write_text(
            "A\n850\nLINE_PAINT\nTEXTURE taxilines.png\nTEXTURE_NORMAL 3.0 taxilines_NML.png\n"
            f"TEX_WIDTH 1024\nSCALE 12 3\n{off}DECAL_LIB lib/g10/decals/m.dcl\n"
            "WEATHER_TRANSPARENT\n", encoding="utf-8", newline="\n")
    for f in ("apt_pavement/textures/a_ALB.dds", "apt_pavement/textures/a_NML.png",
              "apt_pavement/textures/a_wm.png", "apt_pavement/textures/c_ALB.dds",
              "apt_pavement/pavement/r.dds", "apt_lines/taxilines.dds",
              "apt_lines/taxilines_NML.png"):
        (so / f).write_bytes(b"DDS ")
    (so / "library.txt").write_text(
        "A\n800\nLIBRARY\n"
        "EXPORT lib/airport/default_runways/asphalt/taxiway.pol apt_pavement/pavement/twy_a.pol\n"
        "EXPORT lib/airport/pavement/concrete_4D.pol apt_pavement/pavement/c.pol\n"
        "EXPORT lib/airport/default_runways/rubber.pol apt_pavement/pavement/r.pol\n"
        "EXPORT lib/airport/lines/1_single_taxi.lin apt_lines/1_single_taxi.lin\n"
        "EXPORT lib/airport/lines/51_single_taxi_b.lin apt_lines/51_single_taxi_b.lin\n"
        "EXPORT lib/g10/decals/a.dcl apt_pavement/pavement/c.pol\n", encoding="utf-8", newline="\n")
    other = tmp_path / "other.lin"
    other.write_text("A\n850\nLINE_PAINT\nTEXTURE x.png\n", encoding="utf-8", newline="\n")
    index = {"lib/airport/lines/1_single_taxi.lin": str(other)} if override else {}
    return str(root), (lambda p, _r: index.get(p))


def test_page_rows_and_laminar_first(tmp_path):
    root, look = _install(tmp_path, override=True)
    res = deck_skin.laminar_first(look)
    assert res("lib/airport/lines/1_single_taxi.lin", root).endswith("apt_lines/1_single_taxi.lin")
    pa = deck_skin.page_art("lib/airport/default_runways/asphalt/taxiway.pol", root, res)
    assert pa.weather.endswith("a_wm.png") and pa.surface == "asphalt"
    assert pa.decal_lib == "lib/g10/decals/a.dcl"      # resolves: this X-Plane reads decals
    pages = deck_line_art.line_pages("lib/airport/lines/1_single_taxi.lin", root, res)
    assert sorted(pages) == [1, 51] and pages[51].layers[0] == (328.0, 342.0, 356.0)
    assert pages[1].span_m(pages[1].layers[0]) == pytest.approx((8 * 12 / 1024, 8 * 12 / 1024))
    assert pages[1].weather_transparent and pages[1].decal_lib == "lib/g10/decals/m.dcl"


def test_surface_pages_follow_xplanes_shades():
    assert deck_pavement.surface_page(1, "taxi") == \
        "lib/airport/default_runways/asphalt/taxiway.pol"
    assert deck_pavement.surface_page(52, "runway") == \
        "lib/airport/default_runways/concrete_L/runway.pol"
    assert deck_pavement.surface_page(36, "taxi").split("/")[-2] == "asphalt_D3"
    assert deck_pavement.surface_page(3, "taxi") is None             # turf: no paved page
    apt = parse_airport_block(BLOCK)
    ring = Polygon([(17.004, 59.003), (17.006, 59.003), (17.006, 59.007), (17.004, 59.007)])
    assert deck_pavement.carried_surface(apt, ring, "taxi") == 1


def test_recipe_draws_the_carried_surface_line_art_and_no_tire_marks_of_ours(tmp_path):
    root, look = _install(tmp_path)
    pub = _pub()
    pub["decks"][0]["route"] = [[17.0, 59.005], [17.01, 59.005]]
    rec = gen.recipe(pub, _apt(tmp_path), "TEST", LAW, xplane_root=root, resolve_library=look)
    objs = {k: v.decode("ascii") for k, v in rec["files"].items() if k.endswith(".obj")}
    slab = objs[f"{gen.GENERATED_DIR}/deck_t.obj"]
    assert "TEXTURE xp_a_ALB.dds" in slab and "WEATHER xp_a_wm.png" in slab
    assert "ATTR_hard_deck asphalt" in slab and "ATTR_LOD 0 1200" in slab
    paint = objs[f"{gen.GENERATED_DIR}/deck_t_paint.obj"]
    assert "TEXTURE xp_taxilines.dds" in paint and "LIGHT_NAMED taxi_g " in paint
    # #2183 (2): the author laid nothing (no pack DSF read): no film at all
    assert sorted(objs) == [f"{gen.GENERATED_DIR}/deck_t.obj",
                            f"{gen.GENERATED_DIR}/deck_t_paint.obj"]
    for text in objs.values():
        _check_obj8(text)
        # owner sim read 1.0.555: an OBJ is not draped -- no film decal,
        # weather-transparency or polygon offset (deck_objects._FILM_STEP_M)
        for row in ("DECAL_LIB", "WEATHER_TRANSPARENT", "ATTR_poly_os"):
            assert row not in text
    # owner 2026-11-20T15:17Z: every overlay 1 mm over the top at most, on
    # top by draw order (the slab, then layer group objects 1, then 2)
    assert 0.0 < float(G.film_lift_m) <= 0.001 and 0.0 < float(G.paint_lift_m) <= 0.001
    assert "ATTR_layer_group objects 2" in paint and "ATTR_layer_group" not in slab
    assert {f"{gen.GENERATED_DIR}/xp_a_wm.png", f"{gen.GENERATED_DIR}/xp_taxilines.dds"} \
        <= set(rec["links"])
    assert all(os.path.isabs(p) for p in rec["links"].values())
