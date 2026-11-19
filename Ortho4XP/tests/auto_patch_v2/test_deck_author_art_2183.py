"""Twins of #2183 items 1-3 (owner 2026-11-19T14:31Z; every generated
bridge): the carried surface read ON the taxi route (``deck_pavement``),
the pack author's films and lines on a deck (``deck_author_art`` through
``generated_pack.recipe``) and the edge paint of a ``110`` boundary the
apt.dat cut returns (``apt_edit``).  Headless: ``tmp_path``, a fake X-Plane
install and a hand-written DSF dump."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import apt_edit, deck_author_art, deck_pavement
from auto_patch_v2.airport import generated_pack as gen
from auto_patch_v2.airport.apt_dat import parse_airport_block
from auto_patch_v2.law.tables import load_default
from shapely.geometry import box
from test_deck_bridge_2132 import _check_obj8, _install  # noqa: E402  (sibling twins)
from test_generated_2123 import REGION, _apt, _pub  # noqa: E402
from test_pack_edits_2123 import BLOCK  # noqa: E402

LAW = load_default()
G = LAW.tables.structures.deck_gen
ROUTE = [[17.005, 59.0], [17.005, 59.01]]           # north-south across REGION


def test_boundary_edge_paint_inside_the_cut_is_returned():
    # the apron's east edge carries line 3 on its own boundary (no 120 row)
    region = box(17.009, 59.004, 17.011, 59.006)
    res = apt_edit.cut_block(BLOCK, region)
    edge = [d for d in res.dropped if d.line == 3]
    assert len(edge) == 1 and edge[0].light == 0
    lats = sorted(p[1] for p in edge[0].points)
    assert lats[0] == pytest.approx(59.004) and lats[-1] == pytest.approx(59.006)
    assert all(p[0] == pytest.approx(17.01) for p in edge[0].points)
    # an uncoded edge returns nothing
    west = apt_edit.cut_block(BLOCK, box(16.999, 59.004, 17.001, 59.006))
    assert not [d for d in west.dropped if d.feature_line == 1]


def _two_pavements(first: int, second: int):
    """A narrow FIRST pavement down the route over a wide SECOND one (the
    apt.dat layering is top-down: the first one listed is drawn on top)."""
    return parse_airport_block([
        "1    137 0 0 TEST Test Airport",
        f"110 {first} 0.25 0.00 Centre strip",
        "111 59.00000000 17.00480000", "111 59.00000000 17.00520000",
        "111 59.01000000 17.00520000", "113 59.01000000 17.00480000",
        f"110 {second} 0.25 0.00 Shoulders",
        "111 59.00000000 17.00000000", "111 59.00000000 17.01000000",
        "111 59.01000000 17.01000000", "113 59.01000000 17.00000000",
    ])


def test_the_surface_is_the_one_drawn_on_the_route():
    apt = _two_pavements(50, 22)
    assert deck_pavement.carried_surface(apt, REGION, "taxi") == 22          # area: the edge's
    assert deck_pavement.carried_surface(apt, REGION, "taxi", ROUTE) == 50   # the centreline's
    # the route off every pavement: the area rule
    off = [[18.0, 59.0], [18.0, 59.01]]
    assert deck_pavement.carried_surface(apt, REGION, "taxi", off) == 22


def _pack(tmp_path, pages: str):
    """The fake install, the pack's apt.dat, a DSF (its dump) and the
    pack's own pages; ``read_dump`` hands the dump."""
    root, look = _install(tmp_path)
    apt = _apt(tmp_path)
    pack = tmp_path / "Pack"
    (pack / "pols").mkdir()
    (pack / "pols" / "dirt.pol").write_text(
        "A\n850\nDRAPED_POLYGON\nTEXTURE dirt.png\nSCALE 10 20\nLAYER_GROUP markings 1\n",
        encoding="utf-8", newline="\n")
    (pack / "pols" / "base.pol").write_text(
        "A\n850\nDRAPED_POLYGON\nTEXTURE base.png\nSCALE 10 10\nLAYER_GROUP taxiways 0\n",
        encoding="utf-8", newline="\n")
    (pack / "pols" / "edge.lin").write_text(
        "A\n850\nLINE_PAINT\nTEXTURE edge.png\nTEX_WIDTH 256\nSCALE 8 4\n"
        "S_OFFSET 0 10 20 30\n", encoding="utf-8", newline="\n")
    for f in ("dirt.dds", "base.dds", "edge.dds"):
        (pack / "pols" / f).write_bytes(b"DDS ")
    dsf = pack / "Earth nav data" / "+50+010" / "+59+017.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"XPLNEDSF")
    dump = tmp_path / "dump.txt"
    dump.write_text(pages, encoding="utf-8", newline="\n")
    return root, look, apt, (lambda _p: str(dump))


def _poly(idx: int, lon0, lat0, lon1, lat1) -> list[str]:
    return [f"BEGIN_POLYGON {idx} 0 2", "BEGIN_WINDING",
            f"POLYGON_POINT {lon0} {lat0}", f"POLYGON_POINT {lon1} {lat0}",
            f"POLYGON_POINT {lon1} {lat1}", f"POLYGON_POINT {lon0} {lat1}",
            "END_WINDING", "END_POLYGON"]


HEAD = ["A", "800 written by DSFTool", "DSF2TEXT", "",
        "POLYGON_DEF pols/dirt.pol", "POLYGON_DEF pols/base.pol", "POLYGON_DEF pols/edge.lin"]
DUMP = "\n".join([
    *HEAD,
    # the dirt holds the route at BOTH ends
    *_poly(0, 17.003, 59.001, 17.007, 59.009),
    # the base holds the route at the south end only: not the author's
    # treatment of the taxiway on either side
    *_poly(1, 17.003, 59.001, 17.007, 59.0035),
    # an edge line along the deck
    "BEGIN_POLYGON 2 0 2", "BEGIN_WINDING",
    "POLYGON_POINT 17.0042 59.0", "POLYGON_POINT 17.0042 59.01",
    "END_WINDING", "END_POLYGON", ""])


def test_end_pages_need_both_ends():
    pages = deck_author_art.pack_pages(DUMP)
    assert [p.path for p in pages] == ["pols/dirt.pol", "pols/base.pol", "pols/edge.lin"]
    assert deck_author_art.end_pages(pages, REGION, ROUTE) == ["pols/dirt.pol"]
    assert deck_author_art.end_pages(pages, REGION, None) == []
    (line,) = deck_author_art.deck_lines(pages, REGION)
    assert line[0] == "pols/edge.lin"
    assert min(p[1] for p in line[1]) == pytest.approx(59.003)


def _recipe(tmp_path, dump: str):
    root, look, apt, read_dump = _pack(tmp_path, dump)
    pub = _pub()
    pub["decks"][0]["route"] = ROUTE
    return gen.recipe(pub, apt, "TEST", LAW, xplane_root=root, resolve_library=look,
                      read_dump=read_dump)


def test_recipe_draws_the_authors_film_and_line_and_nothing_else(tmp_path):
    rec = _recipe(tmp_path, DUMP)
    objs = {k: v.decode("ascii") for k, v in rec["files"].items() if k.endswith(".obj")}
    d = gen.GENERATED_DIR
    assert sorted(objs) == [f"{d}/deck_t.obj", f"{d}/deck_t_film0.obj",
                            f"{d}/deck_t_lines0.obj", f"{d}/deck_t_paint.obj"]
    film = objs[f"{d}/deck_t_film0.obj"]
    assert "TEXTURE xp_dirt.dds" in film and "ATTR_hard_deck" not in film
    vts = [tuple(map(float, r.split()[1:9])) for r in film.splitlines() if r.startswith("VT")]
    xs, us = [v[0] for v in vts], [v[6] for v in vts]
    # tiled at the page's SCALE (10 m across)
    assert (max(us) - min(us)) == pytest.approx((max(xs) - min(xs)) / 10.0, rel=1e-3)
    assert "TEXTURE xp_edge.dds" in objs[f"{d}/deck_t_lines0.obj"]
    for text in objs.values():
        _check_obj8(text)
    assert f"{d}/xp_dirt.dds" in rec["links"] and f"{d}/xp_base.dds" not in rec["links"]
    assert any("author film(s) ['dirt.dds']" in n for n in rec["notes"])
    # the films under the paint
    assert "ATTR_layer_group objects 1" in film
    assert "ATTR_layer_group objects 2" in objs[f"{d}/deck_t_paint.obj"]


def test_films_follow_the_layer_groups(tmp_path):
    both = "\n".join([*HEAD, *_poly(0, 17.003, 59.001, 17.007, 59.009),
                      *_poly(1, 17.003, 59.001, 17.007, 59.009), ""])
    rec = _recipe(tmp_path, both)
    d = gen.GENERATED_DIR
    # the base (taxiways) under the dirt (markings +1), though the DSF lists the dirt first
    assert "TEXTURE xp_base.dds" in rec["files"][f"{d}/deck_t_film0.obj"].decode()
    assert "TEXTURE xp_dirt.dds" in rec["files"][f"{d}/deck_t_film1.obj"].decode()
