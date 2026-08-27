"""Twin for ``tools/airside_pair_table.py`` (promoted 2026-08-27 on its
SECOND use, RULINGS ``7e90032``).

Pins what the tool promises: it reads through the harness library's own
parser, it derives no law and counts no defects, its role sets are
IMPORTED rather than re-spelled, a chord across a pavement GAP is
excluded by default (spec ``airside-no-step-law-spec.md`` Amendment 1
ruling 2) and included under ``--allow-gap-chords``, the CLI's JSON IS
the library result, and the index row exists.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import airside_pair_table as APT                           # noqa: E402

ANCHOR = (1.5, 1.5)
R = 6378137.0
_COS0 = math.cos(math.radians(ANCHOR[0]))


def _ll(x, y):
    return (ANCHOR[0] + math.degrees(y / R),
            ANCHOR[1] + math.degrees(x / (R * _COS0)))


class _Builder:
    def __init__(self):
        self.nodes = []
        self.ways = []
        self._n = 0

    def _id(self):
        self._n -= 1
        return str(self._n)

    def rect(self, x0, y0, x1, y1, alt, role):
        ids = []
        for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            nid = self._id()
            lat, lon = _ll(x, y)
            self.nodes.append((nid, lat, lon, alt))
            ids.append(nid)
        self.ways.append((self._id(), ids + [ids[0]],
                          {"role": role, "aeroway": "aerodrome"}))

    def write(self, path):
        out = ["<?xml version='1.0' encoding='UTF-8'?>",
               "<osm version='0.6' generator='pair-table-twin'>"]
        for nid, lat, lon, alt in self.nodes:
            out.append(f"  <node id='{nid}' lat='{lat:.11f}' "
                       f"lon='{lon:.11f}'><tag k='alt_abs' "
                       f"v='{alt:.2f}' /></node>")
        for wid, nids, tags in self.ways:
            out.append(f"  <way id='{wid}'>")
            out += [f"    <nd ref='{n}' />" for n in nids]
            out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
            out.append("  </way>")
        out.append("</osm>")
        path.write_text("\n".join(out) + "\n")
        Path(str(path) + ".axes.json").write_text(
            json.dumps({"anchor": list(ANCHOR), "ruleset": "icao"}))
        return path


@pytest.fixture()
def abutting(tmp_path):
    """A junction at 10.0 abutting an apron at 8.0 — one surface, a 2 m
    step across their shared edge."""
    b = _Builder()
    b.rect(-20.0, -10.0, 0.0, 10.0, 10.0, "junction")
    b.rect(0.0, -10.0, 20.0, 10.0, 8.0, "apron")
    return b.write(tmp_path / "abut.patch.osm")


@pytest.fixture()
def separated(tmp_path):
    """The same two surfaces with a 40 m unpaved GAP between them."""
    b = _Builder()
    b.rect(-60.0, -20.0, -20.0, 20.0, 10.0, "junction")
    b.rect(20.0, -20.0, 60.0, 20.0, 8.0, "apron")
    return b.write(tmp_path / "gap.patch.osm")


def test_the_role_sets_are_imported_never_respelled():
    from auto_patch.airside_no_step import taxiway_family_roles
    from auto_patch.layout import (ROLE_APRON, ROLE_RUNWAY,
                                   ROLE_RUNWAY_CROSSING)
    anc = APT.anchor_roles()
    assert set(taxiway_family_roles()) <= anc
    assert {ROLE_RUNWAY, ROLE_RUNWAY_CROSSING} <= anc
    assert APT.membrane_roles() == frozenset({ROLE_APRON})
    assert ROLE_APRON not in anc
    # the emitted feature classes agree with the census's own register
    import check_grade as cg
    assert set(APT.ANCHOR_FEATURES) | set(APT.MEMBRANE_FEATURES) == set(
        cg._NO_STEP_POLYLINE_FEATURES)


def test_it_prices_no_law_and_counts_no_defects():
    src = Path(APT.__file__).read_text()
    assert "_parse_osm" in src                 # the harness library's parser
    assert "run_checks" not in src             # never a private census
    assert "Violation" not in src
    from auto_patch.grade_law import TAXI_MAX_GRADE
    res = APT.read.__doc__
    assert res
    assert "TAXI_MAX_GRADE" in src and float(TAXI_MAX_GRADE) > 0


def test_an_abutting_pair_is_reported_with_its_direct_distance(abutting):
    res = APT.read(abutting, [("s", *_ll(0.0, 0.0))], radius=100.0,
                   dists=(30.0, 75.0))
    assert res["contiguous_pavement_only"] is True
    site = res["sites"][0]
    assert site["anchored_in_reach"] == 4
    row30 = site["rows"][0]
    assert row30["pairs"] > 0
    assert row30["worst"]["de_m"] == pytest.approx(2.0, abs=1e-6)
    assert row30["over_cap"] > 0, "2 m over <=30 m is over 1.5 %"


def test_a_chord_across_a_pavement_GAP_is_excluded_by_default(separated):
    """Spec Amendment 1 ruling 2 / RULINGS 2026-08-24b: a step is lawful
    exactly across a pavement gap."""
    res = APT.read(separated, [("s", *_ll(0.0, 0.0))], radius=100.0,
                   dists=(75.0,))
    row = res["sites"][0]["rows"][0]
    assert row["pairs"] == 0
    assert row["gap_chords_skipped"] > 0
    assert row["worst"] is None
    loose = APT.read(separated, [("s", *_ll(0.0, 0.0))], radius=100.0,
                     dists=(75.0,), allow_gap_chords=True)
    lrow = loose["sites"][0]["rows"][0]
    assert loose["contiguous_pavement_only"] is False
    assert lrow["pairs"] > 0
    assert lrow["worst"]["de_m"] == pytest.approx(2.0, abs=1e-6)


def test_the_distance_buckets_are_cumulative_and_ordered(abutting):
    res = APT.read(abutting, [("s", *_ll(0.0, 0.0))], radius=100.0,
                   dists=(10.0, 30.0, 75.0))
    pairs = [r["pairs"] for r in res["sites"][0]["rows"]]
    assert pairs == sorted(pairs), "a wider bucket cannot hold fewer pairs"


def test_the_CLI_json_IS_the_library_result(abutting, tmp_path):
    out = tmp_path / "t.json"
    lat, lon = _ll(0.0, 0.0)
    rc = APT.main([str(abutting), f"--site=s={lat},{lon}",
                   "--radius", "100", "--dists", "30,75",
                   "--json", str(out)])
    assert rc == 0
    got = json.loads(out.read_text())
    assert got == [APT.read(abutting, [("s", lat, lon)], radius=100.0,
                            dists=(30.0, 75.0))]


def test_the_CLI_refuses_a_malformed_site(abutting):
    with pytest.raises(SystemExit):
        APT.main([str(abutting), "--site=nocoords"])
    with pytest.raises(SystemExit):
        APT.main([str(abutting), "--site=s=1.0,1.0", "--dists", ""])


def test_the_index_row_exists():
    """RULINGS 7e90032: a tool lands with its index entry in the SAME
    commit, or it is treated as absent."""
    idx = (_ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "Ortho4XP/tools/airside_pair_table.py" in idx
