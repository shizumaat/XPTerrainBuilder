"""#2099 G2 (owner 2026-11-16T14:18Z): A MAPPED CAR PARK BESIDE A TAXIWAY IS A CAR
PARK.  Owner 14:18Z, CYYZ ``dsf:pol89``: "only for service vehicles and
connects to the road so it's a parking lot as well, even though a taxiway
runs along two sides".  Twin of ``classify/airside_edge._flank_car_park`` and
the §27 flip's taxi-family read."""
from __future__ import annotations

from auto_patch_v2.classify.airside_edge import airside_edge_flip
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from shapely.geometry import box

LAW = Law.for_airport("SYNT")
RULES = load_rules()
COVER = RULES.lot.flank_car_park_cover


def _flip(neighbour_role, lot_evid):
    final = [[neighbour_role, "pav1", box(0, 0, 100, 100), None, {}, neighbour_role],
             ["parking_lot", "pav2", box(100, 0, 200, 100), None,
              dict({"kind": "lot"}, **lot_evid), "lot"]]
    n, _r = airside_edge_flip(final, [], LAW, RULES)
    return n, final[1][0]


def test_a_mapped_car_park_beside_a_taxiway_stays_a_lot():
    park = {"source_class": "lot", "source_parking_cover": COVER}
    assert _flip("junction", park) == (0, "parking_lot")
    assert _flip("primary_parallel", park) == (0, "parking_lot")


def test_an_apron_edge_still_flips_it():
    """12c's own words: an APRON edge makes it airside, whatever the cover
    below ``parking_cover_fraction`` (11-13s)."""
    park = {"source_class": "lot", "source_parking_cover": COVER}
    assert _flip("apron", park) == (1, "apron")


def test_without_mapped_car_park_cover_a_taxiway_edge_still_flips_it():
    assert _flip("junction", {"source_class": "lot",
                              "source_parking_cover": COVER - 0.01}) == (1, "apron")
    # not a lot by its source (an open page, a road strip): unchanged
    assert _flip("junction", {"source_class": "open",
                              "source_parking_cover": 1.0}) == (1, "apron")
