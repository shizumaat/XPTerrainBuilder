"""Twin for ``tools/no_step_term_split.py`` (promoted 2026-08-27 on its
SECOND use, RULINGS ``7e90032``).

Pins the discriminator (structural, not a guess), the missing-sidecar
behaviour (``None``, never a guessed zero), the imposed / census-only
split Amendment 1 introduced, the CLI's JSON being the library result,
and the index row.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import no_step_term_split as NTS                           # noqa: E402


def _rows(tmp_path, rows):
    p = tmp_path / "rows.json"
    p.write_text(json.dumps({"patch": "x.osm", "n_rows": len(rows),
                             "rows": rows}))
    return p


def _sidecar(tmp_path, edges):
    p = tmp_path / "x.osm.axes.json"
    p.write_text(json.dumps({"airside_no_step_edges": edges}))
    return p


ROWS = [
    {"family": "airside_no_step", "cap_pct": 1.5, "magnitude_m": 0.6},
    {"family": "airside_no_step", "cap_pct": 1.0, "magnitude_m": 1.2},
    {"family": "airside_no_step", "cap_pct": None, "magnitude_m": 2.4},
    {"family": "within_shape", "cap_pct": 1.5, "magnitude_m": 9.9},
]


def test_the_discriminator_is_the_published_cap():
    assert NTS.is_pair_row({"cap_pct": 1.5}) is True
    assert NTS.is_pair_row({"cap_pct": None}) is False
    assert NTS.is_pair_row({}) is False
    # …and it is the one check_grade actually fills, both ways round.
    import inspect
    import check_grade as cg
    assert "cap_pct=cap" in inspect.getsource(cg._check_published_law_edges)
    assert "cap_pct" not in inspect.getsource(cg._check_airside_no_step_rate)


def test_the_two_terms_split_and_other_families_are_untouched(tmp_path):
    res = NTS.split(_rows(tmp_path, ROWS))
    assert res["rows"] == 3           # the within_shape row is not ours
    assert res["grade_rows"] == 2
    assert res["grade_worst_de_m"] == pytest.approx(1.2)
    assert res["rate_rows"] == 1
    assert res["rate_worst_de_m"] == pytest.approx(2.4)


def test_no_sidecar_reports_None_never_a_guessed_zero(tmp_path):
    res = NTS.split(_rows(tmp_path, ROWS))
    assert res["published_edges"] is None
    assert res["published_imposed"] is None
    assert res["published_census_only"] is None


def test_the_imposed_split_is_read_from_the_publication(tmp_path):
    """Spec Amendment 1 ruling 1: a tier2<->tier2 pair is CENSUS-PRICED
    but NOT solver-imposed, and its rows must never read as a constraint
    the projection failed to meet."""
    edges = [{"a": [0, 0], "b": [0, 1], "budget_m": 1.0, "imposed": True},
             {"a": [0, 0], "b": [0, 2], "budget_m": 1.0, "imposed": True},
             {"a": [0, 0], "b": [0, 3], "budget_m": 1.0, "imposed": False}]
    res = NTS.split(_rows(tmp_path, ROWS), _sidecar(tmp_path, edges))
    assert res["published_edges"] == 3
    assert res["published_imposed"] == 2
    assert res["published_census_only"] == 1


def test_a_pre_amendment_publication_reports_None_for_the_split(tmp_path):
    edges = [{"a": [0, 0], "b": [0, 1], "budget_m": 1.0}]
    res = NTS.split(_rows(tmp_path, ROWS), _sidecar(tmp_path, edges))
    assert res["published_edges"] == 1
    assert res["published_imposed"] is None


def test_it_counts_nothing_itself():
    src = Path(NTS.__file__).read_text()
    assert "run_checks" not in src
    assert "_parse_osm" not in src
    assert NTS.FAMILY == "airside_no_step"
    import check_grade as cg
    assert NTS.FAMILY in [k for (k, _t, _b) in cg.LAW_FAMILIES]


def test_the_CLI_json_IS_the_library_result(tmp_path):
    rows = _rows(tmp_path, ROWS)
    side = _sidecar(tmp_path, [{"a": [0, 0], "b": [0, 1],
                                "budget_m": 1.0, "imposed": True}])
    out = tmp_path / "o.json"
    assert NTS.main([str(rows), str(side), "--json", str(out)]) == 0
    assert json.loads(out.read_text()) == NTS.split(rows, side)


def test_the_index_row_exists():
    idx = (_ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "Ortho4XP/tools/no_step_term_split.py" in idx
