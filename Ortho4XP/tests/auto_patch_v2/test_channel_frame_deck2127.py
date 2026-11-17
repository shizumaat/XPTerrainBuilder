"""#2127 R4 Part B (RULINGS 2026-11-17c): the cut runs on under a deck of its
own frame and climbs out beyond it.

B1 the axis runs on straight while each step stays inside the hidden shell's
bound and within the cap of a member or a floor-plate point; B2 a bore under
a frame deck piece yields when its stretch under the piece lies inside the
channel's crest; B3 the floor is held level under a frame deck and the climb
starts beyond it, the end moving to where the run-out meets the ground."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from auto_patch_v2.planar import channel_depth as _cd  # noqa: E402
from auto_patch_v2.planar.channel_claims import _under_frame_deck  # noqa: E402


def _cut(bound, members=(), plates=()):
    pts = np.array([(x, y, 60.0, 0) for x, y in members], float).reshape(-1, 4)
    ext = np.array([(x, y, 60.0, 1.0) for x, y in plates], float).reshape(-1, 4)
    return types.SimpleNamespace(bound=bound, points=pts, extent=ext, members=())


def _way(i, pts):
    return types.SimpleNamespace(id=i, points=[tuple(p) for p in pts])


def test_axis_runs_on_by_floor_plates_and_stops_at_the_bound():
    lead = _way(1, [(0, 0), (100, 0)])
    members = [(x, 5.0) for x in range(0, 101, 10)]
    plates = [(x, 0.0) for x in range(100, 301, 10)]          # past the last member
    cut = _cut(box(-5, -20, 250, 20), members, plates)
    kind = lambda w: "road" if w is lead else ""              # noqa: E731
    ln, used = _cd.extend_axis(LineString(lead.points), [lead], [cut], 30.0, kind, 10.0)
    assert used == []
    x0, x1 = ln.coords[0][0], ln.coords[-1][0]
    assert 240.0 <= x1 <= 250.0          # the plates reach on; the bound stops it
    assert -5.0 <= x0 <= 0.0
    # members only (no plates): the run stops within the cap of the last member
    ln2, _ = _cd.extend_axis(LineString(lead.points), [lead],
                             [_cut(box(-5, -20, 250, 20), members)], 30.0, kind, 10.0)
    assert 120.0 <= ln2.coords[-1][0] <= 130.0
    # no step: ways only (today)
    ln3, _ = _cd.extend_axis(LineString(lead.points), [lead], [cut], 30.0, kind)
    assert ln3.length == LineString(lead.points).length


def _channel(crest):
    return types.SimpleNamespace(id="channel:0", crest_ring=tuple(crest.exterior.coords)[:-1])


def _floor(deck_ring, footprint):
    deck = types.SimpleNamespace(id="dsf:obj9#2", ring=tuple(deck_ring.exterior.coords)[:-1])
    return types.SimpleNamespace(decks=(deck,), footprint=footprint)


def test_bore_under_a_frame_deck_yields_when_its_stretch_is_inside():
    crest = box(0, -15, 200, 15)
    deck = box(80, -30, 140, 30)                    # spans the cut across
    floors = [_floor(deck, box(-10, -40, 210, 40))]
    # 63 m bore, ~3 m outside each end of the deck: 90 % under it
    bore = _way(-838, [(77.0, 2.0), (143.0, 2.0)])
    assert _under_frame_deck([_channel(crest)], bore, floors) == ("channel:0", "dsf:obj9#2")
    # the same bore with no deck piece is kept
    assert _under_frame_deck([_channel(crest)], bore, [types.SimpleNamespace(
        decks=(), footprint=box(-10, -40, 210, 40))]) is None
    # under the deck but its stretch there leaves the crest: kept
    across = _way(-9, [(110.0, -28.0), (110.0, 28.0)])
    assert _under_frame_deck([_channel(crest)], across, floors) is None


def _ground(s):
    return 80.0


def test_rejoin_without_held_is_todays_profile():
    prof = tuple((float(s), 68.0) for s in range(0, 301, 20))
    a = _cd.rejoin(prof, 600.0, _ground, 0.1, 50.0)
    b = _cd.rejoin(prof, 600.0, _ground, 0.1, 50.0, held=())
    assert a == b
    assert a[-1][1] == 80.0 and a[0][1] == 68.0


def test_held_end_climbs_beyond_the_deck_and_moves_the_end():
    tn = types.SimpleNamespace(ramp_grade=0.06, ramp_max_grade=0.10)
    held = ((250.0, 320.0),)                   # a deck piece (with its band)
    ends, climbs, notes = _cd.climb_out((0.0, 300.0), (68.0, 68.0), 600.0, _ground,
                                       held, tn, 50.0)
    (c,) = climbs
    assert c.end == 1 and c.foot == 320.0
    assert ends[0] == 0.0 and 320.0 + 12.0 / 0.10 <= ends[1] <= 320.0 + 12.0 / 0.06 + 1.0
    ss = sorted({*range(0, int(ends[1]) + 1, 10), ends[1]})
    raw = tuple((float(s), 68.0) for s in ss)
    prof = _cd.rejoin(_cd.climbed(raw, climbs), 600.0, _ground, 0.10, 50.0, held=held)
    z = dict(prof)
    assert all(abs(z[s] - 68.0) < 1e-9 for s in z if 250.0 <= s <= 320.0)   # level under it
    assert abs(prof[-1][1] - 80.0) <= 0.05                                  # meets the ground
    assert all(b[1] >= a[1] - 1e-9 for a, b in zip(prof[25:], prof[26:], strict=False))  # climbs beyond


def test_climb_that_cannot_fit_is_reported_not_built():
    tn = types.SimpleNamespace(ramp_grade=0.06, ramp_max_grade=0.10)
    ends, climbs, notes = _cd.climb_out((0.0, 300.0), (68.0, 68.0), 380.0, _ground,
                                       ((250.0, 320.0),), tn, 50.0)
    assert climbs == () and ends == (0.0, 300.0)
    assert notes and "cannot" in notes[0]


def test_end_with_no_deck_is_unchanged():
    tn = types.SimpleNamespace(ramp_grade=0.06, ramp_max_grade=0.10)
    ends, climbs, notes = _cd.climb_out((0.0, 300.0), (68.0, 68.0), 600.0, _ground,
                                       ((10.0, 40.0),), tn, 50.0)
    # the low end's climb (0 -> 120 m at 10 %) touches (10, 40) but the axis
    # does not run on there (its end is the axis's own)
    assert climbs == () and ends == (0.0, 300.0)
