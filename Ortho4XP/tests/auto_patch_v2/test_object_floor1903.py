"""#1903 (owner 2026-11-06T00:07Z): a trench object that carries its own floor
and ramps defines the cut — the ground inside its footprint is its own floor
per triangle (``airport/object_floor``), end to end, not an axis profile."""
from __future__ import annotations

import numpy as np
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import object_floor as OF
from test_hanging_objects1298 import LAW, THICK, _box, _cover, _placed, _write


def _ramped_floor(tmp_path):
    """A floor plate at −4 m over z 10..70 and two ramps rising to the lips
    at z 0 and z 80 — no walls (the cover carries them)."""
    plate = _box(-9.5, 10.0, 19.0, 60.0, 0.2, y0=-4.0)
    ramps = [((-9.5, 0.0, 0.0), (9.5, 0.0, 0.0), (9.5, -3.8, 10.0)),
             ((-9.5, 0.0, 0.0), (9.5, -3.8, 10.0), (-9.5, -3.8, 10.0)),
             ((-9.5, -3.8, 70.0), (9.5, -3.8, 70.0), (9.5, 0.0, 80.0)),
             ((-9.5, -3.8, 70.0), (9.5, 0.0, 80.0), (-9.5, 0.0, 80.0))]
    return _write(tmp_path / "floor.obj", [plate, ramps])


def test_the_lowest_face_is_the_floor_and_the_edge_reads_its_plane():
    faces = np.array([[[0, 0, 5.0], [10, 0, 5.0], [0, 10, 5.0]],
                      [[0, 0, 2.0], [10, 0, 2.0], [0, 10, 2.0]]])
    z = OF.floor_z_at(faces, [2.0, 20.0, -0.5], [2.0, 20.0, 2.0], edge_m=1.0)
    assert z[0] == 2.0 and np.isnan(z[1]) and z[2] == 2.0


def test_a_floor_beside_its_cover_is_the_cut_end_to_end(tmp_path):
    cache = O.ResourceCache(THICK)
    objs = [_placed(_cover(tmp_path), "dsf:obj1"), _placed(_ramped_floor(tmp_path), "dsf:obj2")]
    floors, notes = OF.read_object_floors(objs, cache, LAW, {})
    assert len(floors) == 1, notes
    f = floors[0]
    assert f.object_id == "dsf:obj2" and f.covers == ("dsf:obj1",)
    # the footprint runs lip to lip (80 m), not wall end to wall end
    xs = [p[0] for p in f.footprint.exterior.coords]
    ys = [p[1] for p in f.footprint.exterior.coords]
    assert max(ys) - min(ys) > 79.0 and max(xs) - min(xs) > 18.9
    # the plate at its seat, the ramp half way up, the lip at grade
    s = OF.floor_z_at(f.faces, [0.0, 0.0, 0.0], [-40.0, -5.0, -0.5])
    assert abs(s[0] - 96.0) < 0.21 and abs(s[1] - 98.1) < 0.2 and s[2] > 99.7


def test_a_floor_with_no_cover_is_not_a_tunnels(tmp_path):
    cache = O.ResourceCache(THICK)
    floors, notes = OF.read_object_floors([_placed(_ramped_floor(tmp_path), "dsf:obj2")],
                                          cache, LAW, {})
    assert floors == [] and any("no co-placed cover" in n for n in notes)
