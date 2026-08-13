"""Twins for ``tools/corridor_axis_coverage.py`` and ``tools/arm_site_read.py``.

Both were promoted on their SECOND use (RULINGS `7e90032`, promote-on-reuse)
out of the service-corridor round's lane scratchpad: the first read produced
that round's HECA corridor-A/B coverage table, the second its acceptance
re-measure, and the site/seat read carried the airside +252 attribution.

What these twins pin, for each tool:
  * the CLI's printed answer IS the library entry's result (no second
    derivation living in ``main``),
  * every refusal refuses instead of guessing,
  * the frame parameters MOVE the answer (a halo, a radius) and are
    reported, so two runs at two settings can never be compared silently,
  * neither tool counts a defect: rows come from a census dump and nothing
    else, and axis membership comes from ``axes_exact`` and nothing else,
  * the INDEX row exists (a tool absent from the index is treated as
    absent).

Hand-built sidecars and patches; no build, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import arm_site_read as ASR                                   # noqa: E402
import corridor_axis_coverage as CAC                          # noqa: E402

# A corridor 600 m long at HECA's latitude, laid due east from A.
LAT0, LON0 = 30.1121738, 31.4062992
M_PER_DEG = 111320.0


def _east(metres):
    import math
    return LON0 + metres / (M_PER_DEG * math.cos(math.radians(LAT0)))


def _axis(s0_m, s1_m, *, service=True, n=2, offset_m=0.0):
    """A straight service axis from ``s0_m`` to ``s1_m`` along the corridor."""
    import math
    lat = LAT0 + offset_m / M_PER_DEG
    pts = [[lat, _east(s0_m + (s1_m - s0_m) * k / (n - 1))]
           for k in range(n)]
    return [pts, [0.08] * (n - 1), -1, service]


def _sidecar(tmp_path, axes, key="axes_exact"):
    p = tmp_path / "patch.osm.axes.json"
    p.write_text(json.dumps({key: axes, "anchor": [LAT0, LON0]}))
    return p


CORRIDOR = f"A={LAT0},{LON0}:{LAT0},{_east(600.0)}"


class TestCorridorAxisCoverage:

    def test_the_fragmented_state_reports_its_gaps(self, tmp_path):
        """The named HECA defect: four disjoint 2-node axes with holes."""
        axes = [_axis(0, 51), _axis(55, 97), _axis(254, 269), _axis(593, 600)]
        res = CAC.corridor_coverage(
            CAC.load_axes(_sidecar(tmp_path, axes)),
            (LAT0, LON0), (LAT0, _east(600.0)))
        assert res["axes_touching"] == 4
        assert [[round(a), round(b)] for a, b in res["gaps"]] == [
            [51, 55], [97, 254], [269, 593]]
        assert res["covered_m"] < 150.0

    def test_one_chain_end_to_end_has_no_gap(self, tmp_path):
        axes = [_axis(0, 600, n=25)]
        res = CAC.corridor_coverage(
            CAC.load_axes(_sidecar(tmp_path, axes)),
            (LAT0, LON0), (LAT0, _east(600.0)))
        assert res["gaps"] == []
        assert res["axes_touching"] == 1
        assert res["axes"][0]["span_m"] == pytest.approx(600.0, abs=2.0)

    def test_two_chains_meeting_exactly_leave_no_gap(self, tmp_path):
        """Continuity is a property of the COVER, not of the chain count."""
        axes = [_axis(0, 480, n=9), _axis(480, 600, n=5)]
        res = CAC.corridor_coverage(
            CAC.load_axes(_sidecar(tmp_path, axes)),
            (LAT0, LON0), (LAT0, _east(600.0)))
        assert res["gaps"] == [] and res["axes_touching"] == 2

    def test_the_halo_moves_the_answer_and_is_reported(self, tmp_path):
        """A corridor that bends away from its chord reads as a gap under a
        tight halo — which is why the halo is on every report."""
        axes = [_axis(0, 600, n=9, offset_m=9.0)]
        side = CAC.load_axes(_sidecar(tmp_path, axes))
        tight = CAC.corridor_coverage(side, (LAT0, LON0), (LAT0, _east(600.0)),
                                      halo_m=5.0)
        wide = CAC.corridor_coverage(side, (LAT0, LON0), (LAT0, _east(600.0)),
                                     halo_m=12.0)
        assert tight["axes_touching"] == 0 and tight["gaps"]
        assert wide["axes_touching"] == 1 and wide["gaps"] == []
        assert tight["halo_m"] == 5.0 and wide["halo_m"] == 12.0

    def test_aircraft_axes_are_not_service_axes(self, tmp_path):
        axes = [_axis(0, 600, n=9, service=False)]
        side = CAC.load_axes(_sidecar(tmp_path, axes))
        assert CAC.corridor_coverage(side, (LAT0, LON0),
                                     (LAT0, _east(600.0)))["axes_touching"] == 0
        assert CAC.corridor_coverage(
            side, (LAT0, LON0), (LAT0, _east(600.0)),
            service_only=False)["axes_touching"] == 1

    def test_a_sidecar_without_axes_exact_is_refused(self, tmp_path):
        p = _sidecar(tmp_path, [_axis(0, 600)], key="axes")
        with pytest.raises(CAC.CoverageRefusal):
            CAC.load_axes(p)

    def test_a_degenerate_corridor_is_refused(self, tmp_path):
        side = CAC.load_axes(_sidecar(tmp_path, [_axis(0, 600)]))
        with pytest.raises(CAC.CoverageRefusal):
            CAC.corridor_coverage(side, (LAT0, LON0), (LAT0, _east(5.0)))

    def test_a_bad_corridor_spec_is_refused_naming_the_token(self):
        with pytest.raises(CAC.CoverageRefusal) as exc:
            CAC.parse_corridor("A=30.1,31.4")
        assert "A=30.1,31.4" in str(exc.value)

    def test_the_cli_json_is_the_library_result(self, tmp_path, capsys):
        axes = [_axis(0, 51), _axis(254, 600, n=5)]
        side = _sidecar(tmp_path, axes)
        out = tmp_path / "out.json"
        assert CAC.main([str(side), "--corridor", CORRIDOR,
                         "--json", str(out)]) == 0
        printed = json.loads(out.read_text())["corridors"]["A"]
        assert printed == CAC.corridor_coverage(
            CAC.load_axes(side), (LAT0, LON0), (LAT0, _east(600.0)))
        assert "AXIS-FREE GAPS" in capsys.readouterr().out

    def test_the_cli_refuses_with_a_nonzero_exit(self, tmp_path, capsys):
        side = _sidecar(tmp_path, [_axis(0, 600)], key="axes")
        assert CAC.main([str(side), "--corridor", CORRIDOR]) == 2
        assert "REFUSED" in capsys.readouterr().err


# ──────────────────────────────────────────────────────────────────────
# arm_site_read
# ──────────────────────────────────────────────────────────────────────

def _rows_dump(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text(json.dumps({"patch": "x", "n_rows": len(rows), "rows": rows}))
    return p


def _row(lat, lon, *, family="within_shape", roles="apron|apron",
         de=1.0, grade=1.5):
    return {"family": family, "roles": roles, "side": "airside",
            "magnitude_m": de, "grade_pct": grade, "cap_pct": None,
            "distance_m": 100.0, "site_m": [[0, 0], [1, 1]],
            "lat": lat, "lon": lon, "way_a": "-1", "way_b": "-1",
            "out_of_scope": None}


class TestArmSiteRead:

    def test_rows_near_selects_by_radius_and_reports_the_worst(self):
        rows = [_row(LAT0, LON0, de=0.5, grade=1.2),
                _row(LAT0, _east(10.0), de=2.5, grade=9.9),
                _row(LAT0, _east(400.0), de=9.0, grade=30.0)]
        near = ASR.rows_near(rows, LAT0, LON0, 25.0)
        assert near["n_rows"] == 2
        assert near["worst_grade_pct"] == pytest.approx(9.9)
        assert near["worst_magnitude_m"] == pytest.approx(2.5)
        assert near["families"] == ["within_shape::apron|apron"]

    def test_the_radius_moves_the_answer(self):
        rows = [_row(LAT0, _east(400.0))]
        assert ASR.rows_near(rows, LAT0, LON0, 25.0)["n_rows"] == 0
        assert ASR.rows_near(rows, LAT0, LON0, 500.0)["n_rows"] == 1

    def test_a_row_with_no_coordinate_is_skipped_not_counted_at_zero(self):
        bad = _row(LAT0, LON0)
        bad["lat"] = None
        assert ASR.rows_near([bad], LAT0, LON0, 25.0)["n_rows"] == 0

    def test_a_dump_that_is_not_a_census_dump_is_refused(self, tmp_path):
        p = tmp_path / "not.json"
        p.write_text(json.dumps({"whatever": 1}))
        with pytest.raises(ASR.SiteReadRefusal):
            ASR.load_rows(p)

    def test_seats_join_by_ref_and_report_the_movers(self, tmp_path):
        cg = ASR._check_grade()

        def _patch(name, alt):
            p = tmp_path / name
            def _node(nid, lat, lon):
                # the emitted dialect: alt_abs is a CHILD tag, not an
                # attribute (``check_grade._NODE_ALT_RE``)
                return (f"  <node id='{nid}' lat='{lat}' lon='{lon}'>\n"
                        f"    <tag k='alt_abs' v='{alt}'/>\n  </node>\n")
            p.write_text(
                "<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
                + _node("-1", LAT0, LON0)
                + _node("-2", LAT0 + 1e-4, LON0)
                + _node("-3", LAT0 + 1e-4, _east(20.0))
                + "  <way id='-10'>\n    <nd ref='-1'/>\n    <nd ref='-2'/>\n"
                "    <nd ref='-3'/>\n    <nd ref='-1'/>\n"
                "    <tag k='aeroway' v='building'/>\n"
                "    <tag k='role' v='building'/>\n"
                "    <tag k='ref' v='building211'/>\n  </way>\n</osm>\n")
            return p
        ctl, arm = _patch("ctl.osm", 76.55), _patch("arm.osm", 77.43)
        res = ASR.seat_moves(cg, ctl, arm)
        assert res["pads_joined"] == 1 and res["pads_moved"] == 1
        assert res["worst"][0]["ref"] == "building211"
        assert res["worst"][0]["delta_m"] == pytest.approx(0.88, abs=0.001)
        # ...and a floor above the move reports NO mover (never a rounding
        # accident).
        assert ASR.seat_moves(cg, ctl, arm, floor_m=1.0)["pads_moved"] == 0

    def test_the_cli_json_is_the_library_result(self, tmp_path, capsys):
        rows_c = _rows_dump(tmp_path, "c.rows.json", [_row(LAT0, LON0, de=1.0)])
        rows_a = _rows_dump(tmp_path, "a.rows.json",
                            [_row(LAT0, LON0, de=1.0), _row(LAT0, LON0, de=2.0)])
        patch = tmp_path / "p.osm"
        patch.write_text("<?xml version='1.0' encoding='UTF-8'?>\n"
                         "<osm version='0.6'>\n</osm>\n")
        out = tmp_path / "out.json"
        assert ASR.main([str(patch), str(patch), "--site", f"S={LAT0},{LON0}",
                         "--rows", str(rows_c), str(rows_a),
                         "--json", str(out)]) == 0
        got = json.loads(out.read_text())["sites"]["S"]
        assert got["control"] == ASR.rows_near(
            ASR.load_rows(rows_c), LAT0, LON0, 25.0)
        assert got["arm"] == ASR.rows_near(
            ASR.load_rows(rows_a), LAT0, LON0, 25.0)
        assert "rows" in capsys.readouterr().out

    def test_absent_row_dumps_report_SKIPPED_not_zero(self, tmp_path, capsys):
        patch = tmp_path / "p.osm"
        patch.write_text("<?xml version='1.0' encoding='UTF-8'?>\n"
                         "<osm version='0.6'>\n</osm>\n")
        assert ASR.main([str(patch), str(patch),
                         "--site", f"S={LAT0},{LON0}"]) == 0
        assert "SKIPPED" in capsys.readouterr().out


def test_both_tools_carry_an_index_row():
    """A tool absent from ``tools/INDEX.md`` is treated as absent."""
    index = (ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "Ortho4XP/tools/corridor_axis_coverage.py" in index
    assert "Ortho4XP/tools/arm_site_read.py" in index
