"""Twin of X-Plane's DSF window model (``src/O4_World_Window.py``; flight
manager / World spec 2026-11-10 §2.2, §8.1, §15).

Fixture: ``tests/fixtures/world/cyyr_world_flight.replay.json``, cut from
the CYYR World pack recording (2026-11-10 14:51-15:23Z, 53°N, westbound
then a southbound and a northbound leg) with ``tools/imagery_tier_replay.py
extract flight_world.jsonl --aircraft``: the aircraft positions and every
``.dsf`` X-Plane opened (any pack; the window is the same for all).  The
72 MB recording stays in the data repo
(``.harness/frames/lworld/cyyr-worldkit/``).
"""
from __future__ import annotations

import bisect
import json
import os

import O4_World_Pack as WP
import O4_World_Window as W
import pytest

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "world", "cyyr_world_flight.replay.json")
TOLERANCE_DEG = 0.02


@pytest.fixture(scope="module")
def flight():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def _entries(pos: list, mirror=None) -> list:
    """``[(t, lat, lon, {tiles entering})]`` along the recorded positions,
    from a flight load at the first one."""
    mirror = mirror or (lambda la, lo: (la, lo))
    tracker, out = W.WindowTracker(), []
    tracker.load(*mirror(pos[0][1], pos[0][2]))
    for t, lat, lon, *_ in pos:
        lat, lon = mirror(lat, lon)
        enter = tracker.update(lat, lon)
        if enter:
            out.append((t, lat, lon, enter))
    return out


def _at(pos: list, t: float) -> tuple[float, float]:
    i = min(bisect.bisect_left([p[0] for p in pos], t), len(pos) - 1)
    return pos[i][1], pos[i][2]


def _assign(dsf: list, predicted: list) -> dict[int, list]:
    """Each recorded open goes to the latest predicted entry of its tile at
    or before it (positions are 1 Hz: 2 s of slack): ``{event: [(t, tile)]}``;
    an open no entry explains goes under ``-1``."""
    out: dict[int, list] = {}
    for t, name, _pack in dsf:
        tile = WP.parse_tile(name)
        hits = [i for i, (tp, *_, enter) in enumerate(predicted)
                if tile in enter and tp <= t + 2.0]
        out.setdefault(hits[-1] if hits else -1, []).append((t, tile))
    return out


def test_every_open_is_predicted_and_no_entry_without_one(flight):
    """Each window move of the flight (four columns west, a row south, a
    row north) is predicted with exactly the tiles X-Plane opened, and the
    move's first open came within 0.02° of where the model moves it."""
    pos = flight["pos"]
    predicted = _entries(pos)
    assert len(predicted) == 6
    opens = _assign(flight["dsf"], predicted)
    assert -1 not in opens
    assert sorted(opens) == list(range(len(predicted)))
    for i, (_t, lat, lon, enter) in enumerate(predicted):
        assert {tile for _, tile in opens[i]} == enter
        olat, olon = _at(pos, min(t for t, _ in opens[i]))
        assert max(abs(olat - lat), abs(olon - lon)) <= TOLERANCE_DEG, (
            sorted(enter), (olat, olon), (lat, lon))


def test_world_pack_opens_are_a_subset_of_the_predicted_entries(flight):
    world = [r for r in flight["dsf"] if r[2] == WP.PACK_NAME]
    assert len(world) == 13
    entered = {t for *_, enter in _entries(flight["pos"]) for t in enter}
    assert {WP.parse_tile(r[1]) for r in world} <= entered


def test_measured_entry_lines():
    """§2.2's table: column -63 entered at lon -60.652 westbound, row 51 at
    lat 52.900 southbound, row 54 at 53.100 northbound; and the EAST line,
    which the kit's ``xp_window`` put one degree late (tlon - 0.35)."""
    assert W.load_box(53, -63)[3] == pytest.approx(-60.65)   # T + 2.35
    assert W.load_box(51, -63)[1] == pytest.approx(52.9)
    assert W.load_box(54, -63)[0] == pytest.approx(53.1)
    assert W.load_box(53, -58)[2] == pytest.approx(-59.35)   # T - 1.35
    tracker = W.WindowTracker()
    tracker.load(53.3, -60.447)
    assert tracker.update(53.3, -59.36) == set()
    assert tracker.update(53.3, -59.34) == {(52, -58), (53, -58), (54, -58)}


def test_mirrored_flight_gives_mirrored_entries(flight):
    """Eastbound and northbound: the same track mirrored about lon -60 and
    lat 53 enters the mirrored tiles at the mirrored places."""
    def mirror(lat, lon):
        return 106.0 - lat, -120.0 - lon

    def mirror_tile(tile):
        return 105 - tile[0], -121 - tile[1]

    west = _entries(flight["pos"])
    east = _entries(flight["pos"], mirror=mirror)
    assert [e[0] for e in east] == [w[0] for w in west]
    for (_t, _la, _lo, ew), (_t2, _la2, _lo2, ee) in zip(west, east, strict=True):
        assert {mirror_tile(t) for t in ew} == ee


def test_unknown_history_is_the_union_and_collapses():
    tracker = W.WindowTracker()
    start = tracker.update(53.30427, -60.447077)       # no flight load seen
    assert tracker.cols == {-61, -60} and not tracker.known()
    assert {c for _, c in start} == {-63, -62, -61, -60, -59}
    loaded = W.WindowTracker()
    assert loaded.load(53.30427, -60.447077) <= start
    # the witness of one loaded column settles B
    assert tracker.witness(53, -59) == set() and tracker.cols == {-60}
    # or the first column shift does
    other = W.WindowTracker()
    other.update(53.30427, -60.447077)
    other.update(53.3, -60.66)
    assert other.cols == {-61}


def test_witness_moves_a_wrong_window():
    tracker = W.WindowTracker()
    tracker.load(53.3, -60.4)                 # B -60: columns -62..-59
    # column -64 loaded: B moves the least that holds it, to -62
    added = tracker.witness(53, -64)
    assert {c for _, c in added} == {-64, -63} and tracker.cols == {-62}
    assert tracker.witness(56, -63) and tracker.rows == {55}


def test_reach_east_and_west():
    cyyr = (53.3192, -60.4258)
    at_load = W.WindowTracker()
    at_load.load(*cyyr)                       # B -60: columns -62..-59
    assert W.reach(*cyyr, 53, -62, at_load)["in_window"] is True
    west = W.reach(*cyyr, 53, -63, at_load)
    assert west["in_window"] is False and 14 < west["km_to_load"] < 17
    # no history: B may be -61 as well, so -63 may be held (errs yes)
    assert W.reach(*cyyr, 53, -63)["in_window"] is True
    east = W.reach(*cyyr, 53, -58, at_load)
    # enters at -59.35: 1.07 deg of longitude east at 53.3 N, about 71 km
    assert east["in_window"] is False and 68 < east["km_to_load"] < 75
    assert W.reach(*cyyr, 55, -61)["in_window"] is False
    # flight 2 (60 N, westbound): column -138 opened at lon -135.65.  With
    # no history -135.40 may hold it (B -136 or -135): the answer errs yes
    assert W.reach(60.75, -135.40, 60, -138)["in_window"] is True
    flown = W.WindowTracker()
    flown.load(60.75, -134.9)
    flown.update(60.75, -135.40)
    assert W.reach(60.75, -135.40, 60, -138, flown)["in_window"] is False
    flown.update(60.75, -135.70)
    assert W.reach(60.75, -135.70, 60, -138, flown)["in_window"] is True


def test_route_entries_first_window_and_entry_points(flight):
    pts = [(p[1], p[2]) for p in flight["pos"]]
    first = W.route_entries(pts)
    start = W.window_tiles(W.plausible_columns(pts[0][1]),
                           W.plausible_rows(pts[0][0]))
    assert {t for t, i in first.items() if i == 0} == start
    lat, lon = pts[first[(53, -64)]]
    assert lon == pytest.approx(-61.65, abs=TOLERANCE_DEG)
