"""Twins of round 2 of the generated decks (#2131 the deck spans its cut,
the open approaches, a generated deck witnesses its bore's ends; #2132
X-Plane's own art).  Headless: ``tmp_path`` and a fake X-Plane install."""
from __future__ import annotations

import os
import types

import pytest
from auto_patch_v2.airport import deck_skin
from auto_patch_v2.airport import generated_pack as gen
from auto_patch_v2.airport.deck_obj8 import DeckSkin, DeckStrip, deck_obj8_text, overlay_obj8_text
from auto_patch_v2.airport.obj8 import parse_obj8
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.structures import DeckBridge
from auto_patch_v2.planar import deck_generated as dg
from auto_patch_v2.planar.deck_bridge import _bank_floor
from auto_patch_v2.planar.dual_width import widened_half_fn
from auto_patch_v2.planar.end_witness import EndWitness
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from test_generated_2123 import _apt, _pub  # noqa: E402  (sibling twin)

LAW = load_default()


def _road(line, half=3.5, parent=None):
    return dg._Road("-1", {"highway": "service"}, LineString(line), 80.0, half, parent)


def test_the_deck_spans_its_cut_floor_carries_the_road():
    """#2131: the bank the cut builds from each end line (depth / bank
    slope) stands beyond the floor, which carries the carriageway and its
    shoulders: a deck spanning the reach leaves the road on the floor."""
    road = _road([(0.0, -40.0), (0.0, 40.0)])
    run = dg._bank_run_m(LAW, (road,))
    g = LAW.tables.structures.deck_gen
    # a service road clears by [bridge] clearance_minimum_m (owner 2026-11-17T19:08Z)
    depth = float(g.thickness_m) + float(LAW.tables.structures.bridge.clearance_minimum_m)
    assert run == pytest.approx(depth / dg.generated_bank_slope(LAW))
    C = dg._cut_reach([road], LAW)
    reach = C.bounds[2]
    assert reach == pytest.approx(road.half_m + float(g.shoulder_m) + run)
    # a deck whose end lines stand on the reach: the floor holds the road + shoulders
    ring = box(-reach, -12.0, reach, 12.0)
    db = DeckBridge("o4gen_t", "objects/o4_generated/deck_t.obj", (),
                    tuple(ring.exterior.coords[:-1]), ((-reach, -12.0), (-reach, 12.0)),
                    ((reach, -12.0), (reach, 12.0)), 0.0, 0.0, -depth, 30.0,
                    floor_min_m=depth, witness=dg.GENERATED_WITNESS)
    floor = _bank_floor(db, float(LAW.tables.structures.tunnel.wall_gap_m), run)
    need = road.line.buffer(road.half_m + float(g.shoulder_m), cap_style="flat") \
        .intersection(ring.buffer(-1.0))
    assert floor is not None and need.difference(floor).area < 1e-6


def test_crest_keeps_the_run_along_the_road():
    st = ((0.0, 0.0), (0.0, 10.0), (0.0, 20.0), (3.0, 24.0), (8.0, 26.0))
    assert dg._crest(st, (0.0, 1.0)) == st[:3]
    assert dg._crest(st, None) == st and dg._crest(st[:2], (1.0, 0.0)) == st[:2]


def test_a_generated_deck_witnesses_both_ends_of_its_bore():
    ring = box(-20.0, -20.0, 20.0, 20.0)
    db = DeckBridge("o4gen_t", "r", (), tuple(ring.exterior.coords[:-1]), (), (), 0.0, 0.0,
                    -6.0, 30.0, witness=dg.GENERATED_WITNESS)
    pack = DeckBridge("obj1", "r", (), tuple(ring.exterior.coords[:-1]), (), (), 0.0, 0.0,
                      -6.0, 30.0)
    line = LineString([(-60.0, 0.0), (60.0, 0.0)])      # ends 40 m off the ring
    assert dg.covers_bore(db, line) and not dg.covers_bore(pack, line)
    assert not dg.covers_bore(db, LineString([(-60.0, 40.0), (60.0, 40.0)]))
    field = types.SimpleNamespace(airport=None, generated_decks=[db])
    assert "o4gen_t" in EndWitness(field, LAW).over(types.SimpleNamespace(line=line))
    assert EndWitness(types.SimpleNamespace(airport=None), LAW).over(
        types.SimpleNamespace(line=line)) is None


def test_widened_half_fn():
    assert widened_half_fn(None, 3.5, 1.5)(0.0) == (5.0, 5.0)
    assert widened_half_fn(lambda s: (2.0, 4.0), 3.5, 1.5)(7.0) == (3.5, 5.5)


def test_approach_pavement_beyond_a_mapped_tunnel_end():
    """#2131: pack pavement over the open road past the mapped portal
    leaves (up to the shortest lawful ramp); an underpass piece has none."""
    piece = box(-20.0, -20.0, 20.0, 20.0)
    P = box(-60.0, -30.0, 60.0, 30.0)
    tunnel = _road([(-30.0, 0.0), (30.0, 0.0)])
    on = types.SimpleNamespace(points=[(-30.0, 0.0), (-200.0, 0.0)])
    out = dg._approaches(piece, [tunnel], P, [on], LAW)
    g, tn = LAW.tables.structures.deck_gen, LAW.tables.structures.tunnel
    # the tunnel is a service road: its floor clears by [bridge] clearance_minimum_m
    run = (float(g.thickness_m) + float(LAW.tables.structures.bridge.clearance_minimum_m)) \
        / float(tn.ramp_grade)
    wide = 3.5 + float(g.shoulder_m) + 2 * float(tn.wall_gap_m) + float(tn.wall_band_width_m) \
        + float(g.bearing_m) + float(g.edge_margin_m)
    x0, _y0, x1, _y1 = unary_union(out).bounds
    assert x0 == pytest.approx(-30.0 - run - wide, abs=0.1)     # the road's first run
    assert x1 == pytest.approx(30.0 + wide, abs=0.1)            # the tunnel's own stretch
    assert unary_union(out).intersection(piece).area < 1e-6
    assert dg._approaches(piece, [tunnel], piece, [on], LAW) == []   # no pavement over it
    assert dg._approaches(piece, [tunnel._replace(parent=LineString([(0, 0), (1, 0)]))],
                          P, [on], LAW) == []


def _fake_install(tmp_path):
    root = tmp_path / "X-Plane"
    pav = root / "Resources" / "default scenery" / "sim objects" / "apt_pavement"
    (pav / "pavement").mkdir(parents=True)
    (pav / "textures").mkdir(parents=True)
    (pav / "pavement" / "c.pol").write_text(
        "A\n850\nDRAPED_POLYGON\nTEXTURE ../textures/c_ALB.png\n"
        "TEXTURE_NORMAL 1.0 ../textures/c_NML.png\nSCALE 22 44\n", encoding="utf-8")
    (pav / "pavement" / "r.pol").write_text(
        "A\n850\nDRAPED_POLYGON\nTEXTURE r.png\nSCALE 30 30\n", encoding="utf-8")
    for f in ("textures/c_ALB.dds", "textures/c_NML.png", "pavement/r.dds"):
        (pav / f).write_bytes(b"DDS ")
    return str(root), {"lib/airport/pavement/concrete_4D.pol": str(pav / "pavement" / "c.pol"),
                       "lib/airport/default_runways/rubber.pol": str(pav / "pavement" / "r.pol")}


def test_page_art_and_the_recipe_link_xplanes_art(tmp_path, monkeypatch):
    root, index = _fake_install(tmp_path)
    import auto_patch.agp_reader as agp
    monkeypatch.setattr(agp, "get_library_index", lambda _r: index)
    look = agp.resolve_library_path          # what the object stage hands in
    art = deck_skin.page_art("lib/airport/pavement/concrete_4D.pol", root, look)
    assert art.albedo.endswith("c_ALB.dds") and art.normal.endswith("c_NML.png")
    assert art.scale_m == (22.0, 44.0)
    assert deck_skin.page_art("lib/nothing.pol", root, look) is None
    assert deck_skin.page_art("lib/airport/pavement/concrete_4D.pol", None, look) is None
    assert deck_skin.page_art("lib/airport/pavement/concrete_4D.pol", root, None) is None
    assert deck_skin.install_root(os.path.join(root, "Custom Scenery", "P", "apt.dat")) == root
    assert deck_skin.link_name(art.albedo) == "xp_c_ALB.dds"
    # the slab in the page's art; paint + lights and the rubber as overlays
    rec = gen.recipe(_pub(), _apt(tmp_path), "TEST", LAW, xplane_root=root,
                     resolve_library=look)
    objs = {k: v.decode("ascii") for k, v in rec["files"].items() if k.endswith(".obj")}
    slab = objs[f"{gen.GENERATED_DIR}/deck_t.obj"]
    assert "TEXTURE xp_c_ALB.dds" in slab and "TEXTURE_NORMAL xp_c_NML.png" in slab
    assert "ATTR_hard_deck concrete" in slab and "LIGHT_NAMED" not in slab
    paint = objs[f"{gen.GENERATED_DIR}/deck_t_paint.obj"]
    assert "LIGHT_NAMED taxi_g " in paint and "ATTR_hard_deck" not in paint
    assert "TEXTURE xp_r.dds" in objs[f"{gen.GENERATED_DIR}/deck_t_rubber.obj"]
    assert {d["resource"] for d in rec["decks"]} == set(objs)
    # the art is LINKED into the pack and Restore removes the link only
    pack = tmp_path / "Pack"
    gen.write_files(str(pack), rec)
    link = pack / "objects" / "o4_generated" / "xp_c_ALB.dds"
    assert link.is_file() and os.path.realpath(link) == os.path.realpath(art.albedo)
    entry = {gen.RECORD_KEY: gen.record("sha", rec, {}, "now")}
    assert f"{gen.GENERATED_DIR}/xp_c_ALB.dds" in gen.files_of(entry)
    gen.remove(str(pack), gen.files_of(entry))
    assert not os.path.lexists(link) and os.path.isfile(art.albedo)


def test_skinned_slab_tiles_in_metres(tmp_path):
    ring = Polygon([(-10, -30), (10, -30), (10, 30), (-10, 30)])
    text = deck_obj8_text(ring, lambda x, z: 0.0, thickness_m=1.0, texture="a.png",
                          skin=DeckSkin("c.dds", (22.0, 44.0), "n.png"))
    p = tmp_path / "d.obj"
    p.write_text(text, encoding="ascii", newline="\n")
    assert parse_obj8(str(p)).hard_deck.shape[0] > 0 and "NORMAL_METALNESS" in text
    uvs = [tuple(map(float, r.split()[7:9])) for r in text.splitlines() if r.startswith("VT ")]
    assert max(v for _u, v in uvs) == pytest.approx(30.0 / 44.0, abs=1e-3)   # metres / SCALE
    assert max(u for u, _v in uvs) > 1.0               # the fascia runs on round the ring
    with pytest.raises(ValueError):
        deck_obj8_text(ring, lambda x, z: 0.0, thickness_m=1.0, texture="a.png",
                       skin=DeckSkin("c.dds", (22.0, 44.0)), lights=[object()])
    film = overlay_obj8_text(lambda x, z: 0.0, texture="r.dds",
                             strips=[DeckStrip(((0.0, -20.0), (0.0, 20.0)), 3.75, 3.75,
                                               (0.25, 0.5), 30.0, 0.01)])
    assert "ATTR_poly_os" not in film and "ATTR_hard_deck" not in film   # solid film (1.0.555)


def test_whole_cover_with_no_pavement_over_the_chain():
    """Round-1 defect (KPHX capture b2lvl): a chain missing the pavement gave
    an EMPTY LineString part and ``coords[0]`` raised IndexError."""
    parent = LineString([(0.0, 0.0), (50.0, 0.0)])
    road = _road([(10.0, 0.0), (20.0, 0.0)], parent=parent)
    way = types.SimpleNamespace(points=[(0.0, 0.0), (50.0, 0.0)])
    out, notes = dg._whole_cover([road], box(500.0, 500.0, 600.0, 600.0), 100.0, [way])
    assert out == [road] and notes == []


def test_a_deck_over_a_small_road_and_a_motorway_has_one_floor():
    """Owner 2026-11-17T19:08Z: 4.2 m over a small road, ``[tunnel]
    clearance_m`` over the rest; one deck over both is cut to the larger,
    and the small road's bank reaches that floor."""
    small = _road([(0.0, -40.0), (0.0, 40.0)])
    big = dg._Road("-2", {"highway": "motorway"}, LineString([(20.0, -40.0), (20.0, 40.0)]),
                   80.0, 5.0)
    th = float(LAW.tables.structures.deck_gen.thickness_m)
    st = LAW.tables.structures
    assert dg._depth_m(LAW, (small,)) == pytest.approx(th + float(st.bridge.clearance_minimum_m))
    assert dg._depth_m(LAW, (small, big)) == pytest.approx(th + float(st.tunnel.clearance_m))
    R = box(-60.0, -10.0, 80.0, 10.0)
    shared = dg._shared_depths([small, big], LAW, R)
    assert shared == {"-1": dg._depth_m(LAW, (big,)), "-2": dg._depth_m(LAW, (big,))}
    assert dg._cut_reach([small], LAW, shared).area > dg._cut_reach([small], LAW).area
