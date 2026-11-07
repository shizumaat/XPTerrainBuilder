"""Step 21 stayed an hour at two airports (lane ``slowstep``, 2026-11-06):
a reading that depends on ONE placement was rebuilt per pair.  A
shared-datum pack co-places every object, so ``object_floor`` asked each
floor's every mate for its buffered deep walls (floors x mates GEOS
buffers), and ``sunken_roads`` re-read every member's wall bands per
plate.  Each is now read once per placement — these twins bound it."""
from __future__ import annotations

import types

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


def test_the_near_walls_share_is_the_whole_covers(tmp_path):
    """Widening only the walls near the ring reads the same share as
    widening the whole cover (the pre-slowstep reading)."""
    from shapely.ops import unary_union

    cache = O.ResourceCache(THICK)
    cover, floor = _placed(_cover(tmp_path), "dsf:c"), _placed(_ramped_floor(tmp_path), "dsf:f")
    foot = OF._placed_floor(floor, cache.geometry(floor.resolved), 0.0, LAW)[1]
    walls = OF._deep_walls(cover, cache, LAW)
    tk = LAW.tables.structures.tunnel.object.wall_face_max_thickness_m
    whole = foot.boundary.intersection(unary_union(walls).buffer(tk)).length / foot.boundary.length
    got = OF._walled_share(foot, cover, cache, LAW)
    assert whole > 0.5 and abs(got - whole) < 1e-6


def test_the_family_bands_are_read_once_across_its_plates(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(PF, "_bands_of", lambda o, *a: calls.append(o.id) or ([], []))
    members = [types.SimpleNamespace(id=f"dsf:m{k}") for k in range(5)]
    memo: dict = {}
    for _plate in range(3):
        assert PF.walls_frame(members, None, None, LAW, (0.0, 0.0), (0.0, 50.0), 8.0, 1,
                              memo) is None
    assert sorted(calls) == sorted(m.id for m in members)
