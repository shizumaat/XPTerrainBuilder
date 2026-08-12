"""``tools/runway_end_ground.py`` — the ground off a runway end.

The acceptance population rounds 17 / 17b / 17c all quote: graded
SURFACE vertices within N metres of a runway end that sit at or below a
level they have no business being at.  VHHH's was 1,681 (the runway-end
canyons); the round's target is ~0.

It is not a law and not a census family — it reports EMITTED ALTITUDES
near named points — but it IS quoted as an acceptance number, so it is
twinned: the radius, the level, the ROLE SCOPE (below-grade families
deliberately absent) and the total are each asserted on a synthetic
patch whose answer is known by construction.

Headless: a ``tmp_path`` patch, no build, no network.
"""

from __future__ import annotations

import os
import sys

import pytest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import runway_end_ground as REG  # noqa: E402

#: One end, at the origin of the fixture.
END = ("07L", 22.30000, 113.90000)

#: 500 m of latitude, in degrees — the radius the acceptance uses.
DEG_500_M = 500.0 / (6378137.0 * 3.14159265358979 / 180.0)


def _patch(tmp_path, rings):
    """``rings`` = [(role, [(lat, lon, alt), ...]), ...]."""
    out = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    nid = 0
    ways = []
    for (role, points) in rings:
        nids = []
        for (lat, lon, alt) in points:
            nid += 1
            out.append("  <node id='-{0}' action='modify' visible='true' "
                       "lat='{1:.8f}' lon='{2:.8f}'>\n"
                       "    <tag k='alt_abs' v='{3:.3f}' />\n"
                       "  </node>".format(nid, lat, lon, alt))
            nids.append(-nid)
        ways.append((role, nids))
    wid = 10000
    for (role, nids) in ways:
        wid += 1
        body = "".join("    <nd ref='{0}' />\n".format(n)
                       for n in nids + [nids[0]])
        out.append("  <way id='-{0}' action='modify' visible='true'>\n{1}"
                   "    <tag k='role' v='{2}' />\n"
                   "  </way>".format(wid, body, role))
    out.append("</osm>")
    path = tmp_path / "patch.osm"
    path.write_text("\n".join(out))
    return path


def _ring(lat, lon, alt, role, span=1e-5):
    return (role, [(lat, lon, alt), (lat + span, lon, alt),
                   (lat + span, lon + span, alt), (lat, lon + span, alt)])


#: A ring's four corners plus the repeated closing vertex — the count the
#: harness parser yields, and therefore the count this tool reports.
RING_N = 5


class TestTheCount:
    def test_it_counts_the_sub_level_vertices_near_the_end(self, tmp_path):
        patch = _patch(tmp_path, [
            _ring(END[1], END[2], -12.5, "graded_strip"),      # 4, under
            _ring(END[1] + 0.0005, END[2], 7.3, "junction"),   # 4, over
        ])
        out = REG.measure(patch, [END])
        assert out["total_at_or_below"] == RING_N
        assert out["ends"][0]["n"] == 2 * RING_N
        assert out["ends"][0]["min_m"] == pytest.approx(-12.5)
        assert out["ends"][0]["min_role"] == "graded_strip"

    def test_the_RADIUS_is_a_boundary_not_a_hint(self, tmp_path):
        far = END[1] + 2.0 * DEG_500_M
        patch = _patch(tmp_path, [_ring(far, END[2], -12.5, "graded_strip")])
        assert REG.measure(patch, [END])["total_at_or_below"] == 0
        assert REG.measure(patch, [END],
                           radius_m=3.0 * 500.0)["total_at_or_below"] == RING_N

    def test_the_LEVEL_is_a_parameter_and_the_default_is_zero(self,
                                                              tmp_path):
        patch = _patch(tmp_path, [_ring(END[1], END[2], -0.5,
                                        "graded_strip")])
        assert REG.measure(patch, [END])["total_at_or_below"] == RING_N
        assert REG.measure(patch, [END],
                           level_m=-1.0)["total_at_or_below"] == 0

    def test_ends_are_counted_SEPARATELY_and_summed(self, tmp_path):
        second = ("25R", END[1] + 10.0 * DEG_500_M, END[2])
        patch = _patch(tmp_path, [
            _ring(END[1], END[2], -12.5, "graded_strip"),
            _ring(second[1], second[2], -9.0, "apron"),
        ])
        out = REG.measure(patch, [END, second])
        assert [r["at_or_below"] for r in out["ends"]] == [RING_N, RING_N]
        assert out["total_at_or_below"] == 2 * RING_N


class TestTheROLESCOPE:
    def test_a_BELOW_GRADE_role_is_not_in_the_population(self, tmp_path):
        """``tunnel_trench``'s below-grade vertices are LAWFUL; counting
        them would drown the signal the number exists to carry."""
        patch = _patch(tmp_path, [_ring(END[1], END[2], -12.5,
                                        "tunnel_trench")])
        out = REG.measure(patch, [END])
        assert out["ends"][0]["n"] == 0
        assert out["total_at_or_below"] == 0

    def test_all_four_surface_roles_are_in_it(self, tmp_path):
        rings = [_ring(END[1] + i * 1e-4, END[2], -12.5, role)
                 for i, role in enumerate(REG.DEFAULT_ROLES)]
        out = REG.measure(patch=_patch(tmp_path, rings), ends=[END])
        assert out["total_at_or_below"] == RING_N * len(REG.DEFAULT_ROLES)

    def test_the_scope_is_overridable_and_reported(self, tmp_path):
        patch = _patch(tmp_path, [_ring(END[1], END[2], -12.5,
                                        "tunnel_trench")])
        out = REG.measure(patch, [END], roles=("tunnel_trench",))
        assert out["roles"] == ["tunnel_trench"]
        assert out["total_at_or_below"] == RING_N


class TestTheCLI:
    def test_it_REFUSES_rather_than_baking_in_an_end_table(self, tmp_path):
        """An end table inside an instrument is a second source of truth
        about where the runway is."""
        patch = _patch(tmp_path, [_ring(END[1], END[2], 7.3, "apron")])
        with pytest.raises(SystemExit):
            REG.main([str(patch)])

    def test_it_prints_and_writes_the_total(self, tmp_path, capsys):
        patch = _patch(tmp_path, [_ring(END[1], END[2], -12.5,
                                        "graded_strip")])
        out_json = tmp_path / "out.json"
        assert REG.main([str(patch), "--end", END[0], str(END[1]),
                         str(END[2]), "--json", str(out_json)]) == 0
        printed = capsys.readouterr().out
        assert "TOTAL <=+0.00 m within 500 m of an end" in printed
        import json
        assert json.loads(out_json.read_text())["total_at_or_below"] == RING_N


class TestItIsTheHARNESSPARSER:
    def test_the_patch_is_read_with_check_grades_own_reader(self):
        """One geometry for this tool and the census — a private reader
        is the census-wrapper defect."""
        import inspect
        source = inspect.getsource(REG.measure)
        assert "from check_grade import _parse_osm" in source
