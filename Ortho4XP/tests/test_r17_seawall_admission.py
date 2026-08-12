"""R17-3 — THE SEAWALL ADMISSION SET IS THE EMITTED GRADED COVERAGE.

Round 7 gave the wall its geometry: the patch coverage's outer boundary,
offset 0.5 m outward, intersected with water.  What it did NOT scope was
WHICH rings make up that coverage — the union handed to the law was
``patches_area``, every valid closed way in the patch, which includes
the OSM aerodrome BOUNDARY ribbon and the water-spanning bridge/road
ribbons.

VMMC IS THE CONTROL (standing R4 memory): its aerodrome boundary spans
real open sea, and a wall admitted along it would be a vertical wall
across a live channel.  So the admission set is now role-scoped to the
rings that carry a LAND altitude (``GRADED_COVERAGE_ROLES``), plus the
declared corridor (R17-2), and nothing else.

Headless: synthetic geometry, production's own functions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy
from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402
from auto_patch import flat_site as FS  # noqa: E402
from auto_patch import layout as LAYOUT  # noqa: E402

TILE_LAT, TILE_LON = 22, 113


class TestRoleVocabularyIsNotASecondSpelling:
    """The vector map spells the role literals for import weight; they
    must BE ``auto_patch.layout``'s roles, or the patch and the wall law
    are talking about different shapes."""

    def test_every_pavement_role_is_a_layout_role(self):
        known = {value for name, value in vars(LAYOUT).items()
                 if name.startswith("ROLE_") and isinstance(value, str)}
        assert VMAP.SEAWALL_PAVEMENT_ROLES <= known
        assert VMAP.GRADED_COVERAGE_ROLES - {
            VMAP.DECLARED_CORRIDOR_ROLE} <= known

    def test_the_named_land_roles_are_admitted(self):
        for role in (LAYOUT.ROLE_APRON, LAYOUT.ROLE_JUNCTION,
                     LAYOUT.ROLE_GRADED_STRIP, LAYOUT.ROLE_RUNWAY,
                     LAYOUT.ROLE_SERVICE_JUNCTION,
                     LAYOUT.ROLE_GROUNDSIDE_PAVEMENT):
            assert role in VMAP.GRADED_COVERAGE_ROLES

    def test_the_boundary_and_the_water_spanning_ribbons_are_not(self):
        for role in (LAYOUT.ROLE_BOUNDARY, LAYOUT.ROLE_SERVICE_ROAD,
                     LAYOUT.ROLE_BRIDGE_CAUSEWAY,
                     LAYOUT.ROLE_BRIDGE_TRENCH,
                     LAYOUT.ROLE_TAXIWAY_CLEARANCE,
                     LAYOUT.ROLE_RUNWAY_CLEARANCE, LAYOUT.ROLE_OLS_CUT):
            assert role not in VMAP.GRADED_COVERAGE_ROLES

    def test_the_declared_corridor_rides_with_pavement(self):
        assert VMAP.DECLARED_CORRIDOR_ROLE in VMAP.GRADED_COVERAGE_ROLES


class TestAdmissionAreaContract:
    def test_the_graded_coverage_wins_when_there_is_one(self):
        pavement = geometry.Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        graded = geometry.Polygon([(0, 0), (0.5, 0), (0.5, 0.5), (0, 0.5)])
        assert VMAP.seawall_admission_area(pavement, graded) is graded

    def test_a_roleless_patch_falls_back_to_the_whole_coverage(self):
        pavement = geometry.Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        assert VMAP.seawall_admission_area(
            pavement, geometry.Polygon()) is pavement
        assert VMAP.seawall_admission_area(pavement, None) is pavement


# ── the VMMC fixture: a boundary ring across open sea ────────────────


class _DEM:
    def alt_vec(self, way):
        return numpy.zeros((len(way), 1))


class _Tile:
    def __init__(self):
        self.lat = TILE_LAT
        self.lon = TILE_LON
        self.dem = _DEM()
        self.auto_patch = "All"


def _patch_file(patch_dir, rings):
    """``rings`` = [(role, [(lon, lat), ...])] — closed ways with roles."""
    lines = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<osm version='0.6' upload='true' generator='test'>"]
    node_id, way_id = -10, -100
    bodies = []
    for (role, ring) in rings:
        refs = []
        for (x, y) in ring[:-1]:
            lines.append(
                "  <node id='{}' action='modify' visible='true'"
                " lat='{:.10f}' lon='{:.10f}' />".format(node_id, y, x))
            refs.append(node_id)
            node_id -= 2
        body = ["  <way id='{}' action='modify' visible='true'>".format(
            way_id)]
        body += ["    <nd ref='{}' />".format(r) for r in refs + [refs[0]]]
        body.append("    <tag k='role' v='{}' />".format(role))
        body.append("    <tag k='cst_alt_abs' v='4' />")
        body.append("  </way>")
        bodies.append("\n".join(body))
        way_id -= 2
    lines += bodies
    lines.append("</osm>")
    (patch_dir / "VMMC_auto.patch.osm").write_text("\n".join(lines))


def _box(lon0, lat0, lon1, lat1):
    return [(lon0, lat0), (lon1, lat0), (lon1, lat1), (lon0, lat1),
            (lon0, lat0)]


def _run(tmp_path, monkeypatch, rings, declaration=None):
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    _patch_file(patch_dir, rings)
    monkeypatch.setattr(VMAP.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(FS, "declared_flat_corridors",
                        lambda value=None: declaration or {})
    vector_map = VECT.Vector_Map()
    return VMAP.include_patches(vector_map, _Tile())


# The channel: open sea between the apron (west) and the far shore.
SEA = VECT.ensure_MultiPolygon(geometry.Polygon(
    _box(0.0030, 0.0000, 0.0080, 0.0100)))
APRON = _box(113.0010, 22.0010, 113.0028, 22.0030)
# The aerodrome boundary spans the whole thing — apron AND channel.
BOUNDARY = _box(113.0005, 22.0005, 113.0090, 22.0090)


class TestBoundaryRibbonNeverAdmitsAWall:
    def test_the_boundary_is_a_land_cutter_but_not_a_wall(
            self, tmp_path, monkeypatch):
        (patches_area, _list, graded) = _run(
            tmp_path, monkeypatch,
            [("apron", APRON), ("boundary", BOUNDARY)])
        mid_channel = geometry.Point(0.0050, 0.0050)
        # R4 is untouched: the boundary ring is still in the LAND union.
        assert patches_area.contains(mid_channel)
        # R17-3: it is NOT in the wall admission set.
        assert not graded.contains(mid_channel)

    def test_no_wall_crosses_the_open_channel(self, tmp_path, monkeypatch):
        (patches_area, _list, graded) = _run(
            tmp_path, monkeypatch,
            [("apron", APRON), ("boundary", BOUNDARY)])
        before = VMAP.seawall_breaklines(patches_area, SEA, float(TILE_LAT))
        after = VMAP.seawall_breaklines(
            VMAP.seawall_admission_area(patches_area, graded), SEA,
            float(TILE_LAT))
        # The old admission walls the boundary ring where it crosses the
        # channel; the new one admits nothing there (the apron is dry).
        assert before
        assert after == []

    def test_pavement_that_does_touch_water_is_still_walled(
            self, tmp_path, monkeypatch):
        wet_apron = _box(113.0010, 22.0010, 113.0035, 22.0030)
        (patches_area, _list, graded) = _run(
            tmp_path, monkeypatch,
            [("apron", wet_apron), ("boundary", BOUNDARY)])
        lines = VMAP.seawall_breaklines(
            VMAP.seawall_admission_area(patches_area, graded), SEA,
            float(TILE_LAT))
        assert lines

    def test_the_tool_reads_the_same_role_vocabulary(self):
        """``tools/seawall_admission.py`` measures the wall coverage this
        law produces; it must select rings with PRODUCTION's vocabulary,
        never a copy (the census-wrapper precedent)."""
        import importlib.util

        path = (Path(__file__).resolve().parents[1] / "tools"
                / "seawall_admission.py")
        spec = importlib.util.spec_from_file_location("_sa_twin", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = path.read_text()
        assert "VMAP.GRADED_COVERAGE_ROLES" in source
        assert "VMAP.SEAWALL_PAVEMENT_ROLES" in source
        assert "VMAP.seawall_breaklines" in source
        assert "VMAP.sea_seed_areas" in source
        # and its metre scaling is a real length on a known chord.
        line = geometry.LineString([(0.0, 0.0), (0.0, 1.0)])
        assert abs(module.metre_length(line, 1.0) - module.DEG_M) < 1.0

    def test_the_declared_corridor_is_walled(self, tmp_path, monkeypatch):
        # A corridor across the channel: its long edges meet the water,
        # so they take walls (R17-2's third authority).
        corridor = (22.0040, 113.0030, 22.0048, 113.0080)
        (patches_area, _list, graded) = _run(
            tmp_path, monkeypatch, [("apron", APRON)],
            declaration={"VMMC": [corridor]})
        assert graded.contains(geometry.Point(0.0055, 0.0044))
        lines = VMAP.seawall_breaklines(
            VMAP.seawall_admission_area(patches_area, graded), SEA,
            float(TILE_LAT))
        assert lines
