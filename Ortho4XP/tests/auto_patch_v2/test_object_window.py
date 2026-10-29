"""#1653: a pack's ``.obj`` / ``.agp`` placements are read inside the
airport's OWN extent — never a degree box about its reference point — and
in a pack of several airports each placement is the NEAREST airport's
(``airport/object_window``)."""
from __future__ import annotations

import os

from auto_patch_v2.airport import apt_dat as A
from auto_patch_v2.airport import object_pack as OP
from auto_patch_v2.airport import object_window as W
from auto_patch_v2.model.frame import Frame
from shapely.geometry import box

#: two synthetic airports ~0.9 km apart in one pack apt.dat; each a 130 ring
TWO_APT = """I
1200 synthetic
1 100 0 0 ZQQA Alpha
100 45.00 1 0 0.25 1 2 0 09 47.5000 -122.3200 0 0 3 0 0 0 27 47.5000 -122.2900 0 0 3 0 0 0
130 boundary
111 47.495 -122.322
111 47.495 -122.288
111 47.505 -122.288
113 47.505 -122.322
1 100 0 0 ZQQB Bravo
100 45.00 1 0 0.25 1 2 0 09 47.5000 -122.2720 0 0 3 0 0 0 27 47.5000 -122.2540 0 0 3 0 0 0
130 boundary
111 47.495 -122.276
111 47.495 -122.250
111 47.505 -122.250
113 47.505 -122.276
99
"""


def test_extent_not_a_degree_box():
    """A placement 6 km from the reference point but inside the extent is
    read; one 300 m from the reference point outside it is not."""
    extent = box(-7000, -100, 7000, 100)           # a long runway's extent
    win = W.Window("ZQQA", extent, extent)
    got = win.admits([(6500.0, 0.0), (0.0, 300.0)])
    assert list(got) == [True, False]
    assert win.n_outside == 1 and win.n_rival == 0


def test_nearest_airport_of_the_pack_keeps_it(tmp_path):
    p = os.path.join(tmp_path, "apt.dat")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(TWO_APT)
    assert A.airports_in(p) == ("ZQQA", "ZQQB")
    apts = {i: A.parse_airport_block(A.read_airport_block(p, i)) for i in ("ZQQA", "ZQQB")}
    to_xy = Frame("ZQQA", apts["ZQQA"].reference_point(), 9).transformers()[0]
    own = OP.region_in(apts["ZQQA"], to_xy)
    extent = own.buffer(1000.0)
    rivals = W.rivals(p, "ZQQA", apts["ZQQA"].reference_point(), to_xy, extent)
    assert [r[0] for r in rivals] == ["ZQQB"]
    x_gap0 = to_xy(-122.288, 47.5)[0]          # Alpha's east edge
    x_gap1 = to_xy(-122.276, 47.5)[0]          # Bravo's west edge
    near_a = (x_gap0 + 300.0, 0.0)
    near_b = (x_gap1 - 300.0, 0.0)
    win = W.Window("ZQQA", extent, own, rivals)
    got = win.admits([near_a, near_b, to_xy(-122.30, 47.5)])
    assert list(got) == [True, False, True]
    assert win.n_rival == 1
    # Bravo's own build, in its own frame, takes exactly the one Alpha refused
    to_xy_b = Frame("ZQQB", apts["ZQQB"].reference_point(), 9).transformers()[0]
    own_b = OP.region_in(apts["ZQQB"], to_xy_b)
    win_b = W.Window("ZQQB", own_b.buffer(1000.0), own_b,
                     W.rivals(p, "ZQQB", apts["ZQQB"].reference_point(), to_xy_b,
                              own_b.buffer(1000.0)))
    lonlat = [(-122.288 + 300.0 / 75300.0, 47.5), (-122.276 - 300.0 / 75300.0, 47.5)]
    assert list(win_b.admits([to_xy_b(lo, la) for lo, la in lonlat])) == [False, True]


def test_no_pack_apt_dat_no_rivals(tmp_path):
    assert W.pack_apt_dat(str(tmp_path)) is None
    assert W.rivals(None, "ZQQA", (0.0, 0.0), None, box(0, 0, 1, 1)) == ()
