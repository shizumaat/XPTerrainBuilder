"""Twins for the base-tile fallback (issue #561).

The owner's tile +47-123 was refused twice on 2026-10-11 because the
Viewfinderpanoramas archive of NEIGHBOUR cell +48-123 timed out six
times.  The rule these twins hold: a TRANSPORT failure of the configured
base source is covered by the ranked fallback sources, at their own
cache paths, named in the log, tied to the configured neighbours along
the shared edge -- and nothing else is.

No network: the transports are fakes, the strategies write local files.
"""

import os

import numpy
import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_UI_Utils as UI
from auto_patch import provenance
from elevation_access import base_fallback, base_seam, warp
from elevation_access import registry as ea_registry
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.strategies import degree_cog_base_tile as ea_cog_base
from elevation_access.strategies import degree_named_cog as ea_degree_named_cog

_HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED_PROVIDERS_DIRECTORY = os.path.normpath(
    os.path.join(_HERE, "..", "Providers", "Elevation"))

CELL = (48, -123)
TRANSPORT_TEXT = ("the View elevation download of https://example.invalid/"
                  "dem3/M10.zip failed 6 times on the transport (last: "
                  "ReadTimeout)")


def _write_hgt(path, values):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    numpy.asarray(values, dtype=">i2").tofile(path)


class _Configured:
    """A configured base strategy with a scripted download."""

    calls = []
    outcome = "transport"

    def covers(self, definition, lat, lon):
        return True

    def download_url(self, definition, lat, lon):
        return "https://configured.invalid/%d/%d.zip" % (lat, lon)

    def tile_cache_path(self, definition, lat, lon):
        return FNAMES.elevation_data("View", lat, lon)

    def ensure_tile(self, definition, lat, lon, verbose=True):
        path = self.tile_cache_path(definition, lat, lon)
        if os.path.exists(path):
            return 1
        _Configured.calls.append((lat, lon))
        if _Configured.outcome == "transport":
            raise DEM.ElevationTransportRefused(TRANSPORT_TEXT)
        if _Configured.outcome == "mapping":
            raise DEM.ElevationDownloadRefused("no elevation for LAND cell")
        _write_hgt(path, numpy.full((5, 5), 100))
        return 1


class _Fallback:
    """A fallback strategy writing a flat tile at its own path."""

    calls = []
    failing = set()

    def covers(self, definition, lat, lon):
        return True

    def tile_cache_path(self, definition, lat, lon):
        return "%s_%s.hgt" % (FNAMES.base_file_name(lat, lon),
                              definition["code"])

    def ensure_tile(self, definition, lat, lon, verbose=True):
        path = self.tile_cache_path(definition, lat, lon)
        if os.path.exists(path):
            return 1
        _Fallback.calls.append((definition["code"], lat, lon))
        if definition["code"] in _Fallback.failing:
            raise RuntimeError("bucket unreachable")
        _write_hgt(path, numpy.full((5, 5), 200))
        return 1


CONFIGURED = {"code": "PRIMARY", "role": "base", "access_strategy": "_primary",
              "display_name": "Primary source"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A two-fallback registry over a private elevation directory."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "_primary", _Configured)
    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "_spare", _Fallback)
    providers = {
        "PRIMARY": CONFIGURED,
        "SPARE2": {"code": "SPARE2", "role": "base", "fallback_rank": "2",
                   "access_strategy": "_spare", "display_name": "Spare two"},
        "SPARE1": {"code": "SPARE1", "role": "base", "fallback_rank": "1",
                   "access_strategy": "_spare", "display_name": "Spare one"},
        "INSET": {"code": "INSET", "role": "airport_inset",
                  "fallback_rank": "1", "access_strategy": "_spare"},
    }
    monkeypatch.setattr(INSETS, "elevation_providers_dict", providers)
    monkeypatch.setattr(UI, "red_flag", False)
    _Configured.calls, _Configured.outcome = [], "transport"
    _Fallback.calls, _Fallback.failing = [], set()
    base_fallback.forget_unreachable_sources()
    yield providers
    base_fallback.forget_unreachable_sources()


def _ensure(cell=CELL):
    return base_fallback.ensure_tile_or_fallback(
        _Configured(), CONFIGURED, cell[0], cell[1], False,
        INSETS.elevation_providers_dict)


# ---------------------------------------------------------------- policy
def test_fallbacks_are_ranked_and_only_base_definitions(world):
    assert [d["code"] for d in base_fallback.fallback_definitions(world)] == [
        "SPARE1", "SPARE2"]


def test_a_transport_failure_takes_the_first_fallback_at_its_own_path(
        world, capsys):
    assert _ensure() == 1
    configured_path = FNAMES.elevation_data("View", *CELL)
    assert not os.path.exists(configured_path)
    (path, fallback) = base_fallback.cell_file(configured_path, *CELL, world)
    assert fallback["code"] == "SPARE1"
    assert path.endswith("N48W123_SPARE1.hgt") and path != configured_path
    assert _Fallback.calls == [("SPARE1", 48, -123)]
    said = capsys.readouterr().out
    # Never silent: the cell, the source used and the reason.
    assert "Primary source did not answer" in said
    assert "elevation cell +48-123 taken from Spare one instead" in said
    assert TRANSPORT_TEXT in said
    assert "asked again on the next build" in said


def test_a_cached_configured_file_is_used_and_nothing_is_asked(world):
    _write_hgt(FNAMES.elevation_data("View", *CELL), numpy.zeros((5, 5)) + 7)
    assert _ensure() == 1
    assert _Configured.calls == [] and _Fallback.calls == []
    assert base_fallback.cell_file(
        FNAMES.elevation_data("View", *CELL), *CELL, world)[1] is None


def test_only_a_transport_refusal_is_covered(world):
    # A mapping defect (#173) keeps refusing: it is not an outage.
    _Configured.outcome = "mapping"
    with pytest.raises(DEM.ElevationDownloadRefused) as caught:
        _ensure()
    assert not isinstance(caught.value, DEM.ElevationTransportRefused)
    assert _Fallback.calls == []


def test_the_second_fallback_is_asked_when_the_first_fails(world, capsys):
    _Fallback.failing = {"SPARE1"}
    assert _ensure() == 1
    assert [call[0] for call in _Fallback.calls] == ["SPARE1", "SPARE2"]
    assert "taken from Spare two instead" in capsys.readouterr().out


def test_every_source_failing_refuses_naming_each_one(world):
    _Fallback.failing = {"SPARE1", "SPARE2"}
    with pytest.raises(DEM.ElevationTransportRefused) as caught:
        _ensure()
    text = str(caught.value)
    assert "elevation cell +48-123 could not be fetched from any source" in text
    assert "REFUSING to build this tile on an all-zero" in text
    assert "Primary source: " + TRANSPORT_TEXT in text
    assert "Spare one: RuntimeError: bucket unreachable" in text
    assert "Spare two: RuntimeError: bucket unreachable" in text
    # ... and the 3x3 assembly still names the cell and its role (#121).
    assert isinstance(caught.value, DEM.ElevationDownloadRefused)


def test_the_next_build_asks_the_configured_source_again(world):
    assert _ensure() == 1
    base_fallback.forget_unreachable_sources()      # a new build
    _Configured.outcome = "ok"
    assert _ensure() == 1
    assert _Configured.calls == [CELL, CELL]
    configured_path = FNAMES.elevation_data("View", *CELL)
    # The fallback file is still on disk and is never read again.
    assert base_fallback.cell_file(configured_path, *CELL, world) == (
        configured_path, None)


def test_a_dead_host_is_asked_once_per_run_then_again_later(
        world, monkeypatch, capsys):
    assert _ensure((48, -123)) == 1
    assert _ensure((48, -122)) == 1
    assert _Configured.calls == [(48, -123)]
    assert "did not answer earlier in this run" in capsys.readouterr().out
    # The memory expires: a long-lived engine asks again on a later build.
    clock = base_fallback.time.monotonic()
    monkeypatch.setattr(
        base_fallback.time, "monotonic",
        lambda: clock + base_fallback.UNREACHABLE_MEMORY_S + 1)
    assert _ensure((48, -121)) == 1
    assert _Configured.calls == [(48, -123), (48, -121)]


def test_a_stopped_build_asks_no_fallback(world, monkeypatch):
    monkeypatch.setattr(UI, "red_flag", True)
    assert _ensure() == 0
    assert _Fallback.calls == []


def test_ensure_base_tile_goes_through_the_rule(world, monkeypatch):
    monkeypatch.setattr(INSETS, "resolve_base_definition",
                        lambda lat, lon, source, prefer_coarse=False:
                        CONFIGURED)
    assert INSETS.ensure_base_tile("View", *CELL, verbose=False) == 1
    assert _Fallback.calls == [("SPARE1", 48, -123)]


# ------------------------------------------------------------- transport
class _Session:
    def __init__(self, answer):
        self._answer = answer

    def get(self, url, timeout=None, allow_redirects=True):
        return self._answer()


class _Answer:
    def __init__(self, status):
        self.status_code = status
        self.headers = {}
        self.content = b""

    def close(self):
        pass


def test_retries_spent_on_the_transport_raise_the_coverable_refusal(
        monkeypatch):
    def _timeout():
        raise TimeoutError("Read timed out. (read timeout=10)")

    monkeypatch.setattr(UI, "red_flag", False)
    monkeypatch.setattr(DEM.requests, "Session", lambda: _Session(_timeout))
    monkeypatch.setattr(DEM.time, "sleep", lambda seconds: None)
    with pytest.raises(DEM.ElevationTransportRefused) as caught:
        DEM.http_request("https://example.invalid/dem3/M10.zip", "View")
    assert "failed %d times on the transport" % (
        DEM.HTTP_REQUEST_ATTEMPT_CAP) in str(caught.value)


def test_a_host_refusal_is_not_the_coverable_refusal(monkeypatch):
    monkeypatch.setattr(UI, "red_flag", False)
    monkeypatch.setattr(DEM.requests, "Session",
                        lambda: _Session(lambda: _Answer(403)))
    with pytest.raises(DEM.ElevationDownloadRefused) as caught:
        DEM.http_request("https://example.invalid/dem3/M10.zip", "View")
    assert not isinstance(caught.value, DEM.ElevationTransportRefused)


# ------------------------------------------------------------------ seam
def test_a_tied_side_equals_the_neighbour_and_fades_to_nothing():
    cell = numpy.full((9, 9), 200.0, dtype=numpy.float32)
    edge = numpy.linspace(100.0, 108.0, 9)
    closed = base_seam.tie_side(cell, "south", edge, feather=4)
    assert closed == pytest.approx(100.0)
    assert numpy.array_equal(cell[-1], edge.astype(numpy.float32))
    # Linear fade: full at the edge, three quarters one post in, none
    # beyond the feather.
    assert cell[-2, 0] == pytest.approx(200.0 - 0.75 * 100.0)
    assert numpy.all(cell[:5] == 200.0)


def test_void_posts_are_never_given_a_height():
    cell = numpy.full((6, 6), 50.0, dtype=numpy.float32)
    cell[0, 2] = -32768
    cell[1, 3] = -32768
    edge = numpy.full(6, 60.0)
    edge[4] = -32768
    base_seam.tie_side(cell, "north", edge, feather=3)
    assert cell[0, 2] == -32768 and cell[1, 3] == -32768
    assert cell[0, 4] == 50.0            # a void neighbour post ties nothing
    assert cell[0, 0] == 60.0


def test_four_sides_are_exact_and_the_first_tied_row_keeps_the_corner():
    cell = numpy.full((12, 12), 10.0, dtype=numpy.float32)
    edges = {"north": numpy.full(12, 20.0), "south": numpy.full(12, 30.0),
             "west": numpy.full(12, 40.0), "east": numpy.full(12, 50.0)}
    tied = base_seam.tie_cell_to_neighbours(cell, edges.get, feather=4)
    assert [side for (side, _closed) in tied] == list(base_seam.SIDES)
    assert numpy.all(cell[0] == 20.0) and numpy.all(cell[-1] == 30.0)
    # The columns equal their neighbours post for post, corners excepted:
    # two neighbours that disagree on a corner post cannot both have it.
    assert numpy.all(cell[1:-1, 0] == 40.0)
    assert numpy.all(cell[1:-1, -1] == 50.0)
    assert numpy.all(cell[5:7, 5:7] == 10.0)


def test_a_side_without_a_neighbour_or_on_another_grid_is_left_alone():
    cell = numpy.full((6, 6), 10.0, dtype=numpy.float32)
    edges = {"north": numpy.full(6, 20.0), "west": numpy.full(7, 99.0)}
    tied = base_seam.tie_cell_to_neighbours(cell, edges.get, feather=2)
    assert [side for (side, _closed) in tied] == ["north"]
    assert numpy.all(cell[2:] == 10.0)


def test_shared_edges_are_the_neighbours_facing_posts():
    neighbour = numpy.arange(16).reshape(4, 4)
    assert list(base_seam.shared_edge_of_neighbour(neighbour, "north")) == [
        12, 13, 14, 15]
    assert list(base_seam.shared_edge_of_neighbour(neighbour, "south")) == [
        0, 1, 2, 3]
    assert list(base_seam.shared_edge_of_neighbour(neighbour, "west")) == [
        3, 7, 11, 15]
    assert list(base_seam.shared_edge_of_neighbour(neighbour, "east")) == [
        0, 4, 8, 12]


def test_a_substituted_cell_is_read_tied_to_its_configured_neighbour(
        world, capsys):
    # Viewfinder holds the cell to the SOUTH; the home cell is a fallback.
    south = numpy.full((5, 5), 100)
    south[0] = [110, 111, 112, 113, 114]            # its north row
    _write_hgt(FNAMES.elevation_data("View", 47, -123), south)
    assert _ensure() == 1
    substitutions = []
    cell = DEM.read_base_cell(
        "View", *CELL, False, 5, substitutions=substitutions)[-1]
    assert list(cell[-1]) == [110, 111, 112, 113, 114]
    # A 5-post cell is shorter than the feather: the fade spans it.
    assert cell[0, 0] == pytest.approx(200.0 - 90.0 / 5)
    assert substitutions == [{
        "cell": "+48-123", "code": "SPARE1",
        "path": _Fallback().tile_cache_path(world["SPARE1"], *CELL),
        # the names the tile's closing note shows (RULINGS 2026-10-12e)
        "source": "View", "fallback": "Spare one"}]
    assert "tied to its south neighbour" in capsys.readouterr().out


def test_a_configured_cell_is_read_exactly_as_before(world):
    values = numpy.arange(25).reshape(5, 5)
    _write_hgt(FNAMES.elevation_data("View", *CELL), values)
    substitutions = []
    got = DEM.read_base_cell(
        "View", *CELL, False, 5, substitutions=substitutions)
    expected = DEM.read_elevation_from_file(
        FNAMES.elevation_data("View", *CELL), *CELL, False, 5)
    assert numpy.array_equal(got[-1], expected[-1]) and got[:8] == expected[:8]
    assert substitutions == []


# ------------------------------------------------------------ provenance
class _Tile:
    lat, lon = 47, -123

    def __init__(self, dem):
        self.dem = dem


class _Dem:
    source_path = ""


def test_an_ordinary_build_keeps_its_fingerprint(tmp_path):
    without = provenance.dem_fingerprint(_Tile(_Dem()))
    empty = _Dem()
    empty.base_substitutions = []
    assert provenance.dem_fingerprint(_Tile(empty)) == without


def test_a_substituted_cell_changes_the_fingerprint(tmp_path):
    path = str(tmp_path / "N48W123_SPARE1.hgt")
    _write_hgt(path, numpy.zeros((5, 5)))
    substituted = _Dem()
    substituted.base_substitutions = [
        {"cell": "+48-123", "code": "SPARE1", "path": path}]
    assert provenance.dem_fingerprint(_Tile(substituted)) != (
        provenance.dem_fingerprint(_Tile(_Dem())))


# --------------------------------------------------- the shipped registry
@pytest.fixture
def shipped():
    saved = INSETS.elevation_providers_dict
    yield INSETS.initialize_elevation_providers_dict(
        SHIPPED_PROVIDERS_DIRECTORY)
    INSETS.elevation_providers_dict = saved


def test_the_shipped_fallbacks_are_copernicus_30_then_90(shipped):
    assert [d["code"] for d in base_fallback.fallback_definitions(shipped)] == [
        "COPERNICUSGLO30BASE", "COPERNICUSGLO90BASE"]
    for code in ("COPERNICUSGLO30BASE", "COPERNICUSGLO90BASE"):
        assert shipped[code]["access_strategy"] == "degree_cog_base_tile"
        assert shipped[code]["enabled"] is False


def test_a_fallback_is_never_the_automatic_base_source(shipped):
    for prefer_coarse in (False, True):
        for (lat, lon) in ((48, -123), (36, -87), (46, 8), (-34, 151)):
            codes = [d["code"] for d in INSETS.select_base_definitions_auto(
                lat, lon, prefer_coarse=prefer_coarse)]
            assert not [c for c in codes if c.startswith("COPERNICUS")]


def test_the_fallback_cache_path_is_keyed_by_its_code(shipped, tmp_path,
                                                      monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    strategy = ea_cog_base.DegreeCogBaseTileStrategy()
    paths = {code: strategy.tile_cache_path(shipped[code], 48, -123)
             for code in ("COPERNICUSGLO30BASE", "COPERNICUSGLO90BASE")}
    assert paths["COPERNICUSGLO30BASE"].endswith(
        os.path.join("+40-130", "N48W123_COPERNICUSGLO30BASE.tif"))
    assert len(set(paths.values())) == 2
    assert FNAMES.viewfinderpanorama(48, -123) not in paths.values()


# ------------------------------------------------- the base-tile strategy
def test_the_cell_is_the_last_input_and_absent_neighbours_are_dropped(
        shipped, monkeypatch):
    absent = {"N47_00_W122"}                         # the south-east cell
    monkeypatch.setattr(
        ea_degree_named_cog.DegreeNamedCogStrategy, "_url_exists",
        lambda self, url: not any(token in url for token in absent))
    sources = ea_cog_base.DegreeCogBaseTileStrategy()._sources(
        shipped["COPERNICUSGLO30BASE"], 48, -123)
    assert [s.split("COG_10_")[1][:11] for s in sources] == [
        "N47_00_W123", "N48_00_W122", "N48_00_W123"]
    assert all(s.startswith("/vsicurl/https://copernicus-dem-30m.")
               for s in sources)
    absent.add("N48_00_W123")
    assert ea_cog_base.DegreeCogBaseTileStrategy()._sources(
        shipped["COPERNICUSGLO30BASE"], 48, -123) is None


def test_far_edges_are_filled_from_the_next_post():
    values = numpy.arange(16, dtype=numpy.float32).reshape(4, 4)
    values[-1, :2] = -32768
    values[1, -1] = -32768
    assert ea_cog_base.fill_far_edges_from_next_post(values) == 3
    assert list(values[-1, :2]) == [8.0, 9.0] and values[1, -1] == 6.0


@pytest.mark.skipif(not has_gdal, reason="needs GDAL")
def test_ensure_tile_lands_one_file_on_the_post_grid(shipped, tmp_path,
                                                     monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    asked = {}

    def _fake_warp(sources, bounds, resolution, destination, **keywords):
        asked.update(bounds=bounds, size=keywords["output_size"],
                     sources=list(sources))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        dataset = gdal.GetDriverByName("GTiff").Create(
            destination, 6, 6, 1, gdal.GDT_Float32)
        values = numpy.full((6, 6), 300.0, dtype=numpy.float32)
        values[-1, :] = -32768                       # no southern neighbour
        dataset.GetRasterBand(1).WriteArray(values)
        dataset.GetRasterBand(1).SetNoDataValue(-32768)
        dataset = None
        return True

    strategy = ea_cog_base.DegreeCogBaseTileStrategy()
    monkeypatch.setattr(strategy, "_sources",
                        lambda definition, lat, lon: ["/vsicurl/cell"])
    monkeypatch.setattr(ea_cog_base, "warp_vsicurl_sources_to_geotiff",
                        _fake_warp)
    definition = shipped["COPERNICUSGLO30BASE"]
    assert strategy.ensure_tile(definition, 48, -123, False) == 1
    path = strategy.tile_cache_path(definition, 48, -123)
    assert os.listdir(os.path.dirname(path)) == [os.path.basename(path)]
    assert asked["size"] == (3601, 3601)
    half_post = 0.5 / 3600
    assert asked["bounds"] == pytest.approx(
        (-123 - half_post, 48 - half_post, -122 + half_post, 49 + half_post))
    landed_file = gdal.Open(path)
    landed = landed_file.GetRasterBand(1).ReadAsArray()
    assert numpy.all(landed == 300.0)                # the void row is filled
    # A second call recycles: no warp, no probe.
    monkeypatch.setattr(ea_cog_base, "warp_vsicurl_sources_to_geotiff", None)
    assert strategy.ensure_tile(definition, 48, -123, False) == 1


@pytest.mark.skipif(not has_gdal, reason="needs GDAL")
def test_an_unpublished_cell_writes_nothing(shipped, tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    strategy = ea_cog_base.DegreeCogBaseTileStrategy()
    monkeypatch.setattr(strategy, "_sources",
                        lambda definition, lat, lon: None)
    assert strategy.ensure_tile(shipped["COPERNICUSGLO30BASE"], 0, -30) == 0
    assert not os.path.exists(str(tmp_path / "+00-030"))


@pytest.mark.skipif(not has_gdal, reason="needs GDAL")
def test_the_shared_warp_honours_a_fixed_output_grid(tmp_path):
    source = str(tmp_path / "source.tif")
    dataset = gdal.GetDriverByName("GTiff").Create(
        source, 4, 4, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((10.0, 0.25, 0.0, 51.0, 0.0, -0.25))
    dataset.SetProjection('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID['
                          '"WGS 84",6378137,298.257223563]],PRIMEM['
                          '"Greenwich",0],UNIT["degree",0.0174532925199433],'
                          'AUTHORITY["EPSG","4326"]]')
    dataset.GetRasterBand(1).WriteArray(
        numpy.arange(16, dtype=numpy.float32).reshape(4, 4))
    dataset = None
    destination = str(tmp_path / "out" / "cut.tif")
    assert warp.warp_vsicurl_sources_to_geotiff(
        [source], (10.0, 50.0, 11.0, 51.0), 30.0, destination,
        output_size=(4, 4))
    cut = gdal.Open(destination)
    assert (cut.RasterXSize, cut.RasterYSize) == (4, 4)
    assert numpy.array_equal(
        cut.GetRasterBand(1).ReadAsArray(),
        numpy.arange(16, dtype=numpy.float32).reshape(4, 4))


# ------------------------------------------------- a proxy's refusal (#562)
class ProxyError(ConnectionError):
    """Stands in for ``requests.exceptions.ProxyError``: the catalogue
    reads the class NAME along the MRO, never the message."""


def test_a_proxy_refusal_on_the_transport_is_named_by_its_class(monkeypatch):
    import O4_Tile_Failures as FAIL

    def _proxy():
        raise ProxyError("Tunnel connection failed: 400 Bad Request")

    monkeypatch.setattr(UI, "red_flag", False)
    monkeypatch.setattr(DEM.requests, "Session", lambda: _Session(_proxy))
    monkeypatch.setattr(DEM.time, "sleep", lambda seconds: None)
    with pytest.raises(DEM.ElevationTransportRefused) as caught:
        DEM.http_request("https://example.invalid/dem3/M10.zip", "View")
    assert FAIL.code_for_exception(caught.value) == "proxy_refused"

    def _timeout():
        raise TimeoutError("Read timed out.")

    monkeypatch.setattr(DEM.requests, "Session", lambda: _Session(_timeout))
    with pytest.raises(DEM.ElevationTransportRefused) as caught:
        DEM.http_request("https://example.invalid/dem3/M10.zip", "View")
    assert FAIL.code_for_exception(caught.value) == "elevation_download_failed"


def test_every_source_refused_by_a_proxy_says_so(world, monkeypatch):
    """The all-sources-failed refusal is the user's proxy or VPN when the
    configured source AND every fallback asked died on a ProxyError; one
    source failing another way keeps the ordinary message."""
    import O4_Tile_Failures as FAIL

    def proxied_primary(self, definition, lat, lon, verbose=True):
        refusal = DEM.ElevationTransportRefused(TRANSPORT_TEXT)
        refusal.failure_code = "proxy_refused"      # as http_request sets it
        raise refusal

    def proxied_spare(self, definition, lat, lon, verbose=True):
        raise ProxyError("Tunnel connection failed: 400 Bad Request")

    monkeypatch.setattr(_Configured, "ensure_tile", proxied_primary)
    monkeypatch.setattr(_Fallback, "ensure_tile", proxied_spare)
    with pytest.raises(DEM.ElevationTransportRefused) as caught:
        _ensure()
    assert FAIL.code_for_exception(caught.value) == "proxy_refused"
    (message,) = FAIL.fold([FAIL.record(
        FAIL.code_for_exception(caught.value), str(caught.value))], "+48-123")
    assert message["why"] == "Your proxy or VPN refused the connection."



def test_one_source_failing_another_way_keeps_the_ordinary_message(
        world, monkeypatch):
    import O4_Tile_Failures as FAIL

    def proxied_primary(self, definition, lat, lon, verbose=True):
        refusal = DEM.ElevationTransportRefused(TRANSPORT_TEXT)
        refusal.failure_code = "proxy_refused"
        raise refusal

    monkeypatch.setattr(_Configured, "ensure_tile", proxied_primary)
    _Fallback.failing = {"SPARE1", "SPARE2"}        # RuntimeError, no proxy
    with pytest.raises(DEM.ElevationTransportRefused) as caught:
        _ensure()
    assert FAIL.code_for_exception(caught.value) == "elevation_download_failed"
