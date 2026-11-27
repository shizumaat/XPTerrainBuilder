"""#2297 (GCLA): ``geom/lowest_face.floor_z_at`` read a point just off a
concave shell's WALL on the wall's plane — a face whose plan is a sliver
(0.0004 m wide, 0.34 m tall) — and the trench pin stood 385 km under the
ground.  A reading beyond a face's edge stays within ``edge_m`` of that
face's own heights; a face up to 1:1 reads exactly as before."""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.geom.lowest_face import every_z_at, floor_z_at

#: GCLA_Terminal_Underside_020.obj@shell, face 3593 (frame metres), verbatim
WALL = np.array([[[252.56193575132477, -266.82267871565807, 26.431090706705632],
                  [252.66869743373377, -272.1676614507478, 26.413220706705633],
                  [252.66870396560182, -272.1680297648179, 26.753300706705634]]])
#: the pinned vertex v4305
AT = (253.5, -267.0)


def test_a_wall_read_off_its_edge_stays_by_its_own_heights():
    z = float(floor_z_at(WALL, [AT[0]], [AT[1]], edge_m=1.0)[0])
    assert 26.4132 - 1.0 - 1e-9 <= z <= 26.7533 + 1.0 + 1e-9


def test_a_gentle_face_still_reads_its_plane_beyond_the_edge():
    # a 10 % plate x 0..10, read 0.5 m past its downhill edge
    plate = np.array([[[0.0, 0.0, 1.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]],
                      [[0.0, 0.0, 1.0], [10.0, 10.0, 0.0], [0.0, 10.0, 1.0]]])
    z = float(floor_z_at(plate, [10.5], [5.0], edge_m=1.0)[0])
    assert z == pytest.approx(-0.05)
    assert np.isnan(floor_z_at(plate, [12.0], [5.0], edge_m=1.0)[0])
    assert every_z_at(plate, [5.0], [5.0])[0].tolist() == pytest.approx([0.5, 0.5])
