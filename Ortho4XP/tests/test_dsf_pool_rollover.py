"""A DSF band pool that outgrows 16 bits rolls over to an overflow pool (#2092).

LICJ tile +38+013 in ``default_xplane`` mode died in step 4 with
``OverflowError: unsigned short is greater than maximum``: the default-land
band copies a node once per terrain that uses it, so a 50,000-node geometric
pool can need more than 65,536 band points, and a point index is a 16-bit
word.  ``O4_DSF_Pools.DsfPointPools.slot`` now opens an overflow pool (same
planes, same scale) when one is full; every emitter in ``build_dsf`` takes its
slots there.
"""
import queue

import O4_Default_Terrain_Map as DTM
import O4_DSF_Pools as POOLS
import O4_DSF_Utils as DSF
import test_dsf_texture_modes as MODES

# The synthetic-mesh fixtures of the texture-mode suite, reused.
stub_elevation = MODES.stub_elevation


def test_slot_rolls_over_at_sixteen_bits():
    pools = POOLS.DsfPointPools(2, [7, 7, 5, 5])
    slots = [pools.slot(3) for _ in range(POOLS.DsfPointPools.MAX_POINTS + 10)]
    assert slots[POOLS.DsfPointPools.MAX_POINTS - 1] == (3, POOLS.DsfPointPools.MAX_POINTS - 1)
    assert slots[POOLS.DsfPointPools.MAX_POINTS] == (4, 0)
    assert slots[-1] == (4, 9)
    assert pools.length == [0, 0, 0, POOLS.DsfPointPools.MAX_POINTS, 10]
    # The overflow pool keeps its parent's planes and geometric pool.
    assert pools.plane[4] == 5 and pools.geometric[4] == 1
    # Other bases are untouched and still write into their own pool.
    assert pools.slot(2) == (2, 0)


def test_unfilled_pools_open_no_overflow():
    pools = POOLS.DsfPointPools(3, [7] * 9)
    for base in range(9):
        for _ in range(100):
            pools.slot(base)
    assert len(pools) == 9


class _CheckerTerrainMap:
    """Two projected terrains alternating triangle by triangle on a grid, so
    almost every node is used by both and copied twice into band 3."""

    terrain_paths = ["lib/g10/terrain10/grass.ter",
                     "lib/g10/terrain10/asphalt.ter"]

    def __init__(self, lon0, lat0, step):
        self.lon0, self.lat0, self.step = lon0, lat0, step

    def terrain_index_at(self, lon, lat):
        fx = ((lon - self.lon0) / self.step) % 1.0
        fy = ((lat - self.lat0) / self.step) % 1.0
        return 0 if fx > fy else 1

    def terrain_indices_at(self, lons, lats):
        return [self.terrain_index_at(lon, lat)
                for (lon, lat) in zip(lons, lats, strict=True)]

    def is_projected(self, terrain_index):
        return True


@MODES._DSFTOOL
def test_default_land_pool_over_sixteen_bits_builds(
        tmp_path, monkeypatch, stub_elevation):
    # 190 x 190 nodes inside one level-3 quadtree cell (< 50,000 nodes: one
    # geometric pool), 71,442 land triangles; two terrains per node puts
    # ~72,000 points in one band-3 pool -- past the 16-bit limit.
    side, lon0, lat0, step = 190, 10.001, 50.001, 0.12 / 190
    verts = [(lon0 + i * step, lat0 + j * step)
             for j in range(side) for i in range(side)]
    tris = []
    for j in range(side - 1):
        for i in range(side - 1):
            a = j * side + i + 1
            b, c, d = a + 1, a + side + 1, a + side
            tris.append((a, b, c, 0))
            tris.append((a, c, d, 0))
    build_dir = MODES._prepare_build_dir(tmp_path)
    MODES._write_mesh(build_dir, verts, tris)
    terrain_map = _CheckerTerrainMap(lon0, lat0, step)
    monkeypatch.setattr(
        DTM.DefaultTerrainMap, "from_tile",
        classmethod(lambda cls, lat, lon: terrain_map))
    opened = []
    real_open = POOLS.DsfPointPools._open_overflow
    monkeypatch.setattr(
        POOLS.DsfPointPools, "_open_overflow",
        lambda self, full: opened.append(full) or real_open(self, full))

    assert DSF.build_dsf(MODES._make_tile(build_dir, "default_xplane"),
                         queue.Queue()) == 1

    assert opened, "no band pool reached 65,536 points: the fixture is too small"
    dump = MODES.DECODE.decode_dsf(MODES._emitted_dsf(build_dir))
    land = [p for p in dump.patches if p.terrain_path.startswith("lib/g10/")]
    assert {p.plane_count for p in land} == {5}
    assert sum(p.triangle_count for p in land) == len(tris)
