"""THE AIRPORT'S LEVEL B (owner RULINGS 2026-11-03b; the master's reading of
"one lower level (B)"; ``planar/level_depth``).

The airport's level-B depth is the feet-weighted median of its units'
lower storeys, and no reading where no unit states one.
"""
from __future__ import annotations

import types

from auto_patch_v2.law import Law
from auto_patch_v2.planar import level_depth as LD


def test_the_level_is_the_weighted_median_of_the_storeys():
    assert LD._weighted_median([(7.0, 10), (7.4, 3), (12.0, 1)]) == 7.0
    assert LD._weighted_median([(5.0, 1), (9.0, 5)]) == 9.0


def test_no_partition_or_no_cells_reads_no_level():
    law = Law.for_airport("ZZZZ")
    assert LD.airport_level_b(types.SimpleNamespace(partition=None), None, law)[0] is None
    cl = types.SimpleNamespace(cells=())
    assert LD.airport_level_b(types.SimpleNamespace(partition=object()), cl, law)[0] is None
