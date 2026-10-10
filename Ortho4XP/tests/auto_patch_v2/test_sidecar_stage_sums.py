"""The sidecar's top-block taxi row counters behind a last stage (§55 (4)).

The taxi-family rows (§8.6 trend, §61 cross-section and membrane) live in
the base solve's stage 1; the last stage solves followers only and counts
0 of them.  Its report becomes the build's top block, so the base's rows
are folded in: the top block is the SUM over stages, for
``taxi_trend_rows`` as for ``taxi_xsec_rows`` / ``free_membrane_rows``."""

from __future__ import annotations

from auto_patch_v2.pipeline.build import _BASE_STAGE_ROWS, _fold_base_rows
from auto_patch_v2.solve.design_report import DesignReport


def test_the_top_block_is_the_sum_over_stages():
    base = DesignReport(taxi_trend_rows=412, taxi_xsec_rows=96,
                        free_membrane_rows=31)
    late = DesignReport(taxi_trend_rows=0, taxi_xsec_rows=0,
                        free_membrane_rows=2)
    _fold_base_rows(late, base)
    top = late.as_dict()
    assert top["taxi_trend_rows"] == 412, top["taxi_trend_rows"]
    assert top["taxi_xsec_rows"] == 96
    assert top["free_membrane_rows"] == 33


def test_every_taxi_row_counter_of_the_report_is_folded():
    names = {f for f in DesignReport.__dataclass_fields__
             if f.startswith("taxi_") and f.endswith("_rows")}
    assert names <= set(_BASE_STAGE_ROWS), names - set(_BASE_STAGE_ROWS)
