"""#2113 (KBNA owner sim read 2026-11-17T23:52Z on 1.0.557, eight sites
between the concourses: "they should all be apron"): THE BAND GROUND ON A
GAP SHEET IS APRON (``classify/gap_band``).

The mint cut every piece out of the taxi band envelope and
``gap_apron.fill_to_taxi`` refilled the band only where its far side was a
taxi face within one closing radius; with an apron (a route corridor
flipped to apron) or a road standing across the band, the pack's drawn
pavement there stayed a taxiway STRIP — grass between the gates' apron and
the taxilanes."""
from __future__ import annotations

import sys
from pathlib import Path

from shapely.geometry import Point, Polygon, box

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch_v2.classify.gap_band import attach, band_parts, road_split  # noqa: E402
from auto_patch_v2.classify.ribbon_mint import ribbon_extent  # noqa: E402
from auto_patch_v2.classify.roles import Cell  # noqa: E402
from test_gap_mint import LAW, _airport, _cell, _mint, _ring  # noqa: E402

TAXI = Cell(0, "junction", "pav9", _ring(box(0, 0, 200, 30)), (), 4, "E", "airside",
            "junction", {})


def _apron_at(out, x, y):
    return [ref for role, ref, poly, *_ in out
            if role == "apron" and poly.distance(Point(x, y)) < 1e-6]


def test_band_ground_behind_an_apron_corridor_is_apron():
    """KBNA sites 1-7: an apron corridor (route33) runs inside the taxi band
    between the taxi face and the gates' page; the page's band ground on
    both sides of the corridor is apron, and the corridor stays itself."""
    band = ribbon_extent([TAXI], LAW, Polygon())
    route = _cell(1, "apron", "route33", box(0, 34, 200, 36))
    out, stats, _ = _mint(_airport(box(0, 30, 200, 300)), [TAXI, route])
    for x, y in ((100, 32.5), (100, 37)):
        assert band.contains(Point(x, y))           # the band's ground in the base
        assert _apron_at(out, x, y), (x, y)
    assert stats["gap_band_apron_m2"] > 0.0
    for _r, _f, poly, *_ in out:
        assert poly.intersection(Polygon(route.ring)).area < 1e-6


def test_a_road_across_the_page_leaves_the_far_band_ground_apron():
    """KBNA site 8: a groundside road crosses the page inside the taxi band;
    the band ground it cut off from the page's apron piece is apron — the
    road stays a road."""
    apron = _cell(1, "apron", "pav1", box(0, 120, 200, 220))
    road = _cell(2, "service_road", "route34", box(0, 40, 200, 48))
    out, _s, _ = _mint(_airport(box(0, 30, 200, 120)), [TAXI, apron, road])
    assert _apron_at(out, 100, 60)                  # the page is apron
    assert _apron_at(out, 100, 34)
    for _r, _f, poly, *_ in out:
        assert poly.intersection(Polygon(road.ring)).area < 1e-6


def test_band_ground_far_from_the_page_apron_and_its_road_stays_the_band():
    """A page's apron piece makes no far band ground apron by itself: only
    a road across the page between the two does (HECA's drape pages hold
    both apron and road pieces)."""
    sheet = box(0, 0, 400, 100)
    apron = box(0, 50, 100, 100)
    road = box(150, 0, 160, 100)
    assert road_split(box(161.5, 0, 200, 10), [sheet], [apron], [road], 2.5) is False
    assert road_split(box(101.5, 0, 148.5, 10), [sheet], [box(0, 0, 100, 100)], [box(100, 0, 100.5, 100)], 2.5) is True


def test_band_ground_on_a_page_with_no_apron_stays_the_band():
    """A page drawn beside a taxiway and no apron is not apron population:
    its band ground is not minted (the #1976 road twin's own bar)."""
    lot = _cell(1, "parking_lot", "lot1", box(0, 300, 200, 400))
    out, stats, _ = _mint(_airport(box(0, 30, 200, 300)), [TAXI, lot])
    assert not _apron_at(out, 100, 34)
    assert stats.get("gap_band_pieces", 0) == 0


def test_attach_gives_a_part_to_the_piece_it_shares_most_rim_with():
    part = box(0, 0, 10, 10)
    pieces = [box(10, 0, 20, 2), None, box(0, 10, 10, 20)]
    taken, loose = attach([part, box(50, 50, 60, 60)], pieces, 0.01)
    assert list(taken) == [2] and len(loose) == 1


def test_band_parts_stay_out_of_the_runway_knife():
    free = box(0, 0, 100, 100)
    parts = band_parts(free, box(0, 0, 100, 50), box(0, 0, 100, 20), 0.01)
    assert len(parts) == 1 and abs(parts[0].area - 3000.0) < 1.0
