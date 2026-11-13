"""The automatic photo source per tile, the blend across provider edges
and the World pack's provider record (#2018, spec
``docs/specs/auto-imagery-provider-spec-20261113.md``).

Offline: the vendored ``Providers/`` and ``Extents/`` trees; casts from
synthetic images."""
import json
import os
import sys

import numpy
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _path in (os.path.join(REPO_ROOT, "src"), os.path.join(REPO_ROOT, "Providers")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import O4_Imagery_Provider_Blend as BLEND  # noqa: E402
import O4_Imagery_Provider_Cast as CAST  # noqa: E402
import O4_World_Imagery_Record as IREC  # noqa: E402
import O4_World_State_Text as WTEXT  # noqa: E402


@pytest.fixture(scope="module")
def auto():
    old_cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        import O4_Imagery_Auto as AUTO
        import O4_Imagery_Utils as IMG
        if not (IMG.providers_dict and IMG.combined_providers_dict):
            IMG.initialize_extents_dict()
            IMG.initialize_color_filters_dict()
            IMG.initialize_providers_dict()
            IMG.initialize_combined_providers_dict()
        AUTO.forget()
        yield AUTO
    finally:
        os.chdir(old_cwd)


# --- the choice (spec §1) ---------------------------------------------------
@pytest.mark.parametrize("tile, code", [
    ((48, 2), "FRorth"),      # inland France: the whole tile in the extent
    ((52, 5), "NL"),          # inland Netherlands
    ((46, 7), "CH"),          # inland Switzerland
    ((46, 6), "BI"),          # a border tile: no one national service
    ((48, -5), "BI"),         # open sea past the extent
    ((40, -100), "BI"),       # no national layer at all
])
def test_the_national_service_draws_only_a_tile_it_covers(auto, tile, code):
    assert auto.provider_for(*tile) == code


def test_the_zoom_is_raised_to_the_providers_floor(auto):
    """#2017: never a capture the provider serves differently (BI's
    ``min_source_zl`` is 13; FRorth declares none)."""
    assert auto.choose(46, 6, 12) == ("BI", 13)
    assert auto.choose(46, 6, 16) == ("BI", 16)
    assert auto.choose(48, 2, 12) == ("FRorth", 12)


def test_the_fly_photo_source_is_automatic_unless_one_is_chosen(monkeypatch, auto):
    from o4_engine import world_job_run as RUN
    values = {"default_zl": 16}
    monkeypatch.setattr(RUN, "_settings", lambda: dict(values))
    assert RUN.photo_source((48, 2)) == ("FRorth", 16)
    assert RUN.photo_source((46, 6)) == ("BI", 16)
    assert RUN.photo_source() == ("BI", 16)          # the estimates
    values.update(fly_photo_source="GO2", default_zl=17)
    assert RUN.photo_source((48, 2)) == ("GO2", 17)


# --- the blend (spec §3) ------------------------------------------------------
CAST_AB = (10.0, 0.0, -10.0)


def _cast(edge, a, b):
    """mean(b - a): B is 10 redder and 10 less blue than A everywhere."""
    sign = {("A", "B"): 1.0, ("B", "A"): -1.0}[(a, b)]
    return tuple(sign * v for v in CAST_AB)


def _facts(table, built=None):
    built = built or {}

    def facts(lat, lon):
        if (lat, lon) in built:
            return built[(lat, lon)]
        return BLEND.TileFacts(table.get((lat, lon), "A"))
    return facts


def _by_row(lat, lon):
    """B north of latitude 1, A south of it."""
    return BLEND.TileFacts("B" if lat >= 1 else "A")


def test_two_drapes_meet_halfway_across_a_provider_edge():
    north = {(1, 0): "B"}
    south = BLEND.plan(0, 0, "A", _facts(north), _cast)
    north_tile = BLEND.plan(1, 0, "B", lambda lat, lon: (
        _by_row(lat, lon) if (lat, lon) == (0, 0) else BLEND.TileFacts("B")), _cast)
    assert set(south.terms) == {"N"} and set(north_tile.terms) == {"S"}
    lon = numpy.array([0.25, 0.5, 0.75])
    edge = numpy.full(3, 1.0)
    a_side, b_side = south.at(edge, lon), north_tile.at(edge, lon)
    # A + f_A == B + f_B where B = A + cast: the seam closes at the middle
    numpy.testing.assert_allclose(a_side[1] - b_side[1], CAST_AB)
    numpy.testing.assert_allclose(a_side[1], (5.0, 0.0, -5.0))
    # nothing at the opposite edge, nothing at the corners (no tile beside
    # carries the same edge)
    numpy.testing.assert_allclose(south.at(numpy.zeros(3), lon), 0.0)
    numpy.testing.assert_allclose(south.at(numpy.array([1.0]), numpy.array([0.0])), 0.0)


def test_a_border_along_a_row_adds_no_step_between_its_tiles():
    """Tiles (0,0) and (0,1) both face B to the north: on their shared
    edge (lon 1) both evaluate the same field."""
    table = {(1, 0): "B", (1, 1): "B", (1, 2): "B", (1, -1): "B"}
    west, east = (BLEND.plan(0, lon, "A", _facts(table), _cast) for lon in (0, 1))
    lat = numpy.linspace(0.0, 1.0, 9)
    numpy.testing.assert_allclose(west.at(lat, numpy.full(9, 1.0)),
                                  east.at(lat, numpy.full(9, 1.0)))
    # and the corner carries the shared value, so the seam closes there too
    numpy.testing.assert_allclose(west.terms["N"][2], (5.0, 0.0, -5.0))


def test_a_tile_that_never_blends_is_closed_on_this_side():
    """A full or kept tile across the edge (built, no blend record): the
    drape takes the whole cast; one that blended: the rest of it."""
    table = {(1, 0): "B"}
    fixed = {(1, 0): BLEND.TileFacts("B", True, {})}
    whole = BLEND.plan(0, 0, "A", _facts(table, fixed), _cast)
    numpy.testing.assert_allclose(whole.terms["N"][1], CAST_AB)
    blended = {(1, 0): BLEND.TileFacts("B", True, {"S": {
        "start": [0, 0, 0], "mid": [-4.0, 0.0, 4.0], "end": [0, 0, 0]}})}
    rest = BLEND.plan(0, 0, "A", _facts(table, blended), _cast)
    numpy.testing.assert_allclose(rest.terms["N"][1], (6.0, 0.0, -6.0))


def test_a_built_neighbour_along_the_edge_gives_its_corner():
    table = {(1, 0): "B", (1, -1): "B"}
    beside = {(0, -1): BLEND.TileFacts("A", True, {"N": {
        "start": [0, 0, 0], "mid": [5, 0, -5], "end": [3.0, 0.0, -3.0]}})}
    blend = BLEND.plan(0, 0, "A", _facts(table, beside), _cast)
    assert blend.terms["N"][0] == (3.0, 0.0, -3.0)
    beside_fixed = {(0, -1): BLEND.TileFacts("A", True, {})}
    blend = BLEND.plan(0, 0, "A", _facts(table, beside_fixed), _cast)
    assert blend.terms["N"][0] == (0.0, 0.0, 0.0)


def test_no_edge_no_field_and_the_hook_adds_to_a_base():
    blend = BLEND.plan(0, 0, "A", _facts({}), _cast)
    assert not blend.terms and blend.field(0, 0, 16) is None

    class Tile:
        provider_blend = None
    base = numpy.ones((4, 4, 3), dtype=numpy.float32)
    assert BLEND.add_field(Tile(), base, 0, 0, 16) is base
    Tile.provider_blend = BLEND.plan(45, 2, "A", _facts({(46, 2): "B"}), _cast)
    import O4_Geo_Utils as GEO
    til_x, til_y = GEO.wgs84_to_orthogrid(45.99, 2.5, 16)  # under the north edge
    field = BLEND.add_field(Tile(), None, til_x, til_y, 16)
    assert field.shape == (256, 256, 3) and field[..., 0].max() > 4.0
    assert Tile.provider_blend.record()["N"]["toward"] == "B"


# --- the cast (spec §3) -----------------------------------------------------
def test_the_cast_is_the_mean_difference_on_the_pixels_both_show():
    first = numpy.full((64, 64, 3), 100.0)
    second = numpy.full((64, 64, 3), 112.0)
    second[:8] = 255.0                      # nodata white on one side: gated
    images = {"A": first, "B": second}

    def image_of(provider, _x, _y):
        return images[provider]
    squares = [(0, 0)]
    assert CAST.measure(squares, "A", "B", image_of) == (12.0, 12.0, 12.0)
    assert CAST.measure(squares, "B", "A", image_of) == (-12.0, -12.0, -12.0)
    assert CAST.measure(squares[:0], "A", "B", image_of) is None
    images["B"] = numpy.full((64, 64, 3), 255.0)
    assert CAST.measure(squares, "A", "B", image_of) is None
    images["B"] = numpy.full((64, 64, 3), 200.0)
    assert CAST.measure(squares, "A", "B", image_of) == (40.0, 40.0, 40.0)


def test_the_squares_straddle_the_edge():
    import O4_World_Drape as DRAPE
    squares = CAST.edge_squares(("H", 48, 2))
    assert len({y for _x, y in squares}) == 1 and 11 <= len(squares) <= 13
    for x, y in squares:
        south, _west, north, _east = DRAPE._bounds(x, y, 16)
        assert south <= 48 <= north
    for x, y in CAST.edge_squares(("V", 48, 2)):
        _south, west, _north, east = DRAPE._bounds(x, y, 16)
        assert west <= 2 <= east


def test_the_book_measures_an_edge_once(tmp_path):
    calls = []

    def image_of(provider, x, y):
        calls.append(provider)
        return numpy.full((64, 64, 3), 100.0 if provider == "A" else 90.0)
    book = CAST.CastBook(str(tmp_path / "casts.json"))
    assert book.cast(("H", 48, 2), "A", "B", image_of) == (-10.0, -10.0, -10.0)
    count = len(calls)
    again = CAST.CastBook(str(tmp_path / "casts.json"))
    assert again.cast(("H", 48, 2), "A", "B", image_of) == (-10.0, -10.0, -10.0)
    assert len(calls) == count


# --- the record (spec §4) ---------------------------------------------------
def test_the_record_travels_with_the_tile_into_the_pack(tmp_path):
    import O4_World_Pack as WP
    pack, staged = tmp_path / "pack", tmp_path / "staged"
    tile = WP.tile_name(53, -63)
    for sub in ("terrain", "textures"):
        (staged / sub / tile).mkdir(parents=True)
    (staged / "textures" / tile / "1_2_BI16.dds").write_bytes(b"x")
    dsf = staged / WP.dsf_relpath(53, -63)
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"x" * 5000)
    IREC.write_staged(str(staged), {"provider": "FRorth", "zl": 16})
    WP.swap_in(str(pack), str(staged), 53, -63)
    assert IREC.read(str(pack), 53, -63)["provider"] == "FRorth"
    os.remove(IREC.record_path(str(pack), 53, -63))
    assert IREC.read(str(pack), 53, -63) == {"provider": "BI", "zl": 16,
                                             "derived": True}


def test_dds_names_name_their_provider(tmp_path):
    folder = tmp_path / "textures" / "+31-110"
    folder.mkdir(parents=True)
    (folder / "26608_12736_USA216.dds").write_bytes(b"")
    assert IREC.from_textures(str(tmp_path), 31, -110) == {
        "provider": "USA2", "zl": 16, "derived": True}
    assert IREC.from_textures(str(tmp_path), 0, 0) == {}


def test_the_pane_and_readout_name_the_photo():
    from o4_engine import world_state as WS
    world = WS.WorldTile("drape", "xptb", 0.0, "", "", "/p.dsf", "FRorth")
    assert world.wire((1, 2))[8] == "FRorth"
    assert WTEXT.photo_text(world.fields()) == "photo: FRorth"
    assert WTEXT.pane_detail(world.fields()) == "built here · photo: FRorth"
    assert WTEXT.photo_text(WS.WorldTile("placeholder").fields()) == ""
    from O4_Qt_Cursor_Readout import readout_text
    assert readout_text(48.5, 2.5, "12.0 m", None, "photo: FRorth").endswith(
        "12.0 m · photo: FRorth")


def test_a_drape_blends_toward_the_pack_and_the_source(tmp_path, monkeypatch):
    """``world_blend.blend_for``: a neighbour the World pack holds is read
    from its record (built), any other from the job's photo source."""
    import O4_World_Pack as WP
    from o4_engine import world_blend as WB
    from o4_engine import world_commands as WORLD
    monkeypatch.setattr(WORLD, "pack_dir", lambda scenery: str(tmp_path / "pack"))
    monkeypatch.setattr(WP, "holds_tile", lambda scenery, lat, lon: (lat, lon) == (1, 0))
    IREC.write_staged(str(tmp_path / "staged"), {"provider": "B", "blend": {}})
    IREC.carry(str(tmp_path / "staged"), str(tmp_path / "pack"), 1, 0)
    monkeypatch.setattr(WB, "_caster", lambda: _cast)
    blend = WB.blend_for((0, 0), "A", str(tmp_path), lambda tile: ("A", 16))
    # the north tile is built without a blend: this drape closes it all
    numpy.testing.assert_allclose(blend.terms["N"][1], CAST_AB)
    assert set(blend.terms) == {"N"}
    assert WB.blend_for((0, 0), "A", str(tmp_path), lambda tile: ("A", 16)) is not None
    logs = []
    monkeypatch.setattr(WB, "_caster", lambda: None)   # a failure: no blend
    assert WB.blend_for((0, 0), "A", str(tmp_path), lambda t: ("A", 16),
                        logs.append) is None and logs
