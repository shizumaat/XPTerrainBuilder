"""``tools/shell_seat_replay.py`` (#2272 round 3): the census rows a kept
shell reads as become ``shell`` seat records, a drawn mesh becomes the
placement write's surface, and each shell is measured at its author's and
its skirt's seat.  Synthetic OBJ8 and mesh, no corpus."""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(__file__)
for _p in (os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "tools"),
           os.path.join(HERE, "auto_patch_v2")):
    sys.path.insert(0, _p)

import shell_seat_replay as SSR  # noqa: E402
import test_shell_seat as TSS  # noqa: E402
import test_terrain_model as TTM  # noqa: E402


class _Mesh:
    """A drawn mesh: ``ground(x, y)`` east / north of the anchor."""

    def __init__(self, ground):
        self.surface = TSS._surface(ground)

    def z(self, lats, lons):
        return np.array([np.nan if v is None else v
                         for v in self.surface.many(list(lats), list(lons))])


def test_records_and_the_two_seats(tmp_path):
    TTM._write(tmp_path, "rock.obj", TSS._mesa, half=TSS.HALF, step=1.0, hard=False)
    rows = [{"verdict": "terrain shell", "resource": "rock.obj", "z0": TSS.Z0,
             "lat": TSS.LAT, "lon": TSS.LON, "heading": 0.0},
            {"verdict": "msl row", "resource": "x.obj", "z0": 1.0, "lat": 0, "lon": 0,
             "heading": 0}]
    recs = SSR.shell_records(rows, str(tmp_path))
    assert len(recs) == 1 and recs[0]["shell"]["file"] == str(tmp_path / "rock.obj")
    # our ground 2.5 m under the rim on the east half and 1 m under its
    # body (4.5 m over the rim), over the body in the west
    def ground(x, y):
        if x <= 0:
            return TSS.Z0 + 6.0
        return TSS.Z0 + 3.5 if max(abs(x), abs(y)) < 25.0 else TSS.Z0 - 2.0
    surf = SSR.surface_of(_Mesh(ground))
    (rep,) = SSR.measure(recs, surf)
    assert rep["dz"] == pytest.approx(-2.5, abs=0.05)
    assert rep["author"]["rim_gap_m"] == pytest.approx(2.5, abs=0.05)
    assert rep["skirt"]["rim_gap_m"] == 0.0
    assert rep["skirt"]["through_m2"] > rep["author"]["through_m2"] > 0.0


def test_the_run_out_fill_is_replayed_and_what_floats_is_placed(tmp_path):
    # RULINGS 2026-11-25l (3): a rock whose skirt runs out (``fill_z0``) has
    # our ground raised to its rim before the seat; inside the patch it is
    # never raised, and what still floats is counted there
    import shapely
    TTM._write(tmp_path, "rock.obj", TSS._mesa, half=TSS.HALF, step=1.0, hard=False)
    rows = [{"verdict": "rock", "resource": "rock.obj", "z0": TSS.Z0, "lat": TSS.LAT,
             "lon": TSS.LON, "heading": 0.0, "fill_z0": TSS.Z0 - 4.5}]
    recs = SSR.shell_records(rows, str(tmp_path))
    assert recs[0]["fill_z0"] == TSS.Z0 - 4.5
    surf = SSR.surface_of(_Mesh(lambda x, y: TSS.Z0 - 10.0))      # 10 m under its rim
    filled, reps = SSR.filled_surface(recs, surf, None, 5.0)
    assert reps["shell0"]["raised"] > 0 and reps["shell0"]["in_patch"] == 0
    (rep,) = SSR.measure(recs, filled)
    assert rep["fixed"] and rep["skirt"]["rim_gap_m"] <= 0.5
    left = SSR.floating(recs[0], rep["dz"], filled, None, 5.0)
    assert left["floating_free"] == 0
    patch = shapely.box(TSS.LON - 0.01, TSS.LAT - 0.01, TSS.LON + 0.01, TSS.LAT + 0.01)
    held, reps = SSR.filled_surface(recs, surf, patch, 5.0)
    assert reps["shell0"]["raised"] == 0 and reps["shell0"]["in_patch"] == reps["shell0"]["stations"]
    (rep,) = SSR.measure(recs, held)
    left = SSR.floating(recs[0], rep["dz"], held, patch, 5.0)
    assert left["floating_in_patch"] > 0 and left["floating_free"] == 0
