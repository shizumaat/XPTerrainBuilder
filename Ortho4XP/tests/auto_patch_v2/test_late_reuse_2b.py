"""Late-stage reuse phase 2b (issue #803): a road profile builds each way's
line once and never stores the memo; a ribbon weld cuts with the rim's band
zone computed once, and the answer is the per-call one."""
import pickle

import numpy as np
from auto_patch_v2.airport.road_profile import OSM, RoadProfiles, Way
from auto_patch_v2.geom.cluster_outline import AirsideRim
from auto_patch_v2.planar.ribbon_weld import _weld_to_rim, rim_zone
from shapely.geometry import Polygon, box


def _profiles():
    xy = np.array([[0.0, 0.0], [100.0, 0.0]])
    w = Way(OSM, "w1", xy, np.array([0.0, 100.0]), np.zeros(2), np.array([1.0, 2.0]))
    return RoadProfiles(0.05, 10.0, 3.5, 20.0, (w,)), w


def test_a_way_line_is_built_once_and_never_pickled():
    rp, w = _profiles()
    a = rp.answer((50.0, 1.0), 0.0, through=[(w, 5.0)])
    assert rp._line(w) is rp._line(w)
    b = rp.answer((50.0, 1.0), 0.0, through=[(w, 5.0)])
    assert (a.z, a.lateral_m) == (b.z, b.lateral_m)
    back = pickle.loads(pickle.dumps(rp))
    assert "_line_memo" not in back.__dict__
    assert back.answer((50.0, 1.0), 0.0, through=[(back.ways[0], 5.0)]).z == a.z


def test_the_shared_zone_welds_as_the_per_call_one():
    rim = AirsideRim(box(0, 0, 100, 100), 0.75)
    rib = Polygon([(100.4, 10), (130, 10), (130, 20), (100.4, 20)])
    plain = _weld_to_rim(rib, rim, 0.75, {})
    shared = _weld_to_rim(rib, rim, 0.75, {}, zone=rim_zone(rim, 0.75))
    assert plain.equals_exact(shared, 0.0)
