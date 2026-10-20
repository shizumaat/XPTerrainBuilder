"""``planar/zones.shore_region`` is read once per cell set (issue #412): the
structure pass's overlap passes and the channel pass ask for the same
cells' shore again, and each read buffers the airport union by 500 m.
The memo returns the SAME answer, misses on new cells or a frame that
has read further out, never keeps a frame alive, and leaves a sampler
that cannot name its water reads (every fixture) uncached."""
import gc
import types

from shapely.geometry import box

from auto_patch_v2.planar import zones


class _Frame:
    def __init__(self):
        self.calls = 0
        self.tiles = ((30, 31),)

    def water_tile_keys(self):
        return self.tiles

    def sea_geometry(self, bounds):
        self.calls += 1
        return box(-1000.0, -1000.0, 0.0, 1000.0)


def _cells(x0=10.0):
    ring = ((x0, 0.0), (x0 + 50.0, 0.0), (x0 + 50.0, 50.0), (x0, 50.0))
    return (types.SimpleNamespace(ring=ring, holes=()),)


def test_same_cells_read_once_and_equal():
    zones._SHORE_MEMO.clear()
    dem = _Frame()
    a = zones.shore_region(_cells(), dem)
    b = zones.shore_region(_cells(), dem)
    assert dem.calls == 1 and a is b and not a.is_empty


def test_new_cells_or_wider_frame_miss():
    zones._SHORE_MEMO.clear()
    dem = _Frame()
    zones.shore_region(_cells(), dem)
    zones.shore_region(_cells(20.0), dem)
    assert dem.calls == 2
    dem.tiles = ((30, 31), (30, 32))          # the frame read a neighbour
    zones.shore_region(_cells(), dem)
    assert dem.calls == 3


def test_frame_held_weakly_and_fixture_uncached():
    zones._SHORE_MEMO.clear()
    zones.shore_region(_cells(), _Frame())
    gc.collect()
    ref, _w = next(iter(zones._SHORE_MEMO.values()))
    assert ref() is None                      # the memo kept no frame alive
    plain = types.SimpleNamespace(calls=0)

    def sea(bounds):
        plain.calls += 1
        return box(-1000.0, -1000.0, 0.0, 1000.0)
    plain.sea_geometry = sea
    zones.shore_region(_cells(), plain)
    zones.shore_region(_cells(), plain)
    assert plain.calls == 2
