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

import json
import os

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch import adjacent_ground, bridges
from auto_patch.layout import (BuiltShape, PavementLayout, ROLE_APRON,
                               ROLE_BRIDGE_TRENCH, ROLE_RETAINING_WALL,
                               ROLE_RUNWAY, ROLE_SERVICE_ROAD,
                               ROLE_TUNNEL_RAMP, ROLE_TUNNEL_TRENCH)

T1_FLAG = "O4_OBJ_TUNNEL_COMPOSE"
T2_FLAG = "O4_DEMCUT_PROVENANCE_GATE"
T3_FLAG = "O4_TUNNEL_VETO_SCOPED"


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes=()):
    lay = PavementLayout(icao="KFAKE", anchor=(40.5, -3.58))
    lay.shapes.extend(shapes)
    return lay


@pytest.fixture
def gates_on(monkeypatch):
    for flag in (T1_FLAG, T2_FLAG, T3_FLAG):
        monkeypatch.setenv(flag, "1")


# ═════════════════════════════════════════════════════════════════════
# §T1.2 — A BRIDGE TRENCH IS STILL A TRENCH
# ═════════════════════════════════════════════════════════════════════
class _FakeBridge:
    """The two attributes ``_bridge_footprint_meters`` reads: a deck
    polygon in the STRUCTURE METRE FRAME and that frame's origin."""

    def __init__(self, half_m, origin_lon_lat=(-3.58, 40.5)):
        self.deck_polygon = _rect(-half_m, -half_m, half_m, half_m)
        self.frame_origin_longitude_latitude = origin_lon_lat


class _FakeClassification:
    def __init__(self, tunnels=(), bridges_=()):
        self.tunnels = list(tunnels)
        self.bridges = list(bridges_)


class TestObjectTrenchUnionComposesBridgeTrenches:
    """§T1.2: ``_object_trench_body_union`` widens to ``ROLE_BRIDGE_
    TRENCH`` bodies — R8-3's yield had nothing to yield to at LEMD's
    -2070 portal because the union was tunnel-only."""

    def _prepared(self, monkeypatch):
        # A bridge whose deck sits at the origin, and the object-born
        # corridor plate under it.  ``_bridge_footprint_meters``
        # projects the deck polygon through the FRAME ORIGIN, so a tiny
        # degree-space ring lands as a metres-scale body at the anchor.
        bridge = _FakeBridge(30.0)
        plate = BuiltShape(polygon=_rect(-20, -20, 20, 20),
                           role=ROLE_BRIDGE_TRENCH,
                           ref="object_bridge_corridor",
                           altitude=606.96)
        lay = _layout([plate])
        monkeypatch.setattr(
            bridges, "_object_bridge_classification",
            lambda _l: _FakeClassification(bridges_=[bridge]))
        return lay

    def test_on_the_bridge_trench_body_joins_the_union(self, monkeypatch):
        monkeypatch.setenv(T1_FLAG, "1")
        lay = self._prepared(monkeypatch)
        union = bridges._object_trench_body_union(lay)
        assert union is not None, (
            "the object-BRIDGE corridor is a trench to every consumer "
            "that asks 'is this ground object-owned' (spec §T1.2)")
        assert union.area > 0.0

    def test_off_is_the_pre_round_tunnel_only_union(self, monkeypatch):
        monkeypatch.setenv(T1_FLAG, "0")
        lay = self._prepared(monkeypatch)
        assert bridges._object_trench_body_union(lay) is None

    def test_a_body_with_no_emitted_floor_pan_is_still_excluded(
            self, monkeypatch):
        """The predicate stays AN EMITTED FLOOR PAN, not a
        classification — ``tunnel4_done`` (a body with no trench must
        not lose its OSM ramps) is unchanged."""
        monkeypatch.setenv(T1_FLAG, "1")
        bridge = _FakeBridge(30.0)
        lay = _layout([])                  # no plate emitted
        monkeypatch.setattr(
            bridges, "_object_bridge_classification",
            lambda _l: _FakeClassification(bridges_=[bridge]))
        assert bridges._object_trench_body_union(lay) is None


# ═════════════════════════════════════════════════════════════════════
# §T1.3 — NO IMPROVISED RETREAT WALL AT AN OBJECT TRENCH EDGE
# ═════════════════════════════════════════════════════════════════════
class TestObjectTrenchWallKeepout:
    """§T1.3 extends RULINGS 2026-08-07 §1 ("the tunnel machinery walls
    its own cut") to object trench / bridge-trench edges."""

    def _layout(self):
        return _layout([
            BuiltShape(polygon=_rect(0, 0, 40, 40),
                       role=ROLE_BRIDGE_TRENCH,
                       ref="object_bridge_corridor", altitude=606.96),
            BuiltShape(polygon=_rect(100, 100, 140, 140),
                       role=ROLE_TUNNEL_TRENCH,
                       ref="object_tunnel_trench", altitude=600.0),
        ])

    def test_on_the_plate_edges_are_a_keepout(self, monkeypatch):
        monkeypatch.setenv(T1_FLAG, "1")
        zone = adjacent_ground._object_trench_wall_keepout(self._layout())
        assert zone is not None
        from shapely.geometry import Point
        # ON the corridor rim, where the four LEMD stubs stood.
        assert zone.contains(Point(0.0, 20.0))
        # And well away from it, where the pass is untouched.
        assert not zone.contains(Point(70.0, 20.0))

    def test_off_is_the_pre_round_scope(self, monkeypatch):
        monkeypatch.setenv(T1_FLAG, "0")
        assert adjacent_ground._object_trench_wall_keepout(
            self._layout()) is None

    def test_an_osm_trench_sharing_the_role_is_untouched(self,
                                                        monkeypatch):
        """Named by REF, not by role: the keepout is about plates the
        OBJECT machinery bore, not about every shape with that role."""
        monkeypatch.setenv(T1_FLAG, "1")
        lay = _layout([BuiltShape(polygon=_rect(0, 0, 40, 40),
                                  role=ROLE_TUNNEL_TRENCH,
                                  ref="tunnel_trench", altitude=1.0)])
        assert adjacent_ground._object_trench_wall_keepout(lay) is None


# ═════════════════════════════════════════════════════════════════════
# §T2.1 — DEM-CUT MODE GATES ON DEM PROVENANCE
# ═════════════════════════════════════════════════════════════════════
class TestDemCutProvenanceGate:
    """§T2.1: the light-touch mode needs BOTH measured relief and a DEM
    source class that can carry an approach profile."""

    @pytest.mark.parametrize("klass,ok", [
        ("lidar", True),        # EGGW 2026-07-17, PRESERVED
        ("sub10m", False),      # spec §T2.1: NEVER qualifies
        ("1arcsec", False),
        ("ge3arcsec", False),
        (None, False),          # a class we cannot name cannot qualify
    ])
    def test_the_register_is_the_sidecar_site_class(self, klass, ok):
        lay = _layout()
        lay.site_class = {"s2_source_class": klass}
        assert bridges._dem_cut_provenance(lay, None) == (ok, klass)

    def test_sub_ten_metre_is_not_lidar_class(self):
        assert "sub10m" not in bridges._DEM_CUT_LIDAR_CLASSES
        assert "lidar" in bridges._DEM_CUT_LIDAR_CLASSES

    def test_no_register_at_all_does_not_qualify(self):
        """No site_class, no DEM, no inset provenance: the mode stands
        down and the full synthetic ramp+mouth is emitted.  A refusal to
        guess is not a reason to skip the ramps."""
        ok, klass = bridges._dem_cut_provenance(_layout(), None)
        assert ok is False and klass is None


# ═════════════════════════════════════════════════════════════════════
# §T2.2 — THE MOUTH BEATS THE CAP
# ═════════════════════════════════════════════════════════════════════
class TestCapFragmentMustStillSpan:
    """§T2.2: a post-cut cap fragment that no longer SPANS the portal
    face is dropped with its §1-style named line.  The 0.5 m² area floor
    admitted all eight LEMD slivers."""

    def _cap(self):
        # A cap BAR: 22 m across the face, 0.6 m of reach.
        return BuiltShape(polygon=_rect(0.0, 0.0, 22.0, 0.6),
                          role=ROLE_RETAINING_WALL, ref="tunnel_cap",
                          altitude=600.0)

    def _cutter(self):
        # Pavement that eats the middle, leaving two 3 m stubs.
        return _rect(3.0, -1.0, 19.0, 2.0)

    def test_span_is_the_long_side_of_the_min_rotated_rect(self):
        assert bridges._piece_span_m(_rect(0, 0, 22, 0.6)) == pytest.approx(
            22.0, abs=1e-6)

    def test_on_the_non_spanning_stubs_are_dropped_and_named(
            self, monkeypatch, capsys):
        monkeypatch.setenv(T2_FLAG, "1")
        import O4_UI_Utils as UI
        monkeypatch.setattr(UI, "verbosity", 1, raising=False)
        lay = _layout()
        pieces = bridges._tunnel_cover_pieces(
            self._cap(), self._cutter(), min_span_m=22.0, layout=lay,
            cluster=(0.0, 0.0))
        assert pieces == [], (
            "a 3 m stub does not span a 22 m portal face (spec §T2.2)")
        out = capsys.readouterr().out
        assert out.count("[tunnel-remove]") == 2, out
        assert "no longer spans the portal face" in out

    def test_off_ships_the_slivers_exactly_as_before(self, monkeypatch):
        monkeypatch.setenv(T2_FLAG, "0")
        pieces = bridges._tunnel_cover_pieces(
            self._cap(), self._cutter(), min_span_m=22.0,
            layout=_layout(), cluster=(0.0, 0.0))
        assert len(pieces) == 2

    def test_an_intact_cap_survives_the_new_gate(self, monkeypatch):
        monkeypatch.setenv(T2_FLAG, "1")
        pieces = bridges._tunnel_cover_pieces(
            self._cap(), _rect(100, 100, 110, 110), min_span_m=22.0,
            layout=_layout())
        assert len(pieces) == 1
        assert pieces[0].polygon.area == pytest.approx(22.0 * 0.6)

    def test_the_area_floor_alone_would_have_kept_them(self):
        """The measured defect, restated as an assertion: every stub is
        comfortably over ``_TUNNEL_COVER_MIN_PIECE_M2``, which is why
        eight sliver caps shipped."""
        stub = _rect(0.0, 0.0, 3.0, 0.6)
        assert stub.area > bridges._TUNNEL_COVER_MIN_PIECE_M2


# ═════════════════════════════════════════════════════════════════════
# §T2.3 — LIGHT-TOUCH MOUTHS LOSE THE UNWALLED-FINDING EXEMPTION
# ═════════════════════════════════════════════════════════════════════
class TestLightTouchMouthsAreReported:

    def _layout_with_bare_mouth(self):
        mouth = BuiltShape(polygon=_rect(0, 0, 20, 6),
                           role=ROLE_TUNNEL_RAMP, ref="tunnel_mouth",
                           altitude=600.0)
        lay = _layout([mouth])
        lay._tunnel_light_touch_mouths = {id(mouth)}
        return lay

    def test_on_a_light_touch_mouth_is_reported_like_any_mouth(
            self, monkeypatch):
        monkeypatch.setenv(T2_FLAG, "1")
        lay = self._layout_with_bare_mouth()
        bridges._record_tunnel_mouth_walling(lay, set(), None)
        assert getattr(lay, "tunnel_unwalled_mouth", None), (
            "§T2.3 withdraws A7(c)'s exemption — the finding reports "
            "them like any mouth")

    def test_off_keeps_the_a7c_exemption(self, monkeypatch):
        monkeypatch.setenv(T2_FLAG, "0")
        lay = self._layout_with_bare_mouth()
        bridges._record_tunnel_mouth_walling(lay, set(), None)
        assert not getattr(lay, "tunnel_unwalled_mouth", None)


# ═════════════════════════════════════════════════════════════════════
# §T3 — THE ADJACENT-ROAD VETO IS SCOPED
# ═════════════════════════════════════════════════════════════════════
def _veto_world(*, cross: bool):
    """One tunnel candidate plus one foreign road, crossing it or merely
    running beside it.  Returns the arguments
    ``_compute_tunnel_system_veto`` takes."""
    # The candidate on y=0 and a SYSTEM SIBLING on y=20: 20 m apart, so
    # ``_compute_tunnel_system_veto`` unions them (the link bar is
    # ``adjacent_road_dist_m * 1.5`` = 22.5 m).  Every foreign road below
    # is placed so it reaches ONLY the candidate — the sibling's verdict
    # is therefore purely a question of PROPAGATION.
    nodes_m = {
        "t0": (0.0, 0.0), "t1": (100.0, 0.0),
        "t2": (0.0, 20.0), "t3": (100.0, 20.0),
    }
    ways_r = [
        ("-2070", ["t0", "t1"], {"tunnel": "yes", "highway": "service"}),
        ("-2071", ["t2", "t3"], {"tunnel": "yes", "highway": "service"}),
    ]
    if cross:
        road = LineString([(50.0, -30.0), (50.0, 2.0)])
    else:
        road = LineString([(0.0, -8.0), (100.0, -8.0)])
    other = [(road, frozenset({"r0", "r1"}), "-9000")]
    from shapely.strtree import STRtree
    return ways_r, nodes_m, other, STRtree([road])


class TestTheVetoIsScopedToWhatItWasWrittenFor:

    def _run(self, ways_r, nodes_m, other, tree, *, gate,
             gate_union=None, cover_union=None, detail=None,
             monkeypatch=None):
        monkeypatch.setenv(T3_FLAG, gate)
        return bridges._compute_tunnel_system_veto(
            ways_r, nodes_m, set(), 15.0, True, other, tree, set(),
            airside_gate_union=gate_union,
            own_bore_cover_union=cover_union,
            veto_detail=detail)

    def test_lmml_class_crossing_off_airport_still_vetoes(self,
                                                         monkeypatch):
        """PRESERVED PRIOR RULING (user 2026-06-12, LMML): a crossing
        foreign road vetoes, and the verdict still propagates across the
        system."""
        ways_r, nodes_m, other, tree = _veto_world(cross=True)
        veto = self._run(ways_r, nodes_m, other, tree, gate="1",
                         monkeypatch=monkeypatch)
        assert veto["-2070"] is True
        assert veto["-2071"] is True, (
            "an interchange tangle stays out WHOLE — crossings propagate")

    def test_a_merely_near_road_no_longer_kills_the_system(self,
                                                          monkeypatch):
        """§T3.1(b): system propagation drops for NON-crossing
        neighbours.  The near road still vetoes its own way; it does not
        take the rest of the system with it."""
        ways_r, nodes_m, other, tree = _veto_world(cross=False)
        veto = self._run(ways_r, nodes_m, other, tree, gate="1",
                         monkeypatch=monkeypatch)
        assert veto["-2070"] is True
        assert veto["-2071"] is False

    def test_off_the_near_road_kills_the_whole_system_as_before(
            self, monkeypatch):
        ways_r, nodes_m, other, tree = _veto_world(cross=False)
        veto = self._run(ways_r, nodes_m, other, tree, gate="0",
                         monkeypatch=monkeypatch)
        assert veto["-2070"] is True
        assert veto["-2071"] is True

    def test_a_portal_inside_the_airside_gate_is_never_vetoed(
            self, monkeypatch):
        """§T3.1(a): an airport's own bore is never vetoed by its own
        service roads."""
        ways_r, nodes_m, other, tree = _veto_world(cross=True)
        gate_u = _rect(-10.0, -10.0, 10.0, 10.0)     # around portal t0
        detail = {}
        veto = self._run(ways_r, nodes_m, other, tree, gate="1",
                         gate_union=gate_u, detail=detail,
                         monkeypatch=monkeypatch)
        assert veto["-2070"] is False
        assert detail["-2070"]["exempt"] == "portal_in_airside_gate"
        assert detail["-2070"]["exempted_veto"] is True

    def test_a_bore_under_airside_pavement_is_never_vetoed(self,
                                                          monkeypatch):
        ways_r, nodes_m, other, tree = _veto_world(cross=True)
        cover_u = _rect(30.0, -20.0, 70.0, 20.0)     # apron over the span
        detail = {}
        veto = self._run(ways_r, nodes_m, other, tree, gate="1",
                         cover_union=cover_u, detail=detail,
                         monkeypatch=monkeypatch)
        assert veto["-2070"] is False
        assert detail["-2070"]["exempt"] == "covered_by_airside_pavement"

    def test_the_exempt_bore_does_not_drag_its_system_either(self,
                                                            monkeypatch):
        ways_r, nodes_m, other, tree = _veto_world(cross=True)
        cover_u = _rect(30.0, -20.0, 70.0, 20.0)
        veto = self._run(ways_r, nodes_m, other, tree, gate="1",
                         cover_union=cover_u, monkeypatch=monkeypatch)
        assert veto["-2071"] is False

    def test_off_the_own_bore_evidence_is_ignored(self, monkeypatch):
        ways_r, nodes_m, other, tree = _veto_world(cross=True)
        veto = self._run(ways_r, nodes_m, other, tree, gate="0",
                         gate_union=_rect(-10, -10, 10, 10),
                         monkeypatch=monkeypatch)
        assert veto["-2070"] is True

    def test_the_own_bore_cover_roles_are_runway_apron_taxiway(self):
        from auto_patch.layout import (ROLE_JUNCTION, ROLE_PRIMARY_PARALLEL,
                                       ROLE_STUB)
        roles = bridges._TUNNEL_OWN_BORE_COVER_ROLES
        for role in (ROLE_RUNWAY, ROLE_APRON, ROLE_JUNCTION,
                     ROLE_PRIMARY_PARALLEL, ROLE_STUB):
            assert role in roles
        assert ROLE_SERVICE_ROAD not in roles, (
            "an airport's own SERVICE roads are what the ruling scopes "
            "the veto away from — they are not the cover evidence")


class TestTheVetoIsRecordedNotThrownAway:
    """§T3.2: refusals recorded and thrown away are the class this
    campaign exists to kill."""

    def test_the_sidecar_carries_the_register(self, tmp_path):
        lay = PavementLayout(icao="LEMD", anchor=(40.5, -3.58))
        lay.tunnel_passthrough_findings = [
            {"way_id": "-2070", "refused_because": "adjacent_road_veto"},
            {"way_id": "-2085", "refused_because": "no_cover_no_cut"},
        ]
        out = tmp_path / "p.osm"
        lay.to_osm(str(out))
        data = json.loads((tmp_path / "p.osm.axes.json").read_text())
        assert "tunnel_vetoes" in data, (
            "written UNCONDITIONALLY so 'nothing was refused' ([]) is "
            "distinguishable from 'this patch predates the register'")
        assert [r["way_id"] for r in data["tunnel_vetoes"]] == [
            "-2070", "-2085"]

    def test_an_airport_that_refused_nothing_still_writes_the_key(
            self, tmp_path):
        lay = PavementLayout(icao="LEMD", anchor=(40.5, -3.58))
        out = tmp_path / "p.osm"
        lay.to_osm(str(out))
        data = json.loads((tmp_path / "p.osm.axes.json").read_text())
        assert data["tunnel_vetoes"] == []


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
        tpa = _load_acceptance()
        args = tpa.build_parser().parse_args([
            "P.osm", "--site", "A=1,2",
            "--bore-osm", "_airport_road_feed/LEMD_road_feed.cache",
            "--bore-ways", "-2070,-2119",
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
