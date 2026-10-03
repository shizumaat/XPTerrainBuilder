"""Twin for the ``.alt`` raster's FRAME (#238, lane ``altraster238``).

``DEM.write_to_file`` emits a headerless raw float32 raster, so a reader
has nothing in the file to tell it which patch of the world the samples
span.  ``tools/mesh_elevation_sampler.AltRaster`` used to assume the
historic viewfinder frame ([-0.01, 1.01]^2 on a 3673-square grid); a tile
whose base is a GeoTIFF or a densified inset grid does not have it -- KASE
+39-107 at ``elevation_level=10`` is 10834 square over about +-5.5
arc-seconds -- and reading it as the viewfinder's put every sample 58 m
away from the mesh it was baked into.

So the build now RECORDS its frame beside the raster and the reader takes
that record.  These twins assert both halves and, first, that they SEE
the defect: the same synthetic raster read in the viewfinder frame is
metres wrong where the sidecar frame is exact.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import O4_DEM_Utils as DEM_UTILS  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "mesh_elevation_sampler", ROOT / "tools" / "mesh_elevation_sampler.py")
mes = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(mes)


# The KASE class of frame: a densified grid posted a little way BEYOND
# the tile, which is exactly what the viewfinder constant gets wrong.
# Small enough to write in a test; the frame, not the grid size, is the
# thing under test.
BEYOND_DEGREES = 5.5 / 3600.0
PROBE_SIDE = 9
TILE_LAT, TILE_LON = 39, -107

# A field that is LINEAR in tile-relative degrees, so a correct bilinear
# read reproduces it EXACTLY at every point -- any frame error shows up
# as a plain elevation error rather than as interpolation noise.
BASE_METRES = 1700.0
PER_DEGREE_EAST = 1000.0
PER_DEGREE_NORTH = 3000.0


def _truth(x: float, y: float) -> float:
    """The synthetic surface at a tile-relative ``(x, y)``, in metres."""
    return BASE_METRES + PER_DEGREE_EAST * x + PER_DEGREE_NORTH * y


def _probe_frame() -> dict:
    """The non-viewfinder frame the probe raster is posted on."""
    return {
        "x0": -BEYOND_DEGREES, "y0": -BEYOND_DEGREES,
        "x1": 1.0 + BEYOND_DEGREES, "y1": 1.0 + BEYOND_DEGREES,
    }


def _probe_array(frame: dict, side: int = PROBE_SIDE) -> numpy.ndarray:
    """``_truth`` sampled on ``frame``'s grid, row 0 at y1 (the ``.alt``
    convention ``DEM.alt`` and ``Triangle4XP.altitude()`` share)."""
    out = numpy.zeros((side, side), dtype=numpy.float32)
    for row in range(side):
        y = frame["y1"] - row / (side - 1) * (frame["y1"] - frame["y0"])
        for column in range(side):
            x = frame["x0"] + column / (side - 1) * (
                frame["x1"] - frame["x0"])
            out[row, column] = _truth(x, y)
    return out


def _write_probe_alt(tmp_path: Path, *, frame: dict | None = None,
                     side: int = PROBE_SIDE, with_lat_lon: bool = True,
                     sidecar: bool = True) -> Path:
    """A probe ``.alt`` written by the ENGINE's own ``write_to_file``.

    A real ``DEM`` instance would have to load a raster off disk, so the
    object is built the way ``tests/test_approach_rings.py`` builds its
    own: ``object.__new__`` plus the attributes ``write_to_file`` reads.
    The method under test is the real one.
    """
    frame = dict(frame or _probe_frame())
    dem = object.__new__(DEM_UTILS.DEM)
    for key, value in frame.items():
        setattr(dem, key, value)
    dem.nxdem = dem.nydem = side
    dem.epsg = 4326
    dem.nodata = -32768
    dem.alt_dem = _probe_array(frame, side)
    if with_lat_lon:
        dem.lat, dem.lon = TILE_LAT, TILE_LON
    path = tmp_path / "Data+39-107.alt"
    dem.write_to_file(str(path))
    if not sidecar:
        Path(DEM_UTILS.alt_frame_sidecar_path(str(path))).unlink()
    return path


# =====================================================================
# THE WRITER: the build records its own frame beside the raster
# =====================================================================
def test_write_to_file_leaves_the_frame_beside_the_raster(tmp_path):
    """The sidecar names the grid that was WRITTEN, plus its context."""
    path = _write_probe_alt(tmp_path)
    sidecar = Path(DEM_UTILS.alt_frame_sidecar_path(str(path)))
    assert sidecar.name == "Data+39-107.alt.frame.json"

    raw = sidecar.read_bytes()
    assert b"\r\n" not in raw, "the sidecar must be written newline='\\n'"
    frame = json.loads(raw.decode("utf-8"))

    assert frame["schema"] == DEM_UTILS.ALT_FRAME_SCHEMA
    assert frame["nxdem"] == frame["nydem"] == PROBE_SIDE
    assert frame["x0"] == pytest.approx(-BEYOND_DEGREES)
    assert frame["x1"] == pytest.approx(1.0 + BEYOND_DEGREES)
    assert frame["y0"] == pytest.approx(-BEYOND_DEGREES)
    assert frame["y1"] == pytest.approx(1.0 + BEYOND_DEGREES)
    assert (frame["tile_lat"], frame["tile_lon"]) == (TILE_LAT, TILE_LON)
    assert frame["epsg"] == 4326


def test_the_sidecar_grid_follows_the_bytes_not_the_counters(tmp_path):
    """``tofile`` flattens ``alt_dem``, so the grid in the sidecar is the
    array's shape -- a stale ``nxdem``/``nydem`` pair would make every
    reader stride the file wrong."""
    frame = _probe_frame()
    dem = object.__new__(DEM_UTILS.DEM)
    for key, value in frame.items():
        setattr(dem, key, value)
    dem.alt_dem = _probe_array(frame, PROBE_SIDE)
    dem.nxdem = dem.nydem = 3673          # stale: the viewfinder's
    dem.lat, dem.lon, dem.epsg = TILE_LAT, TILE_LON, 4326
    path = tmp_path / "Data+39-107.alt"
    dem.write_to_file(str(path))

    written = json.loads(
        Path(DEM_UTILS.alt_frame_sidecar_path(str(path))).read_text(
            encoding="utf-8"))
    assert written["nxdem"] == written["nydem"] == PROBE_SIDE


def test_a_dem_without_tile_context_still_records_its_frame(tmp_path):
    """The FRAME keys are not optional; ``tile_lat``/``tile_lon`` are
    context, and a synthetic DEM that carries none still leaves a usable
    record rather than failing the write."""
    path = _write_probe_alt(tmp_path, with_lat_lon=False)
    frame = json.loads(
        Path(DEM_UTILS.alt_frame_sidecar_path(str(path))).read_text(
            encoding="utf-8"))
    assert all(key in frame for key in DEM_UTILS.ALT_FRAME_KEYS)
    assert "tile_lat" not in frame and "tile_lon" not in frame
    # ... and it is still resolvable, because the caller supplies the tile.
    resolved = DEM_UTILS.resolve_alt_frame(
        str(path), PROBE_SIDE, TILE_LAT, TILE_LON)
    assert resolved["x1"] == pytest.approx(1.0 + BEYOND_DEGREES)


# =====================================================================
# THE READER: the defect, then the fix
# =====================================================================
def test_the_viewfinder_frame_is_metres_wrong_on_this_raster(tmp_path):
    """The twin SEES #238 before it declares it gone.

    Same raster, same point: read in the viewfinder frame (the old
    hard-coded constant, still reachable as an explicit override) the
    elevation is wrong; read in the frame the build recorded it is exact.
    """
    path = _write_probe_alt(tmp_path)
    latitude, longitude = TILE_LAT + 0.3137, TILE_LON + 0.6213
    truth = _truth(longitude - TILE_LON, latitude - TILE_LAT)

    wrong = mes.AltRaster(str(path), TILE_LAT, TILE_LON,
                          extent=(-0.01, 1.01))
    assert abs(wrong.elevation_at(latitude, longitude) - truth) > 1.0

    right = mes.AltRaster(str(path), TILE_LAT, TILE_LON)
    assert right.elevation_at(latitude, longitude) == pytest.approx(
        truth, abs=1e-3)


def test_a_sidecar_frame_reads_back_exact(tmp_path):
    """Over the whole raster, not just one point: the recorded frame
    reproduces the linear surface everywhere a bilinear read can."""
    path = _write_probe_alt(tmp_path)
    raster = mes.AltRaster(str(path), TILE_LAT, TILE_LON)

    assert (raster.x0, raster.x1) == pytest.approx(
        (-BEYOND_DEGREES, 1.0 + BEYOND_DEGREES))
    assert (raster.y0, raster.y1) == pytest.approx(
        (-BEYOND_DEGREES, 1.0 + BEYOND_DEGREES))
    assert raster.side == PROBE_SIDE
    assert "frame.json" in raster.describe_frame()

    worst = 0.0
    for x in (0.0, 0.125, 0.5, 0.731, 1.0):
        for y in (0.0, 0.2, 0.5, 0.937, 1.0):
            read = raster.elevation_at(TILE_LAT + y, TILE_LON + x)
            worst = max(worst, abs(read - _truth(x, y)))
    assert worst < 1e-3, f"worst frame error {worst} m"


def test_the_viewfinder_grid_is_still_assumable_without_a_sidecar():
    """A raster built before this change, on the historic grid, keeps
    reading.  The frame is the ENGINE's own -- asked of
    ``build_combined_raster`` (``info_only``, so no download), never
    restated here -- so the fallback cannot drift from the build."""
    frame = DEM_UTILS.resolve_alt_frame(
        "/nonexistent/Data+39-107.alt",
        DEM_UTILS.viewfinder_alt_frame(TILE_LAT, TILE_LON)["nxdem"],
        TILE_LAT, TILE_LON)
    assert (frame["x0"], frame["x1"]) == pytest.approx((-0.01, 1.01))
    assert (frame["y0"], frame["y1"]) == pytest.approx((-0.01, 1.01))
    assert frame["nxdem"] == frame["nydem"] == 3673
    assert "no sidecar" in frame["origin"]


def test_a_sidecarless_non_viewfinder_grid_refuses(tmp_path):
    """The #238 case itself: no record, and not the one grid that may be
    assumed, so the extent is UNKNOWABLE -- refuse, never guess."""
    path = _write_probe_alt(tmp_path, sidecar=False)
    with pytest.raises(SystemExit) as refusal:
        mes.AltRaster(str(path), TILE_LAT, TILE_LON)
    message = str(refusal.value)
    assert "REFUSING" in message
    assert str(PROBE_SIDE) in message and "3673" in message
    assert "frame.json" in message


def test_a_non_square_raster_still_refuses(tmp_path):
    """The pre-existing refusal is untouched by the frame work."""
    path = tmp_path / "Data+39-107.alt"
    numpy.arange(7, dtype=numpy.float32).tofile(path)
    with pytest.raises(SystemExit, match="not a square raster"):
        mes.AltRaster(str(path), TILE_LAT, TILE_LON)


# =====================================================================
# A BROKEN OR FOREIGN SIDECAR: refuse, never fall back past it
# =====================================================================
def _rewrite_sidecar(path: Path, mutate) -> None:
    sidecar = Path(DEM_UTILS.alt_frame_sidecar_path(str(path)))
    frame = json.loads(sidecar.read_text(encoding="utf-8"))
    mutate(frame)
    with open(sidecar, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(frame, handle, indent=1, sort_keys=True)
        handle.write("\n")


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda f: f.pop("x1"), "carries no x1"),
        (lambda f: f.update(nxdem=512, nydem=512), "does not belong"),
        (lambda f: f.update(tile_lat=40), "wrong tile"),
        (lambda f: f.update(epsg=3857), "EPSG 3857"),
    ],
    ids=["missing-frame-key", "other-grid", "other-tile", "other-epsg"],
)
def test_a_sidecar_that_does_not_describe_this_raster_refuses(
    tmp_path, mutate, expected
):
    path = _write_probe_alt(tmp_path)
    _rewrite_sidecar(path, mutate)
    with pytest.raises(DEM_UTILS.AltFrameRefused, match=expected):
        DEM_UTILS.resolve_alt_frame(
            str(path), PROBE_SIDE, TILE_LAT, TILE_LON)


def test_an_unreadable_sidecar_refuses_rather_than_falls_back(tmp_path):
    """A present-but-broken record is the one case where falling back is
    worst: the build DID write a frame, so the viewfinder guess is known
    to be wrong."""
    path = _write_probe_alt(tmp_path)
    sidecar = Path(DEM_UTILS.alt_frame_sidecar_path(str(path)))
    with open(sidecar, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("{not json\n")
    with pytest.raises(DEM_UTILS.AltFrameRefused,
                       match="not readable as a frame sidecar"):
        DEM_UTILS.resolve_alt_frame(
            str(path), PROBE_SIDE, TILE_LAT, TILE_LON)


def test_an_explicit_extent_overrides_the_sidecar(tmp_path):
    """The escape hatch the refusal names: a caller who knows the frame
    out of band still gets it, and the raster says so."""
    path = _write_probe_alt(tmp_path, sidecar=False)
    raster = mes.AltRaster(str(path), TILE_LAT, TILE_LON,
                           extent=(-0.01, 1.01))
    assert (raster.x0, raster.y1) == pytest.approx((-0.01, 1.01))
    assert "caller-supplied" in raster.describe_frame()


# =====================================================================
# EVERY CONSUMER, NOT JUST THIS ONE: the frame has ONE implementation
# =====================================================================
def test_all_three_alt_consumers_go_through_one_reader():
    """``mesh_elevation_sampler --alt-raster``, ``patch_transect --alt``
    and ``mesh_region_tris --interp-alt-audit`` each construct
    ``AltRaster``; none carries a frame constant of its own, so #238 is
    fixed once.  (``mesh_inset_error`` reads the INSET raster, which is
    a different question -- it is not a consumer of the ``.alt``.)"""
    for name in ("mesh_elevation_sampler.py", "patch_transect.py",
                 "mesh_region_tris.py"):
        source = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "AltRaster(" in source, name
        for line in source.splitlines():
            code = line.split("#")[0]
            assert "ALT_RASTER_EXTENT" not in code, f"{name}: {line}"


def test_the_reader_and_the_writer_share_one_sidecar_name():
    """The filename convention is not spelled twice: the reader resolves
    through the engine rather than rebuilding the path."""
    assert DEM_UTILS.alt_frame_sidecar_path("/x/Data+39-107.alt") == (
        "/x/Data+39-107.alt" + DEM_UTILS.ALT_FRAME_SIDECAR_SUFFIX)
    source = (ROOT / "tools" / "mesh_elevation_sampler.py").read_text(
        encoding="utf-8")
    assert DEM_UTILS.ALT_FRAME_SIDECAR_SUFFIX not in source
