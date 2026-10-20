"""Known-answer twins for ``tools/census_rows_diff.py``.

Instrument-truth (RULINGS 2026-08-06): an instrument without a
calibration twin is not an instrument.  The quantity this one produces
is a JOIN — which rows of A are which rows of B — and a join is exactly
the kind of code that answers plausibly while being wrong, so every case
below has a hand-computable answer.

The tool derives no law: it reads census dumps verbatim.  What is
asserted here is therefore the join and its refusals, not any count.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import census_rows_diff as CRD  # noqa: E402


KNOBS = {"max_grade_pct": 1.5, "proximity_m": 0.5,
         "edge_search_m": 5.0, "edge_step_m": 0.5}


def _row(family="within_shape", roles="apron|apron", side="airside",
         p0=(0.0, 0.0), p1=(10.0, 0.0), mag=1.0, way_a="-1", way_b="-1"):
    return {"family": family, "roles": roles, "side": side,
            "magnitude_m": mag, "grade_pct": 2.0, "cap_pct": 1.0,
            "distance_m": 10.0, "site_m": [list(p0), list(p1)],
            "lat": 30.0, "lon": 31.0, "way_a": way_a, "way_b": way_b,
            "out_of_scope": None}


def _dump(rows, patch="X.osm", knobs=None, frame="own"):
    return {"patch": patch,
            "provenance": {"sha": "deadbeef", "dirty": "false"},
            "axis_frame": {"frame": frame},
            "law_true_knobs": dict(knobs or KNOBS),
            "n_rows": len(rows), "rows": rows}


def _write(tmp_path, name, dump):
    p = tmp_path / name
    p.write_text(json.dumps(dump), encoding="utf-8", newline="")
    return p


# ── the join, four tiers, one hand-built scene ──────────────────────

def test_the_four_tiers_are_what_they_say():
    """One row identical, one moved 0.20 m, one gone, one new.

    Hand answer: EXACT 1, MOVED 1 (separation exactly 0.20 m), GONE 1,
    NEW 1, NET 0.
    """
    same = _row(p0=(0, 0), p1=(10, 0), way_a="-1")
    moved_a = _row(p0=(0, 50), p1=(10, 50), mag=1.0, way_a="-2")
    moved_b = _row(p0=(0, 50.2), p1=(10, 50.2), mag=1.5, way_a="-2")
    gone = _row(p0=(0, 100), p1=(10, 100), way_a="-3")
    new = _row(p0=(0, 900), p1=(10, 900), way_a="-4")
    res = CRD.diff_rows([same, moved_a, gone], [same, moved_b, new],
                        tol_m=0.5)
    assert len(res["exact"]) == 1
    assert len(res["moved"]) == 1
    assert res["moved"][0][2] == pytest.approx(0.2, abs=1e-9)
    assert [r["way_a"] for r in res["gone"]] == ["-3"]
    assert [r["way_a"] for r in res["new"]] == ["-4"]


def test_tolerance_is_the_knob_that_decides_moved_vs_new_and_gone():
    """The SAME pair reads MOVED at 0.5 m and NEW+GONE at 0.1 m.

    This is why the tolerance is printed with every table: raising it
    can only convert NEW/GONE into MOVED, never the reverse.
    """
    a = [_row(p0=(0, 0), p1=(10, 0))]
    b = [_row(p0=(0, 0.2), p1=(10, 0.2))]
    wide = CRD.diff_rows(a, b, tol_m=0.5)
    tight = CRD.diff_rows(a, b, tol_m=0.1)
    assert (len(wide["moved"]), len(wide["new"]), len(wide["gone"])) == (1, 0, 0)
    assert (len(tight["moved"]), len(tight["new"]), len(tight["gone"])) == (0, 1, 1)


def test_a_row_never_matches_across_its_class():
    """Same coordinates, different FAMILY / ROLE PAIR / SIDE — three
    different defects at one place, and none of them is the other."""
    a = [_row(family="within_shape"),
         _row(family="within_shape", roles="apron|graded_strip"),
         _row(family="within_shape", side="groundside")]
    b = [_row(family="transverse")]
    res = CRD.diff_rows(a, b, tol_m=5.0)
    assert len(res["exact"]) == 0 and len(res["moved"]) == 0
    assert len(res["gone"]) == 3 and len(res["new"]) == 1


def test_endpoint_order_is_not_a_difference():
    """One edge spelled A-B in the control and B-A in the arm is ONE
    edge — the site key sorts its endpoints."""
    a = [_row(p0=(0, 0), p1=(10, 0))]
    b = [_row(p0=(10, 0), p1=(0, 0))]
    res = CRD.diff_rows(a, b, tol_m=0.0)
    assert len(res["exact"]) == 1, res


def test_each_partner_is_used_once():
    """Two A rows at one site and ONE B row: exactly one pairs, the
    other is GONE.  A join that reused the partner would report churn
    as balance."""
    a = [_row(p0=(0, 0), p1=(10, 0), way_a="-1"),
         _row(p0=(0, 0), p1=(10, 0), way_a="-2")]
    b = [_row(p0=(0, 0), p1=(10, 0), way_a="-1")]
    res = CRD.diff_rows(a, b, tol_m=0.5)
    assert len(res["exact"]) == 1
    assert len(res["gone"]) == 1 and not res["new"]


def test_nearest_partner_wins():
    """With two candidates in tolerance the join takes the NEAREST, and
    the far one is left for its own nearest partner."""
    a = [_row(p0=(0, 0), p1=(10, 0), way_a="-1"),
         _row(p0=(0, 0.4), p1=(10, 0.4), way_a="-2")]
    b = [_row(p0=(0, 0.02), p1=(10, 0.02), mag=9.0),
         _row(p0=(0, 0.38), p1=(10, 0.38), mag=8.0)]
    res = CRD.diff_rows(a, b, tol_m=0.5)
    assert len(res["moved"]) == 2 and not res["new"] and not res["gone"]
    by_a = {ra["way_a"]: (rb["magnitude_m"], s) for ra, rb, s in res["moved"]}
    assert by_a["-1"][0] == 9.0 and by_a["-2"][0] == 8.0


def test_exact_beats_near_even_when_a_nearer_partner_exists():
    """A coordinate-identical partner is an identity; a near one is an
    inference.  The identity is consumed first."""
    a = [_row(p0=(0, 0), p1=(10, 0), way_a="-1")]
    b = [_row(p0=(0, 0.01), p1=(10, 0.01), way_a="-9", mag=7.0),
         _row(p0=(0, 0), p1=(10, 0), way_a="-1", mag=3.0)]
    res = CRD.diff_rows(a, b, tol_m=0.5)
    assert len(res["exact"]) == 1
    assert res["exact"][0][1]["magnitude_m"] == 3.0
    assert [r["way_a"] for r in res["new"]] == ["-9"]


# ── the refusals ────────────────────────────────────────────────────

def test_it_refuses_a_join_across_law_knobs(tmp_path):
    a = _write(tmp_path, "a.json", _dump([_row()]))
    b = _write(tmp_path, "b.json",
               _dump([_row()], knobs=dict(KNOBS, max_grade_pct=4.0)))
    with pytest.raises(SystemExit) as e:
        CRD.main([str(a), str(b)])
    assert "different law knobs" in str(e.value)


def test_it_refuses_a_join_across_axis_frames(tmp_path):
    a = _write(tmp_path, "a.json", _dump([_row()], frame="own"))
    b = _write(tmp_path, "b.json", _dump([_row()], frame="base"))
    with pytest.raises(SystemExit) as e:
        CRD.main([str(a), str(b)])
    assert "AXIS FRAME" in str(e.value)


def test_it_refuses_a_class_level_census_json(tmp_path):
    p = tmp_path / "census.json"
    p.write_text(json.dumps({"patch": "x", "lawtrue": {"total": 3}}), encoding="utf-8", newline="")
    q = _write(tmp_path, "b.json", _dump([_row()]))
    with pytest.raises(SystemExit) as e:
        CRD.main([str(p), str(q)])
    assert "--rows-json" in str(e.value)


def test_it_refuses_a_truncated_dump(tmp_path):
    d = _dump([_row()])
    d["n_rows"] = 5
    p = _write(tmp_path, "a.json", d)
    q = _write(tmp_path, "b.json", _dump([_row()]))
    with pytest.raises(SystemExit) as e:
        CRD.main([str(p), str(q)])
    assert "truncated" in str(e.value)


# ── the report is the join, not a recount ───────────────────────────

def test_the_report_counts_are_the_join_and_the_filter_is_report_only(
        tmp_path, capsys):
    """A side filter narrows the TABLES; it must not change which rows
    matched (a join run on a filtered population would invent NEW rows
    whose partner was filtered out)."""
    a_rows = [_row(side="airside", p0=(0, 0), p1=(10, 0)),
              _row(side="groundside", p0=(0, 20), p1=(10, 20))]
    b_rows = [_row(side="airside", p0=(0, 0), p1=(10, 0)),
              _row(side="groundside", p0=(0, 900), p1=(10, 900))]
    a = _write(tmp_path, "a.json", _dump(a_rows))
    b = _write(tmp_path, "b.json", _dump(b_rows))
    CRD.main([str(a), str(b), "--side", "airside"])
    text = capsys.readouterr().out
    assert "EXACT (same class, coordinates identical to 1 mm) : 1" in text
    assert "NEW   (B only, no partner)                        : 0" in text
    assert "GONE  (A only, no partner)                        : 0" in text
    assert "REPORT FILTER" in text


def test_json_out_carries_every_new_and_gone_row(tmp_path):
    a = _write(tmp_path, "a.json",
               _dump([_row(p0=(0, 0), p1=(1, 0), way_a="-7")]))
    b = _write(tmp_path, "b.json",
               _dump([_row(p0=(0, 90), p1=(1, 90), way_a="-8")]))
    out = tmp_path / "d.json"
    CRD.main([str(a), str(b), "--json", str(out)])
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["counts"] == {"exact": 0, "moved": 0, "gone": 1, "new": 1}
    assert d["new"][0]["way_a"] == "-8"
    assert d["gone"][0]["way_a"] == "-7"
    assert d["law_true_knobs"] == KNOBS


# ── site-less rows join by identity, never by site (#733) ───────────

def _conflict(row, lat, lon, tier="pad", s_m=0.3):
    """A ``hard_conflict`` row as the census dumps it: every one at
    ``site_m`` [[0,0],[0,0]] on the shared way id, named only by its
    way ref."""
    r = _row(family="hard_conflict", roles="apron|apron", p0=(0, 0),
             p1=(0, 0), mag=s_m, way_a="hard_conflict",
             way_b="hard_conflict")
    ref = f"hard_conflict:{tier}:{row}"
    r.update(lat=lat, lon=lon, ref_a=ref, ref_b=ref)
    return r


def test_siteless_rows_join_by_identity_not_by_the_shared_origin():
    """A holds conflicts r1, r2, r3; B holds r2, r3, r4 (equal counts).

    Hand answer: EXACT 2 (r2, r3), GONE [r1], NEW [r4], MOVED 0.  Joined
    on the shared origin site, every row paired with some other row and
    the diff read EXACT 3 — the real change vanished (HECA's 38 far
    "new" conflicts were the same mis-join with unequal counts).
    """
    r1 = _conflict("pad_flat:1", 30.10, 31.10)
    r2 = _conflict("pad_flat:2", 30.20, 31.20)
    r3 = _conflict("taxi_ramp:3", 30.30, 31.30)
    r4 = _conflict("pad_flat:4", 30.40, 31.40)
    res = CRD.diff_rows([r1, r2, r3], [r4, r3, r2], tol_m=0.5)
    assert sorted(a["ref_a"] for a, b in res["exact"]) == [
        "hard_conflict:pad:pad_flat:2", "hard_conflict:pad:taxi_ramp:3"]
    assert all(a["ref_a"] == b["ref_a"] for a, b in res["exact"])
    assert res["moved"] == []
    assert [r["ref_a"] for r in res["gone"]] == ["hard_conflict:pad:pad_flat:1"]
    assert [r["ref_a"] for r in res["new"]] == ["hard_conflict:pad:pad_flat:4"]


def test_siteless_rows_never_join_as_moved_at_any_tolerance():
    """Two different conflicts both at the origin are 0 m apart by site;
    with no site of their own they must stay GONE + NEW, never MOVED."""
    a = [_conflict("pad_flat:1", 30.1, 31.1)]
    b = [_conflict("pad_flat:9", 30.9, 31.9)]
    res = CRD.diff_rows(a, b, tol_m=1e6)
    assert res["exact"] == [] and res["moved"] == []
    assert len(res["gone"]) == 1 and len(res["new"]) == 1


def test_a_sited_row_is_not_read_as_siteless():
    assert not CRD.is_siteless(_row(p0=(0, 0), p1=(10, 0)))
    assert CRD.is_siteless(_row(p0=(0, 0), p1=(0, 0)))
    assert CRD.is_siteless(dict(_row(), site_m=None))
