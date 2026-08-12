"""R21 — LAND-CONNECTED CONTINUITY: the isthmus joins automatically.

Owner ruling 2026-08-12 ("LAND-CONNECTED CONTINUITY, NO DECLARATIONS"):
where an airport's flat-site family — the constant CORE and the
claimed-object clusters the datum gate admitted — stands on ONE
SEA-BOUNDED land component, the land BETWEEN its members grades with it.
No per-tile declaration; the same measurement for every airport and
every user.  R17-2's ``flat_site_declared_corridors`` retires with it
(``tests/test_r21_corridor_retirement.py``), and this file carries the
acceptance those corridor twins carried: the causeway grades flat at Z0,
the water beside it stays where it is — new mechanism, same claim.

THE THREE BOUNDS, one test class each, because each ALONE must stop a
mainland from flattening:
  1. ISLAND    — the component may not reach the working frame.
  2. FAMILY    — two members of one airport, or there is nothing to be
                 continuous with.
  3. BETWEEN   — only land touching TWO members, clipped to their hull;
                 never the whole component.

Headless: the land/sea partition is injected, so no OSM cache, no
network and no X-Plane install are touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy
from shapely import geometry, ops

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
from auto_patch import flat_site_mode as FSM  # noqa: E402

TILE_LAT, TILE_LON = 22, 113

# ── THE FIXTURE: VHHH in miniature ───────────────────────────────────
#: The airport's island, the ISTHMUS that joins it to the east island,
#: and the east island.  One land component, sea all round it.
ISLAND = geometry.box(0.30, 0.34, 0.40, 0.40)
ISTHMUS = geometry.box(0.40, 0.365, 0.44, 0.372)
EAST = geometry.box(0.44, 0.35, 0.50, 0.39)
#: A second island the airport claims nothing on, across open water.
FARAWAY = geometry.box(0.80, 0.80, 0.86, 0.86)
#: The MAINLAND: a land component that reaches the tile frame.  Nothing
#: on it may ever flatten (the twin the ruling names, HECA's class).
MAINLAND = geometry.box(0.0, 0.0, 0.60, 0.20)
LAND = ops.unary_union([ISLAND, ISTHMUS, EAST, FARAWAY, MAINLAND])

#: The family: the core rectangle inside the airport's island and the
#: claimed-object cluster over the east island.  NEITHER covers the
#: isthmus — that is the ground this law is about.
CORE = (0.31, 0.35, 0.39, 0.39)
EAST_CLUSTER = (0.45, 0.355, 0.49, 0.385)
Z0 = 7.315


class _Dem:
    """A working grid at ~1/1200° over the tile, flat at 3 m."""

    def __init__(self, n=1201, base_m=3.0):
        self.nxdem = self.nydem = n
        self.x0, self.y0, self.x1, self.y1 = 0.0, 0.0, 1.0, 1.0
        self.nodata = -32768.0
        self.alt_dem = numpy.full((n, n), base_m, dtype=numpy.float32)

    def alt_vec(self, way):
        way = numpy.asarray(way)
        step = (self.x1 - self.x0) / (self.nxdem - 1)
        columns = numpy.clip(((way[:, 0] - self.x0) / step).astype(int),
                             0, self.nxdem - 1)
        rows = numpy.clip(((self.y1 - way[:, 1]) / step).astype(int),
                          0, self.nydem - 1)
        return self.alt_dem[rows, columns].astype(float)

    def at(self, lat, lon):
        step = (self.x1 - self.x0) / (self.nxdem - 1)
        return float(self.alt_dem[int(round((self.y1 - (lat - TILE_LAT))
                                            / step)),
                                  int(round((lon - TILE_LON) / step))])


class _Tile:
    airport_elevation_inset_feather_m = 60.0

    def __init__(self):
        self.lat, self.lon = TILE_LAT, TILE_LON
        self.dem = _Dem()


def _entry(kind, box, icao="VHHH", z0=Z0):
    return {"icao": icao, "kind": kind, "z0_m": z0,
            "extent_tile_degrees": list(box)}


def _family(core=CORE, cluster=EAST_CLUSTER, icao="VHHH", z0=Z0):
    entries = [_entry(FSM.CORE_INSET_KIND, core, icao, z0)]
    if cluster is not None:
        entries.append(_entry(FSM.CLUSTER_INSET_KIND, cluster, icao, z0))
    return entries


def _with_land(monkeypatch, land=LAND):
    monkeypatch.setattr(
        VMAP, "cached_tile_land_area",
        lambda tile: (None if land is None
                      else VMAP.VECT.ensure_MultiPolygon(land)))


def _regions(monkeypatch, stamped, land=LAND):
    _with_land(monkeypatch, land)
    return FSM.island_continuity_regions(_Tile(), stamped)


class TestTheIslandBound:
    """BOUND 1 — sea-bounded component, or nothing."""

    def test_the_airports_island_carries_an_isthmus(self, monkeypatch):
        regions = _regions(monkeypatch, _family())
        assert len(regions) == 1
        assert regions[0]["icao"] == "VHHH"
        assert regions[0]["z0_m"] == Z0
        assert regions[0]["polygon"].intersects(ISTHMUS)

    def test_a_MAINLAND_family_is_refused(self, monkeypatch):
        """THE STRUCTURAL GATE, and the HECA class: a component that
        reaches the working frame is mainland and never flattens, however
        many footprints stand on it."""
        stamped = _family(core=(0.05, 0.05, 0.15, 0.15),
                          cluster=(0.40, 0.05, 0.50, 0.15), icao="HECA")
        assert _regions(monkeypatch, stamped) == []

    def test_a_tile_with_no_sea_at_all_is_mainland(self, monkeypatch):
        """An inland tile's land is the whole frame — one frame-touching
        component.  HECA has no coastline data to read and must come out
        the same way as a tile whose coastline says "all land"."""
        whole = geometry.box(0.0, 0.0, 1.0, 1.0)
        assert _regions(monkeypatch, _family(), land=whole) == []

    def test_NO_LAND_DATA_is_inert_and_never_a_guess(self, monkeypatch):
        """No coastline cache on disk: the law refuses rather than
        downloading (an implicit fetch into the shared data repo) or
        guessing which ground is land."""
        assert _regions(monkeypatch, _family(), land=None) == []


class TestTheFamilyBound:
    """BOUND 2 — two members of ONE airport."""

    def test_a_single_member_family_has_no_isthmus(self, monkeypatch):
        assert _regions(monkeypatch, _family(cluster=None)) == []

    def test_two_DIFFERENT_airports_are_not_one_family(self, monkeypatch):
        """VHHH's core and VMMC's cluster do not grade into each other:
        they carry different Z0s, and a family is an airport's."""
        stamped = (_family(cluster=None)
                   + [_entry(FSM.CLUSTER_INSET_KIND, EAST_CLUSTER,
                             icao="VMMC", z0=6.10)])
        assert _regions(monkeypatch, stamped) == []

    def test_a_REFUSED_cluster_is_not_a_member(self, monkeypatch):
        """The family is what LANDED.  A cluster the R11-2 datum gate
        refused is not stamped, so it joins nothing — the refusal cannot
        be walked around through this law."""
        assert _regions(monkeypatch, _family(cluster=None)) == []

    def test_a_member_on_ANOTHER_island_does_not_join(self, monkeypatch):
        """A cluster across open water is not connected: the law reads
        land, never proximity."""
        stamped = _family(cluster=(0.81, 0.81, 0.85, 0.85))
        assert _regions(monkeypatch, stamped) == []


class TestTheBetweenBound:
    """BOUND 3 — connecting land only, never the component."""

    def test_the_WHOLE_COMPONENT_does_not_flatten(self, monkeypatch):
        region = _regions(monkeypatch, _family())[0]
        island = ops.unary_union([ISLAND, ISTHMUS, EAST])
        assert region["polygon"].area < island.area * 0.5
        assert region["island_area_km2"] > region["area_km2"] * 2

    def test_land_hanging_off_ONE_member_is_not_connecting(self,
                                                           monkeypatch):
        """A spur reachable only through one footprint joins nothing —
        it is not BETWEEN anything."""
        spur = geometry.box(0.26, 0.36, 0.30, 0.38)
        land = ops.unary_union([LAND, spur])
        region = _regions(monkeypatch, _family(), land=land)[0]
        assert not region["polygon"].intersects(spur.buffer(-1e-6))

    def test_land_OUTSIDE_the_members_hull_is_not_connecting(self,
                                                             monkeypatch):
        """"Between" is the members' hull.  A lobe of the same island far
        outside it keeps the real surface, and the clip is REPORTED."""
        lobe = geometry.box(0.34, 0.40, 0.38, 0.46)
        land = ops.unary_union([LAND, lobe])
        region = _regions(monkeypatch, _family(), land=land)[0]
        assert not region["polygon"].intersects(lobe.buffer(-1e-6))

    def test_a_DEAD_END_arm_between_the_members_is_not_connecting(
            self, monkeypatch):
        """The two-member rule, isolated.

        The island has two arms reaching east out of the core: the NORTH
        one reaches the east island (it connects), the SOUTH one stops in
        open water (it does not).  Both lie BETWEEN the footprints, so
        the hull clip cannot answer this — only "does this piece touch
        two members" can.  A dead-end arm graded to Z0 would be a flat
        pier standing in the sea.
        """
        west = geometry.box(0.30, 0.34, 0.40, 0.40)
        north_arm = geometry.box(0.40, 0.3780, 0.44, 0.3820)
        south_arm = geometry.box(0.40, 0.3580, 0.43, 0.3620)   # dead end
        east = geometry.box(0.44, 0.35, 0.50, 0.39)
        land = ops.unary_union([west, north_arm, south_arm, east, MAINLAND])
        core = (0.29, 0.33, 0.41, 0.41)          # covers the west blob
        cluster = (0.45, 0.355, 0.49, 0.385)
        region = _regions(
            monkeypatch, _family(core=core, cluster=cluster), land=land)[0]
        assert region["polygon"].intersects(north_arm.buffer(-1e-6))
        assert not region["polygon"].intersects(south_arm.buffer(-1e-6))

    def test_the_faraway_island_is_never_touched(self, monkeypatch):
        region = _regions(monkeypatch, _family())[0]
        assert not region["polygon"].intersects(FARAWAY)

    def test_the_MAINLAND_is_never_touched(self, monkeypatch):
        region = _regions(monkeypatch, _family())[0]
        assert not region["polygon"].intersects(MAINLAND)


class TestTheBake:
    """The masked constant inset — Z0 on the land, the base elsewhere."""

    def _bake(self, monkeypatch, stamped=None, land=LAND):
        _with_land(monkeypatch, land)
        tile = _Tile()
        stamped = list(stamped if stamped is not None else _family())
        INSETS._bake_island_continuity(tile, stamped, 60.0)
        return tile, stamped

    def test_the_isthmus_land_is_baked_to_Z0(self, monkeypatch):
        tile, _ = self._bake(monkeypatch)
        assert abs(tile.dem.at(TILE_LAT + 0.3685, TILE_LON + 0.42)
                   - Z0) < 0.01

    def test_the_water_BESIDE_the_isthmus_keeps_the_base_surface(
            self, monkeypatch):
        """THE R17-2 ACCEPTANCE, new mechanism: the channel outside the
        connecting land is not raised.  The mask is what makes this true
        — a bounding-box inset would have flattened the water with it."""
        tile, _ = self._bake(monkeypatch)
        for (lat, lon) in ((TILE_LAT + 0.380, TILE_LON + 0.42),
                           (TILE_LAT + 0.355, TILE_LON + 0.42),
                           (TILE_LAT + 0.3685, TILE_LON + 0.60)):
            assert abs(tile.dem.at(lat, lon) - 3.0) < 0.01

    def test_the_provenance_names_the_isthmus(self, monkeypatch):
        _tile, stamped = self._bake(monkeypatch)
        kinds = [entry["kind"] for entry in stamped]
        assert kinds[-1] == FSM.ISTHMUS_INSET_KIND
        entry = stamped[-1]
        assert entry["z0_m"] == Z0
        assert entry["icao"] == "VHHH"
        assert entry["feather_m"] == 0.0
        assert entry["members"] == 2
        assert entry["extent_area_km2"] > 0
        # The base-vs-Z0 offset is ATTRIBUTION, carried on the stamp so a
        # reader can see how far the ground moved.
        assert abs(entry["base_offset_m"] - (3.0 - Z0)) < 0.01

    def test_the_MAINLAND_bake_is_a_no_op(self, monkeypatch):
        """The byte-identity twin: on a mainland family nothing is baked
        and nothing is stamped — the surface the build gets is the one it
        would have got with this law absent."""
        _with_land(monkeypatch, LAND)
        tile = _Tile()
        before = tile.dem.alt_dem.copy()
        stamped = _family(core=(0.05, 0.05, 0.15, 0.15),
                          cluster=(0.40, 0.05, 0.50, 0.15), icao="HECA")
        INSETS._bake_island_continuity(tile, stamped, 60.0)
        assert numpy.array_equal(tile.dem.alt_dem, before)
        assert [entry["kind"] for entry in stamped] == [
            FSM.CORE_INSET_KIND, FSM.CLUSTER_INSET_KIND]

    def test_the_masked_inset_holds_Z0_only_inside_the_polygon(self):
        """The mask itself: posts inside the polygon carry Z0, posts
        outside carry nodata — which is what ``_bake_one_inset`` already
        means by "the base keeps its value"."""
        inset = INSETS._MaskedConstantInset(
            ISTHMUS, Z0, 1.0 / 1200, 1.0 / 1200, label="probe")
        values = set(numpy.unique(inset.alt_dem).tolist())
        assert values <= {numpy.float32(Z0).item(), inset.nodata}
        assert inset.mask_valid_posts > 0
        # A polygon with a HOLE keeps its hole (a lagoon inside the
        # isthmus is water, and water is not graded).
        holed = ISTHMUS.difference(geometry.box(0.41, 0.3675, 0.42, 0.370))
        holed_inset = INSETS._MaskedConstantInset(
            holed, Z0, 1.0 / 1200, 1.0 / 1200, label="probe")
        assert holed_inset.mask_valid_posts < inset.mask_valid_posts


class TestTheVocabularyIsNotSpelledTwice:
    """Two spellings of one kind would be two laws."""

    def test_the_vector_map_reads_the_isthmus_as_the_airports_island(self):
        assert FSM.ISTHMUS_INSET_KIND in VMAP.AIRPORT_ISLAND_INSET_KINDS
        assert FSM.CORE_INSET_KIND in VMAP.AIRPORT_ISLAND_INSET_KINDS
        assert (VMAP.AIRPORT_ISLAND_CLUSTER_INSET_KIND
                == FSM.CLUSTER_INSET_KIND)

    def test_the_isthmus_joins_the_wall_admission(self, monkeypatch):
        """The wall half of the ruling: the isthmus is inset footprint,
        so its shoreline is admitted exactly as the core's is."""
        sea = geometry.box(0.0, 0.0, 1.0, 1.0).difference(LAND)
        coverage = geometry.box(0.33, 0.36, 0.37, 0.38)

        class _StampDem:
            def __init__(self, entries):
                self.synthetic_flat_site_provenance = entries

        class _StampTile:
            lat, lon = TILE_LAT, TILE_LON

            def __init__(self, entries):
                self.dem = _StampDem(entries)

        with_isthmus = _StampTile(_family() + [
            _entry(FSM.ISTHMUS_INSET_KIND, (0.39, 0.360, 0.46, 0.378))])
        land = VMAP.coastline_wall_admission(
            with_isthmus, sea, graded_area=coverage)
        assert land.intersects(ISTHMUS)
