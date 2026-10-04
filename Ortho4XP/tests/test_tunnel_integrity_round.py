"""THE TUNNEL INTEGRITY ROUND — §T1, §T2, §T3, §T8.

Spec: ``docs/specs/tunnel-integrity-round-spec.md`` (Fable, 2026-08-28),
implementing ``docs/RULINGS.md`` 2026-08-28 items 4-8 and 2026-08-28c.

The measured frame these twins pin (lane/lemdtun, LEMD + OTHH):

* 37 LEMD tunnel ways killed by the adjacent-road SYSTEM veto, recorded
  nowhere — a refusal recorded and thrown away is the class this
  campaign exists to kill (§T3).
* 8 of 8 LEMD DEM-cut clusters emit NO ramp, on a DEM whose source class
  cannot carry an approach profile at all (§T2.1).
* All 8 LEMD ``tunnel_cap`` rings are 0.5-11 m² slivers — R10-2 cut the
  cap back against the mouth the cap reached into (§T2.2).
* Four 0.3-4.3 m² ``authority_retreat_wall`` stubs at the item-4 site:
  the adjacent-ground machinery improvising at an OBJECT-BRIDGE trench
  edge (§T1.3).
* ``covered_span_clean`` tests ``e < 0.0`` on a field that runs
  561-617 m — structurally vacuous, and it reported PASS (§T8.1).

Each law is twinned in BOTH gate states; the preserved prior rulings
(EGGW lidar earns the no-ramp mode; an off-airport LMML-class crossing
still vetoes) are twinned as such.
"""
from __future__ import annotations

import os

import pytest
from shapely.geometry import LineString, Polygon


T1_FLAG = "O4_OBJ_TUNNEL_COMPOSE"
T2_FLAG = "O4_DEMCUT_PROVENANCE_GATE"
T3_FLAG = "O4_TUNNEL_VETO_SCOPED"


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


@pytest.fixture
def gates_on(monkeypatch):
    for flag in (T1_FLAG, T2_FLAG, T3_FLAG):
        monkeypatch.setenv(flag, "1")


# ═════════════════════════════════════════════════════════════════════
# §T1.2 — A BRIDGE TRENCH IS STILL A TRENCH
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §T1.1 — THE DECK-CLEARANCE CORRIDOR YIELDS TO A MAPPED BORE
# (Fable ruling 2026-08-28, option (c))
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §T3 — THE ADJACENT-ROAD VETO IS SCOPED
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §T8 — INSTRUMENT REPAIRS
# ═════════════════════════════════════════════════════════════════════
def _load_acceptance():
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "tpa_under_test", root / "tools" / "tunnel_portal_acceptance.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tpa_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


class _FakePatch:
    """The three members ``_check_covered_span`` reads."""

    def __init__(self, ways, nodes):
        self.ways = ways
        self.nodes = nodes
        self.ll_to_m = lambda lat, lon: (lon, lat)


class _FakeWay:
    def __init__(self, nids, elevs):
        self.nids, self.elevs = nids, elevs


class _FakeRoadNetwork:
    """Module-level (so it pickles) stand-in for
    ``auto_patch.osm_load.AirportRoadNetwork``."""
    nodes = {"a": (40.0, -3.0), "b": (40.001, -3.0)}
    ways = [("-2070", ["a", "b"], {"tunnel": "yes"}),
            ("-9", ["a", "b"], {})]


class TestCoveredSpanHasALocalDatum:
    """§T8.1: LEMD's 561-617 m field makes ``e < 0.0`` structurally
    vacuous — the check reported PASS over a span it had not examined."""

    def _world(self, trench_elev):
        tpa = _load_acceptance()
        bores = {"-2070": LineString([(0.0, 0.0), (0.0, 100.0)])}
        nodes, ways = {}, []
        # A ring of surrounding grade at 600 m, 30 m off the axis.
        nids, elevs = [], []
        for i in range(12):
            nid = f"g{i}"
            nodes[nid] = (i * 8.0, 30.0)          # (lat, lon) -> (x=30)
            nids.append(nid)
            elevs.append(600.0)
        ways.append(_FakeWay(nids, elevs))
        # A trench vertex ON the axis.
        nodes["t0"] = (50.0, 0.0)
        ways.append(_FakeWay(["t0"], [trench_elev]))
        profile = tpa.Profile(
            name="X", bore_way_ids=("-2070",),
            covered_span_m=(0.0, 100.0),
            covered_half_widths_m=(10.0,))
        return tpa, _FakePatch(ways, nodes), profile, bores

    def test_a_trench_far_below_the_local_grade_fails(self):
        tpa, patch, profile, bores = self._world(590.0)
        (check,) = tpa._check_covered_span(patch, profile, bores,
                                           tpa.Thresholds())
        assert check.verdict == tpa.FAIL
        assert check.measured == 1
        assert "600.00" in check.detail

    def test_the_old_absolute_zero_predicate_would_have_passed_it(self):
        """The bug, stated: 590 m is not below 0.0 m."""
        assert not (590.0 < 0.0)

    def test_a_clean_covered_span_passes(self):
        tpa, patch, profile, bores = self._world(600.0)
        (check,) = tpa._check_covered_span(patch, profile, bores,
                                           tpa.Thresholds())
        assert check.verdict == tpa.PASS

    def test_no_annulus_evidence_skips_never_passes(self):
        tpa = _load_acceptance()
        bores = {"-2070": LineString([(0.0, 0.0), (0.0, 100.0)])}
        profile = tpa.Profile(name="X", bore_way_ids=("-2070",),
                              covered_span_m=(0.0, 100.0),
                              covered_half_widths_m=(10.0,))
        patch = _FakePatch([], {})
        (check,) = tpa._check_covered_span(patch, profile, bores,
                                           tpa.Thresholds())
        assert check.verdict == tpa.SKIP

    def test_an_undeclared_span_skips_never_passes(self):
        tpa = _load_acceptance()
        bores = {"-2070": LineString([(0.0, 0.0), (0.0, 100.0)])}
        profile = tpa.Profile(name="X", bore_way_ids=("-2070",))
        (check,) = tpa._check_covered_span(_FakePatch([], {}), profile,
                                           bores, tpa.Thresholds())
        assert check.verdict == tpa.SKIP
        assert "no covered span declared" in check.detail


class TestSiteModeGainsTheBoreInputs:
    """§T8.2: an ad-hoc ``--site`` run can execute the covered-span and
    claim checks instead of SKIPPING them."""

    def test_the_flags_reach_the_profile(self):
        """``--bore-ways=...``, with the equals sign, because way ids are
        NEGATIVE: argparse reads a bare ``-2070,-2119`` as an option
        string (its negative-number matcher accepts ``-2070`` but not
        ``-2070,-2119``) and exits 2.  That is true of every Python this
        runs on, so the twin was asserting a spelling the CLI has never
        accepted; the attached form is the one a caller must use, and
        stating it here is the only place it is written down."""
        tpa = _load_acceptance()
        args = tpa.build_parser().parse_args([
            "P.osm", "--site", "A=1,2",
            "--bore-osm", "_airport_road_feed/LEMD_road_feed.cache",
            "--bore-ways=-2070,-2119",
            "--covered-span", "70,740"])
        assert args.bore_osm.endswith("LEMD_road_feed.cache")
        assert args.bore_ways == "-2070,-2119"
        assert args.covered_span == "70,740"

    def test_the_lemd_profile_ships(self):
        tpa = _load_acceptance()
        p = tpa.SITE_PROFILES["LEMD"]
        assert list(p.sites)[0].startswith("item 4"), (
            "the FIRST site is the mouth the --mouth-max-m check reads")
        assert len(p.sites) == 4
        assert set(p.bore_way_ids) == {"-2070", "-1872", "-257",
                                       "-2085", "-2119"}
        assert p.bore_osm_relpath.endswith("LEMD_road_feed.cache")

    def test_a_road_feed_cache_is_a_bore_source(self, tmp_path):
        """The road feed is where LEMD's bores actually live — there is
        no ``big_roads`` tunnel extract for that tile."""
        import pickle
        cache = tmp_path / "X_road_feed.cache"
        cache.write_bytes(pickle.dumps({"network": _FakeRoadNetwork()}))
        tpa = _load_acceptance()
        profile = tpa.Profile(name="X", bore_osm_relpath=str(cache),
                              bore_way_ids=("-2070",))
        lines = tpa._bore_lines(profile, None, lambda la, lo: (lo, la))
        assert set(lines) == {"-2070"}


