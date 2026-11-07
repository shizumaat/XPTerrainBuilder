"""Step 21 stayed an hour at two airports (lane ``slowstep``, 2026-11-06):
a reading that depends on ONE placement was rebuilt per pair.  A
shared-datum pack co-places every object, so ``object_floor`` asked each
floor's every mate for its buffered deep walls (floors x mates GEOS
buffers), and ``sunken_roads`` re-read every member's wall bands per
plate.  Each is now read once per placement — these twins bound it."""
from __future__ import annotations

import types

import shapely

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import object_floor as OF
from auto_patch_v2.airport import plate_frame as PF
from test_hanging_objects1298 import LAW, THICK, _cover, _placed
from test_object_floor1903 import _ramped_floor


def test_each_mates_wall_band_is_built_once_per_read(tmp_path, monkeypatch):
    calls: list[str] = []
    real = OF._deep_walls

    def counted(p, cache, law):
        calls.append(p.id)
        return real(p, cache, law)

    monkeypatch.setattr(OF, "_deep_walls", counted)
    cover, floor = _cover(tmp_path), _ramped_floor(tmp_path)
    objs = ([_placed(cover, f"dsf:c{k}") for k in range(4)]
            + [_placed(floor, f"dsf:f{k}") for k in range(6)])
    floors, notes = OF.read_object_floors(objs, O.ResourceCache(THICK), LAW, {})
    assert floors, notes
    # 6 floors x 4 covers asked; each cover's walls built ONCE
    assert sorted(calls) == sorted(set(calls)) and len(calls) <= 4


def test_the_sampled_share_reads_the_buffered_one(tmp_path):
    """The indexed ring-sample share reads what the pre-slowstep reading
    did (the ring's length inside the whole cover's walls widened by the
    thickness) to well inside the 0.5 threshold's margin."""
    cache = O.ResourceCache(THICK)
    cover, floor = _placed(_cover(tmp_path), "dsf:c"), _placed(_ramped_floor(tmp_path), "dsf:f")
    foot = OF._placed_floor(floor, cache.geometry(floor.resolved), 0.0, LAW)[1]
    walls = shapely.union_all(OF._deep_walls(cover, cache, LAW).geometries)
    tk = LAW.tables.structures.tunnel.object.wall_face_max_thickness_m
    whole = foot.boundary.intersection(walls.buffer(tk)).length / foot.boundary.length
    got = OF._walled_share(foot, cover, cache, LAW)
    assert whole > 0.5 and abs(got - whole) < 0.01
