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


# ──────────────────────────────────────────────────────────────────────
# corridor-joins round: the two acceptance instruments (spec ruling 4)
# ──────────────────────────────────────────────────────────────────────

def _seam_patch(tmp_path, name, *, shared: bool, road_alt=216.95,
                air_alt=219.23, wall=False, way_alt=False):
    """A road-family way and an airside way at one site, sharing a node or
    standing 0.999 m apart — the KCLT seam, both states.

    ``way_alt`` writes the values as WAY tags instead of per-node
    ``alt_abs``: the dialect in which two ways can genuinely disagree at a
    shared node (a torn weld).  With node values — production's usual
    spelling — a shared node is single-valued by construction, which is
    itself worth pinning.
    """
    def node(nid, lat, lon, alt):
        if way_alt:
            return f"  <node id='{nid}' lat='{lat:.9f}' lon='{lon:.9f}'/>\n"
        return (f"  <node id='{nid}' lat='{lat:.9f}' lon='{lon:.9f}'>\n"
                f"    <tag k='alt_abs' v='{alt}'/>\n  </node>\n")

    def alt_tag(v):
        return f"    <tag k='altitude' v='{v}'/>\n" if way_alt else ""
    txt = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    # airside ring: a 20 m square east of the site
    for k, (dlat, dlon) in enumerate(((0.0, 0.0), (20.0, 0.0),
                                      (20.0, 20.0), (0.0, 20.0))):
        txt.append(node(f"-{10 + k}", LAT0 + dlat / M_PER_DEG,
                        _east(dlon), air_alt))
    # road ring: west of it, either sharing node -10 or standing off
    off = 0.0 if shared else 0.999
    for k, (dlat, dlon) in enumerate(((0.0, -20.0 - off), (20.0, -20.0 - off),
                                      (20.0, -off))):
        txt.append(node(f"-{20 + k}", LAT0 + dlat / M_PER_DEG,
                        _east(dlon), road_alt))
    road_last = "-10" if shared else "-23"
    if not shared:
        txt.append(node("-23", LAT0, _east(-off), road_alt))
    if wall:
        for k in range(3):
            txt.append(node(f"-{30 + k}", LAT0 + k / M_PER_DEG,
                            _east(-0.5), road_alt))
    txt.append("  <way id='-100'>\n"
               + "".join(f"    <nd ref='-{10 + k}'/>\n" for k in range(4))
               + "    <nd ref='-10'/>\n"
               "    <tag k='role' v='apron'/>\n"
               + alt_tag(air_alt)
               + "    <tag k='aeroway' v='apron'/>\n  </way>\n")
    txt.append("  <way id='-200'>\n"
               + "".join(f"    <nd ref='-{20 + k}'/>\n" for k in range(3))
               + f"    <nd ref='{road_last}'/>\n    <nd ref='-20'/>\n"
               "    <tag k='role' v='service_junction'/>\n"
               + alt_tag(road_alt)
               + "    <tag k='aeroway' v='taxiway'/>\n  </way>\n")
    if wall:
        txt.append("  <way id='-13314'>\n"
                   + "".join(f"    <nd ref='-{30 + k}'/>\n" for k in range(3))
                   + "    <nd ref='-30'/>\n"
                   "    <tag k='role' v='retaining_wall'/>\n"
                   "    <tag k='aeroway' v='taxiway'/>\n  </way>\n")
    txt.append("</osm>\n")
    p = tmp_path / name
    p.write_text("".join(txt))
    return p


class TestSeamWelds:
    """``arm_site_read --welds`` — ruling 4(a)'s instrument."""

    def test_an_unwelded_seam_reports_its_gap_where_a_census_is_silent(
            self, tmp_path):
        cg = ASR._check_grade()
        p = _seam_patch(tmp_path, "unwelded.osm", shared=False)
        res = ASR.seam_welds(cg, p, LAT0, LON0, 60.0)
        assert res["shared_nodes"] == 0
        assert res["nearest_unwelded_m"] == pytest.approx(0.999, abs=0.02)

    def test_a_welded_seam_reports_its_shared_nodes(self, tmp_path):
        cg = ASR._check_grade()
        p = _seam_patch(tmp_path, "welded.osm", shared=True)
        res = ASR.seam_welds(cg, p, LAT0, LON0, 60.0)
        assert res["shared_nodes"] >= 1
        assert res["nearest_unwelded_m"] is None

    def test_a_torn_weld_is_reported_by_its_seam_delta(self, tmp_path):
        """A SHARED node whose two ways carry different values is a torn
        weld — the number the ruling wants at 0.00."""
        cg = ASR._check_grade()
        p = _seam_patch(tmp_path, "torn.osm", shared=True, way_alt=True,
                        road_alt=216.95, air_alt=219.23)
        res = ASR.seam_welds(cg, p, LAT0, LON0, 60.0)
        assert res["max_seam_dalt_m"] == pytest.approx(2.28, abs=0.001)

    def test_a_node_valued_weld_is_single_valued_by_construction(self,
                                                                tmp_path):
        """Production's usual spelling puts the value on the NODE, so a
        welded seam reads 0.00 because there is ONE value — which is the
        ruling's construction, and why the SHARED COUNT is the primary
        evidence and the delta is the guard."""
        cg = ASR._check_grade()
        p = _seam_patch(tmp_path, "node_valued.osm", shared=True,
                        road_alt=216.95, air_alt=219.23)
        res = ASR.seam_welds(cg, p, LAT0, LON0, 60.0)
        assert res["shared_nodes"] >= 1
        assert res["max_seam_dalt_m"] == 0.0

    def test_walls_at_the_site_are_counted_with_their_ids(self, tmp_path):
        cg = ASR._check_grade()
        p = _seam_patch(tmp_path, "walled.osm", shared=True, wall=True)
        res = ASR.seam_welds(cg, p, LAT0, LON0, 60.0)
        assert res["walls"] == 1 and "-13314" in res["wall_wids"]

    def test_the_radius_moves_the_answer(self, tmp_path):
        cg = ASR._check_grade()
        p = _seam_patch(tmp_path, "far.osm", shared=True)
        assert ASR.seam_welds(cg, p, LAT0, _east(-400.0),
                              5.0)["shared_nodes"] == 0

    def test_the_cli_json_is_the_library_result(self, tmp_path, capsys):
        p = _seam_patch(tmp_path, "cli.osm", shared=True, wall=True)
        out = tmp_path / "welds.json"
        assert ASR.main([str(p), str(p), "--site", f"M={LAT0},{LON0}",
                         "--radius", "60", "--welds", "--json",
                         str(out)]) == 0
        got = json.loads(out.read_text())["welds"]["M"]["arm"]
        assert got == ASR.seam_welds(ASR._check_grade(), p, LAT0, LON0, 60.0)
        assert "SEAM WELDS" in capsys.readouterr().out

    def test_welds_without_a_site_read_the_WHOLE_PATCH(self, tmp_path,
                                                       capsys):
        """An airport with no owner-named site still has an answer: the
        patch-wide table (the CYXY/KSTJ reading)."""
        p = _seam_patch(tmp_path, "nosite.osm", shared=True)
        assert ASR.main([str(p), str(p), "--welds"]) == 0
        printed = capsys.readouterr().out
        assert "WHOLE PATCH" in printed
        assert (ASR.seam_welds(ASR._check_grade(), p)["shared_nodes"]
                == ASR.seam_welds(ASR._check_grade(), p, LAT0, LON0,
                                  500.0)["shared_nodes"])

    def test_mouths_cluster_so_the_ge2_rule_is_per_mouth(self, tmp_path):
        """"≥2 shared nodes per MOUTH" is not a patch total: the shared
        nodes cluster at the tool's stated window."""
        cg = ASR._check_grade()
        p = _seam_patch(tmp_path, "clustered.osm", shared=True)
        res = ASR.seam_welds(cg, p)
        assert res["mouths"] >= 1
        assert res["mouth_cluster_m"] == ASR.MOUTH_CLUSTER_M
        assert sum(m["shared_nodes"] for m in res["mouth_list"]) \
            == res["shared_nodes"]


def _free_end_sidecar(tmp_path, recs, *, key=True):
    p = tmp_path / "fe.osm.axes.json"
    body = {"axes_exact": [], "anchor": [LAT0, LON0]}
    if key:
        body["svc_free_ends"] = recs
    p.write_text(json.dumps(body))
    return p


def _road_patch(tmp_path, alts):
    """A service_road way whose nodes march east from the site."""
    def node(nid, lon, alt):
        return (f"  <node id='{nid}' lat='{LAT0:.9f}' lon='{lon:.9f}'>\n"
                f"    <tag k='alt_abs' v='{alt}'/>\n  </node>\n")
    txt = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    for k, (d, a) in enumerate(alts):
        txt.append(node(f"-{40 + k}", _east(d), a))
    txt.append("  <way id='-300'>\n"
               + "".join(f"    <nd ref='-{40 + k}'/>\n"
                         for k in range(len(alts)))
               + "    <nd ref='-40'/>\n"
               "    <tag k='role' v='service_road'/>\n"
               "    <tag k='aeroway' v='taxiway'/>\n  </way>\n</osm>\n")
    p = tmp_path / "road.osm"
    p.write_text("".join(txt))
    return p


class TestFreeEndOffsets:
    """``corridor_axis_coverage --free-ends`` — ruling 4(b)'s instrument."""

    def test_a_patch_from_before_the_round_is_refused(self, tmp_path):
        """No published DEM frame ⇒ no answer, never a substituted one."""
        with pytest.raises(CAC.CoverageRefusal):
            CAC.load_free_ends(_free_end_sidecar(tmp_path, [], key=False))

    def test_a_geometry_only_build_is_refused(self, tmp_path):
        with pytest.raises(CAC.CoverageRefusal):
            CAC.load_free_ends(_free_end_sidecar(tmp_path, None))

    def test_a_build_with_no_free_end_reads_empty_not_refused(self, tmp_path):
        assert CAC.load_free_ends(_free_end_sidecar(tmp_path, [])) == []

    def test_an_end_on_dem_reports_a_zero_offset(self, tmp_path):
        rec = {"lat": LAT0, "lon": LON0, "dem_m": 213.5, "target_m": 213.5,
               "clamped": False, "nodes": 2}
        patch = _road_patch(tmp_path, [(0.0, 213.5), (20.0, 215.0)])
        (row,) = CAC.free_end_offsets([rec], CAC._road_nodes(patch))
        assert row["offset_m"] == pytest.approx(0.0, abs=1e-6)
        assert row["over_floor"] is False

    def test_the_measured_defect_is_reported_as_over_floor(self, tmp_path):
        """THE KCLT NUMBER: 6.31 m proud of DEM at the acceptance
        coordinate — an instrument that cannot see this is the one the
        round replaced."""
        rec = {"lat": LAT0, "lon": LON0, "dem_m": 213.5, "target_m": 213.5,
               "clamped": False, "nodes": 2}
        patch = _road_patch(tmp_path, [(0.0, 219.81), (20.0, 220.0)])
        (row,) = CAC.free_end_offsets([rec], CAC._road_nodes(patch))
        assert row["offset_m"] == pytest.approx(6.31, abs=1e-6)
        assert row["over_floor"] is True

    def test_a_clamped_end_carries_its_own_disposition(self, tmp_path):
        rec = {"lat": LAT0, "lon": LON0, "dem_m": 100.0, "target_m": 213.5,
               "clamped": True, "nodes": 2}
        patch = _road_patch(tmp_path, [(0.0, 213.5), (20.0, 215.0)])
        (row,) = CAC.free_end_offsets([rec], CAC._road_nodes(patch))
        assert row["clamped"] is True
        assert row["offset_m"] == pytest.approx(113.5, abs=1e-6)

    def test_the_slack_is_the_road_cap_over_the_match_distance(self,
                                                              tmp_path):
        """A matched node metres from the terminus is lawfully carried away
        from it by the road's OWN cap — the offset is judged against that,
        not against a bare floor."""
        rec = {"lat": LAT0, "lon": LON0, "dem_m": 213.5, "target_m": 213.5,
               "clamped": False, "nodes": 2}
        patch = _road_patch(tmp_path, [(5.0, 213.8), (25.0, 215.0)])
        (row,) = CAC.free_end_offsets([rec], CAC._road_nodes(patch))
        assert row["match_m"] == pytest.approx(5.0, abs=0.05)
        assert row["lawful_slack_m"] == pytest.approx(
            CAC._road_cap() * 5.0 + CAC.FREE_END_FLOOR_M, abs=0.002)
        assert row["over_floor"] is False

    def test_an_end_with_no_road_node_reports_None_not_zero(self, tmp_path):
        rec = {"lat": LAT0, "lon": LON0, "dem_m": 213.5, "target_m": 213.5,
               "clamped": False, "nodes": 2}
        patch = _road_patch(tmp_path, [(400.0, 213.5), (420.0, 215.0)])
        (row,) = CAC.free_end_offsets([rec], CAC._road_nodes(patch))
        assert row["emitted_m"] is None and row["offset_m"] is None

    def test_the_transect_reports_the_cliff_as_a_spread(self, tmp_path):
        """The 'no cliff on the old wall's footprint' read: the altitude
        SPREAD the road carries around the terminus."""
        rec = {"lat": LAT0, "lon": LON0, "dem_m": 213.5, "target_m": 213.5,
               "clamped": False, "nodes": 2}
        patch = _road_patch(tmp_path, [(0.0, 213.5), (10.0, 223.5)])
        (row,) = CAC.free_end_offsets([rec], CAC._road_nodes(patch))
        assert row["transect_spread_m"] == pytest.approx(10.0, abs=1e-6)

    def test_the_cli_json_is_the_library_result(self, tmp_path, capsys):
        rec = {"lat": LAT0, "lon": LON0, "dem_m": 213.5, "target_m": 213.5,
               "clamped": False, "nodes": 2}
        sidecar = _free_end_sidecar(tmp_path, [rec])
        patch = _road_patch(tmp_path, [(0.0, 213.5), (20.0, 215.0)])
        out = tmp_path / "fe.json"
        assert CAC.main([str(sidecar), "--free-ends", str(patch),
                         "--json", str(out)]) == 0
        got = json.loads(out.read_text())["free_ends"]
        assert got == json.loads(json.dumps(
            CAC.free_end_offsets([rec], CAC._road_nodes(patch))))
        assert "FREE-END DEM offsets" in capsys.readouterr().out

    def test_asking_nothing_is_refused(self, tmp_path, capsys):
        assert CAC.main([str(_free_end_sidecar(tmp_path, []))]) == 2


def test_both_tools_carry_an_index_row():
    """A tool absent from ``tools/INDEX.md`` is treated as absent."""
    index = (ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "Ortho4XP/tools/corridor_axis_coverage.py" in index
    assert "Ortho4XP/tools/arm_site_read.py" in index


# ══════════════════════════════════════════════════════════════════════
# --profile — THE VERTICAL end-to-end read (staged-solve round, S2)
# ══════════════════════════════════════════════════════════════════════

def _profile_sidecar(tmp_path, n_pts=41, step_m=5.0, service=True):
    """A sidecar whose single ``axes_exact`` entry is a straight service
    axis marching east from the site."""
    pts = [[LAT0, _east(k * step_m)] for k in range(n_pts)]
    p = tmp_path / "prof.osm.axes.json"
    p.write_text(json.dumps({"axes_exact": [[pts, [], 0, service]]}))
    return p


class TestVerticalProfile:
    """``--profile``: the hump, the cap-riding runs and the pockets."""

    def test_prominence_finds_a_hump_and_ignores_a_monotone_ramp(self):
        assert CAC.prominence([0.0, 1.0, 2.0, 3.0]) == []
        hump = CAC.prominence([0.0, 0.0, 6.18, 0.0, 0.0])
        assert len(hump) == 1
        assert hump[0]["kind"] == "peak"
        assert hump[0]["prominence_m"] == pytest.approx(6.18)

    def test_prominence_reads_a_pocket_as_a_pocket(self):
        rows = CAC.prominence([10.0, 10.0, 4.0, 10.0, 10.0])
        assert [r["kind"] for r in rows] == ["pocket"]
        assert rows[0]["prominence_m"] == pytest.approx(6.0)

    def test_a_flat_run_has_no_hump_and_no_cap_ride(self, tmp_path):
        sidecar = _profile_sidecar(tmp_path, n_pts=21)
        patch = _road_patch(tmp_path,
                            [(k * 5.0, 100.0) for k in range(21)])
        axes = CAC.load_axes(sidecar)
        rows = CAC.service_axis_profiles(
            axes, CAC._road_nodes(patch), halo_m=12.0, cap=0.08)
        assert len(rows) == 1
        r = rows[0]
        assert r["worst_grade"] == pytest.approx(0.0)
        assert r["over_cap_segments"] == 0
        assert r["cap_ride_runs"] == 0
        assert r["worst_peak_prominence_m"] == pytest.approx(0.0)

    def test_a_cap_ridden_hump_is_measured_as_one(self, tmp_path):
        """The named HECA shape: up at the cap, over, back down at the
        cap.  Prominence reads the hump; the audit reads the ride."""
        alts = []
        for k in range(41):
            d = k * 5.0
            z = 100.0 + 0.08 * min(d, 200.0 - d)
            alts.append((d, round(z, 3)))
        sidecar = _profile_sidecar(tmp_path, n_pts=41)
        patch = _road_patch(tmp_path, alts)
        rows = CAC.service_axis_profiles(
            CAC.load_axes(sidecar), CAC._road_nodes(patch),
            halo_m=12.0, cap=0.08)
        assert len(rows) == 1
        r = rows[0]
        assert r["worst_peak_prominence_m"] == pytest.approx(8.0, abs=0.2)
        assert r["cap_ride_runs"] >= 1
        assert r["over_cap_segments"] == 0

    def test_an_over_cap_pocket_is_counted(self, tmp_path):
        alts = [(k * 5.0, 100.0) for k in range(21)]
        alts[10] = (50.0, 94.0)          # a 6 m drop over 5 m = 120 %
        sidecar = _profile_sidecar(tmp_path, n_pts=21)
        patch = _road_patch(tmp_path, alts)
        r = CAC.service_axis_profiles(
            CAC.load_axes(sidecar), CAC._road_nodes(patch),
            halo_m=12.0, cap=0.08)[0]
        assert r["over_cap_segments"] == 2
        assert r["worst_pocket_prominence_m"] == pytest.approx(6.0)

    def test_non_service_axes_are_not_profiled(self, tmp_path):
        sidecar = _profile_sidecar(tmp_path, n_pts=21, service=False)
        patch = _road_patch(tmp_path,
                            [(k * 5.0, 100.0) for k in range(21)])
        assert CAC.service_axis_profiles(
            CAC.load_axes(sidecar), CAC._road_nodes(patch),
            halo_m=12.0, cap=0.08) == []

    def test_cli_writes_json_matching_the_library(self, tmp_path, capsys):
        sidecar = _profile_sidecar(tmp_path, n_pts=21)
        patch = _road_patch(tmp_path,
                            [(k * 5.0, 100.0 + 0.01 * k)
                             for k in range(21)])
        out = tmp_path / "prof.json"
        assert CAC.main([str(sidecar), "--profile", str(patch),
                         "--json", str(out)]) == 0
        got = json.loads(out.read_text())
        assert got["cap"] == pytest.approx(CAC._road_cap())
        assert got["axes"] == json.loads(json.dumps(
            CAC.service_axis_profiles(
                CAC.load_axes(sidecar), CAC._road_nodes(patch),
                halo_m=CAC.DEFAULT_HALO_M, cap=CAC._road_cap())))
        assert "VERTICAL PROFILE" in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════
# arm_site_read --profile / --line — WHAT SHAPE IS THE SURFACE HERE?
# (docs/specs/heca-apron-round2-spec.md acceptance; the round needed the
# emitted elevation itself, which no row count or weld table carries)
# ══════════════════════════════════════════════════════════════════════

def _surface_patch(tmp_path, name, alts, *, role="graded_strip",
                   step_m=10.0, lat_off_m=0.0):
    """One open way marching east from the site, one vertex every
    ``step_m``, carrying ``alts`` as per-node ``alt_abs`` — the dialect
    production emits."""
    lat = LAT0 + lat_off_m / M_PER_DEG
    txt = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    for k, a in enumerate(alts):
        txt.append(f"  <node id='-{100 + k}' lat='{lat:.9f}' "
                   f"lon='{_east(k * step_m):.9f}'>\n"
                   f"    <tag k='alt_abs' v='{a}'/>\n  </node>\n")
    txt.append("  <way id='-13257'>\n"
               + "".join(f"    <nd ref='-{100 + k}'/>\n"
                         for k in range(len(alts)))
               + f"    <tag k='role' v='{role}'/>\n"
               "    <tag k='aeroway' v='taxiway'/>\n  </way>\n")
    txt.append("</osm>\n")
    p = tmp_path / name
    p.write_text("".join(txt))
    (tmp_path / (name + ".axes.json")).write_text(
        json.dumps({"anchor": [LAT0, LON0], "ruleset": "icao"}))
    return p


class TestStationProfiles:
    """The RIPPLE reading: peak-to-peak inside a 50 m run along the ring."""

    def test_a_rippling_ring_reports_its_amplitude(self, tmp_path):
        cg = ASR._check_grade()
        alts = [100.0 + (0.55 if k % 2 else -0.55) for k in range(21)]
        p = _surface_patch(tmp_path, "ripple.osm", alts)
        got = ASR.station_profiles(cg, p, LAT0, LON0, 250.0)
        assert len(got) == 1
        assert got[0]["amp_m"] == pytest.approx(1.10, abs=0.01)
        assert got[0]["worst_step_m"] == pytest.approx(1.10, abs=0.01)
        assert got[0]["worst_step_pct"] == pytest.approx(11.0, abs=0.1)

    def test_a_faired_ring_reports_a_small_amplitude(self, tmp_path):
        """The same ring, faired to a straight ramp: the amplitude falls
        to what the ramp itself carries across the window."""
        cg = ASR._check_grade()
        alts = [100.0 + 0.01 * k for k in range(21)]
        p = _surface_patch(tmp_path, "faired.osm", alts)
        got = ASR.station_profiles(cg, p, LAT0, LON0, 250.0)
        assert got[0]["amp_m"] == pytest.approx(0.05, abs=0.005)
        assert got[0]["worst_step_pct"] == pytest.approx(0.1, abs=0.01)

    def test_the_role_scope_is_a_parameter(self, tmp_path):
        cg = ASR._check_grade()
        p = _surface_patch(tmp_path, "roled.osm", [100.0] * 11,
                           role="apron")
        assert ASR.station_profiles(cg, p, LAT0, LON0, 250.0,
                                    roles=("graded_strip",)) == []
        assert ASR.station_profiles(cg, p, LAT0, LON0, 250.0,
                                    roles=("apron",))

    def test_a_ring_that_does_not_reach_the_site_is_not_profiled(self,
                                                                 tmp_path):
        cg = ASR._check_grade()
        p = _surface_patch(tmp_path, "far.osm", [100.0] * 11,
                           lat_off_m=400.0)
        assert ASR.station_profiles(cg, p, LAT0, LON0, 25.0) == []

    def test_a_window_the_run_cannot_support_reads_None_not_zero(self,
                                                                tmp_path):
        """A reading a window cannot support is not a reading."""
        cg = ASR._check_grade()
        p = _surface_patch(tmp_path, "short.osm", [100.0, 100.9, 99.4],
                           step_m=2.0)
        got = ASR.station_profiles(cg, p, LAT0, LON0, 250.0)
        assert got[0]["amp_m"] is None
        assert got[0]["worst_step_m"] == pytest.approx(1.5, abs=0.01)


class TestLineProfile:
    """The CLIFF reading — and the NODELESS-VOID reading, which is the
    same instrument answering with an empty list."""

    def test_the_stations_along_the_line_carry_their_step(self, tmp_path):
        cg = ASR._check_grade()
        alts = [100.0] * 10 + [104.0] * 11        # a 4 m step at station 100
        p = _surface_patch(tmp_path, "cliff.osm", alts)
        got = ASR.line_profile(cg, p, (LAT0, LON0), (LAT0, _east(200.0)))
        assert got["n_stations"] == 21
        assert got["worst_step_m"] == pytest.approx(4.0, abs=0.01)
        assert got["worst_step_at_m"] == pytest.approx(90.0, abs=0.5)

    def test_an_empty_station_list_IS_the_finding(self, tmp_path):
        """A NODELESS void: the line crosses real pavement and no emitted
        vertex lies along it.  The tool reports zero stations rather than
        a clean profile — the census's blind spot, made visible."""
        cg = ASR._check_grade()
        p = _surface_patch(tmp_path, "void.osm", [100.0] * 5,
                           lat_off_m=300.0)
        got = ASR.line_profile(cg, p, (LAT0, LON0), (LAT0, _east(200.0)))
        assert got["n_stations"] == 0
        assert got["worst_step_m"] is None
        assert got["alt_min"] is None            # never 0.0

    def test_the_corridor_width_is_a_parameter(self, tmp_path):
        cg = ASR._check_grade()
        p = _surface_patch(tmp_path, "corr.osm", [100.0] * 11,
                           lat_off_m=20.0)
        assert ASR.line_profile(cg, p, (LAT0, LON0), (LAT0, _east(100.0)),
                                corridor_m=15.0)["n_stations"] == 0
        assert ASR.line_profile(cg, p, (LAT0, LON0), (LAT0, _east(100.0)),
                                corridor_m=30.0)["n_stations"] > 0

    def test_two_distinct_coordinates_are_required(self, tmp_path):
        cg = ASR._check_grade()
        p = _surface_patch(tmp_path, "same.osm", [100.0] * 5)
        with pytest.raises(ASR.SiteReadRefusal):
            ASR.line_profile(cg, p, (LAT0, LON0), (LAT0, LON0))

    def test_the_cli_json_is_the_library_result(self, tmp_path, capsys):
        p = _surface_patch(tmp_path, "cli_prof.osm",
                           [100.0 + (0.5 if k % 2 else -0.5)
                            for k in range(21)])
        out = tmp_path / "prof.json"
        assert ASR.main([
            str(p), str(p), "--site", f"S={LAT0},{LON0}",
            "--radius", "250", "--profile",
            "--line", f"L={LAT0},{LON0}:{LAT0},{_east(200.0)}",
            "--json", str(out)]) == 0
        got = json.loads(out.read_text())
        cg = ASR._check_grade()
        assert got["profiles"]["S"]["arm"] == ASR.station_profiles(
            cg, p, LAT0, LON0, 250.0)
        assert got["lines"]["L"]["arm"] == ASR.line_profile(
            cg, p, (LAT0, LON0), (LAT0, _east(200.0)))
        printed = capsys.readouterr().out
        assert "STATION PROFILES" in printed
        assert "OWNER LINES" in printed

    def test_profile_without_a_site_is_reported_as_skipped(self, tmp_path,
                                                           capsys):
        p = _surface_patch(tmp_path, "nosite_prof.osm", [100.0] * 5)
        assert ASR.main([str(p), str(p), "--profile"]) == 0
        assert "SKIPPED profiles" in capsys.readouterr().out
