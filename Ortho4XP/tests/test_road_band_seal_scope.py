"""ROAD BAND-SEAL SCOPE + ROAD↔APRON EDGE CONFORMANCE — the twins.

Spec ``docs/specs/road-band-seal-scope-spec.md``; owner rulings: the
seal-scope half is owner-approved option (a) (2026-08-25), the contact half
is RULINGS 2026-08-25b ("a road sharing an edge with an apron conforms to
the strictest grade — it becomes part of the apron").

(a) A road ring beyond the band's off-net radius with a lawful descent:
    flag ON it is not sealed and the descent survives; flag OFF the
    historic clamp reproduces.
(b) AIRSIDE sealing is byte-identical between the two flag states — the
    change removes roles from the scope and touches nothing else.
(c) An edge-sharing road ring CONFORMS WITHOUT RECLASSIFICATION: it takes
    the apron cap end to end and seeds from the apron datum, while staying
    road-family population — no absorption, no merge, no role change
    (Amendment 1, on attempt 1's measurement that absorbing them moved
    HECA airside 1,735 → 1,948 and SPJC 175 → 178).  A free road 2 m away
    takes neither (canonical identity, never proximity — the ruling's own
    boundary, and the near-miss class it excludes).
(d) The two spellings each half needs — the seal's scope against the band
    engine's own domain, and the seam audit's road-family literals against
    ``auto_patch.layout`` — cannot drift.

Headless: hand-built layouts and polygons, an explicit band closure, no
DEM, no build.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon
from shapely.strtree import STRtree

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from auto_patch import config as CFG                                # noqa: E402
from auto_patch import lateral_contiguity as LC                     # noqa: E402
from auto_patch.elevation_per_surface import building_feasibility as BF  # noqa: E402
from auto_patch.elevation_per_surface import raster_reach_band as RRB  # noqa: E402
from auto_patch.elevation_per_surface import solver_primitives as SP  # noqa: E402
from auto_patch.layout import (                                     # noqa: E402
    BuiltShape, ROLE_APRON, ROLE_BUILDING, ROLE_JUNCTION, ROLE_RUNWAY,
    ROLE_RUNWAY_CROSSING, ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD)


class _Layout:
    def __init__(self, shapes):
        self.shapes = shapes
        self.band_clamp_findings = []


def _square(x0=0.0, y0=0.0, side=10.0):
    return Polygon([(x0, y0), (x0 + side, y0), (x0 + side, y0 + side),
                    (x0, y0 + side), (x0, y0)])


def _shape(role, alts, poly=None):
    s = BuiltShape(role=role, polygon=poly if poly is not None else _square())
    s.node_altitudes = list(alts)
    return s


def _band(floor=4.6, ceiling=9.4):
    """The band of record — the AIRCRAFT band, which states no road law.

    Constant over the plane, which is exactly the defect's shape: the
    raster band prices an off-mask point at the APRON cap × its offset out
    to a 30 m horizon, so a road 25 m from the nearest airside cell is
    handed an interval computed under a law it is not under.
    """
    return lambda x, y: (floor, ceiling)


# ══════════════════════════════════════════════════════════════════
# (a) + (b) — the seal's scope
# ══════════════════════════════════════════════════════════════════
class TestSealScopeIsTheBandsOwnDomain:

    def test_the_scope_is_derived_from_the_band_engine_not_retyped(self):
        """(d) ONE source: the seal's roles ARE the band's domain roles
        minus the hard ones.  A second hand-written list is the
        census-wrapper defect."""
        scope = SP.seal_role_scope()
        assert scope == RRB.band_domain_roles() - SP.SEAL_HARD_ROLES
        # The road family is out, and the hard datums stay out.
        assert ROLE_SERVICE_ROAD not in scope
        assert ROLE_SERVICE_JUNCTION not in scope
        assert ROLE_RUNWAY not in scope and ROLE_RUNWAY_CROSSING not in scope
        # The airside surfaces the band DOES legislate are in.
        assert {ROLE_APRON, ROLE_JUNCTION, ROLE_BUILDING} <= scope

    def test_the_flag_off_restores_the_historic_scope(self, monkeypatch):
        monkeypatch.setenv(SP.SEAL_AIRSIDE_ONLY_FLAG, "0")
        scope = SP.seal_role_scope()
        assert scope == frozenset(SP.PAVEMENT_ROLES) - SP.SEAL_HARD_ROLES
        assert ROLE_SERVICE_ROAD in scope and ROLE_SERVICE_JUNCTION in scope

    @pytest.mark.parametrize("role", [ROLE_SERVICE_ROAD,
                                      ROLE_SERVICE_JUNCTION])
    def test_a_road_off_the_airside_net_keeps_its_lawful_descent(self, role):
        """(a) The road descends 0.8 m over its 10 m ring — 8 %, its own
        cap — and every value is below the aircraft band's floor.  ON: the
        seal leaves it alone and the descent SURVIVES."""
        alts = [3.0, 2.2, 2.2, 3.0]
        s = _shape(role, alts)
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        assert SP.seal_pavement_to_band(layout, "TEST") == 0
        assert s.node_altitudes == alts
        assert layout.band_clamp_findings == []

    @pytest.mark.parametrize("role", [ROLE_SERVICE_ROAD,
                                      ROLE_SERVICE_JUNCTION])
    def test_the_flag_off_reproduces_the_historic_clamp(self, role,
                                                        monkeypatch):
        """(a) OFF: the same ring is clamped to the aircraft band's floor
        and the descent is flattened into the step the owner reported."""
        monkeypatch.setenv(SP.SEAL_AIRSIDE_ONLY_FLAG, "0")
        alts = [3.0, 2.2, 2.2, 3.0]
        s = _shape(role, alts)
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        assert SP.seal_pavement_to_band(layout, "TEST") == 1
        assert s.node_altitudes != alts
        assert max(s.node_altitudes) >= 4.6 - 1e-9
        assert layout.band_clamp_findings

    def test_airside_sealing_is_byte_identical_between_flag_states(
            self, monkeypatch):
        """(b) The change REMOVES roles from the scope; what stays in it is
        sealed to the same numbers, shape for shape, finding for finding."""
        def _run(flag):
            monkeypatch.setenv(SP.SEAL_AIRSIDE_ONLY_FLAG, flag)
            shapes = [
                _shape(ROLE_APRON, [20.0, 20.0, 20.0, 20.0]),
                _shape(ROLE_JUNCTION, [1.0, 1.0, 1.0, 1.0]),
                _shape(ROLE_BUILDING, [12.0, 11.0, 11.0, 12.0]),
                _shape(ROLE_RUNWAY, [20.0, 20.0, 20.0, 20.0]),
                _shape(ROLE_RUNWAY_CROSSING, [20.0, 20.0, 20.0, 20.0]),
            ]
            layout = _Layout(shapes)
            BF.publish_band_of_record(layout, _band())
            SP.seal_pavement_to_band(layout, "TEST")
            return ([tuple(s.node_altitudes) for s in shapes],
                    list(layout.band_clamp_findings))

        assert _run("1") == _run("0")

    def test_the_fingerprint_still_covers_the_roads_it_no_longer_clamps(
            self):
        """The seal stops CLAMPING roads; it does not stop WATCHING them.
        A post-seal author on a road must still be nameable."""
        s = _shape(ROLE_SERVICE_ROAD, [3.0, 2.2, 2.2, 3.0])
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        SP.seal_pavement_to_band(layout, "TEST")
        assert SP.verify_band_seal(layout) == []
        s.node_altitudes = [9.0, 2.2, 2.2, 3.0]              # a late author
        moved = SP.verify_band_seal(layout)
        assert moved and moved[0][1] == ROLE_SERVICE_ROAD


# ══════════════════════════════════════════════════════════════════
# (c) — edge-sharing contact takes the apron's law
# ══════════════════════════════════════════════════════════════════
def _contact_fixture(offset_m: float):
    """An apron, and a road ring END-ON to it, ``offset_m`` away.

    ``0.0`` shares the apron's edge exactly (two common vertices —
    canonical identity).  Any other offset is proximity, which the ruling
    excludes.  The road runs AWAY from the apron, so no perpendicular
    probe cast along the road's own axis can ever see the apron: this is
    the end connection the pre-ruling closure excluded, and the population
    the HECA measurement found (162 of 469 shared edges).
    """
    x0 = 10.0
    y0 = 0.0 - offset_m
    # The apron carries the road's two frontage vertices — that is what the
    # T-vertex weld leaves behind, and it is why the contact is an EDGE and
    # not merely a collinear touch.  (An UNWELDED collinear touch is not
    # contact by this law: the late ``rebind_only`` pass is the reader that
    # sees the welded arrangement, which is exactly why the law binds its
    # number there.)
    apron = Polygon([(0.0, 0.0), (x0, 0.0), (x0 + 6.0, 0.0), (40.0, 0.0),
                     (40.0, 40.0), (0.0, 40.0)])
    road = Polygon([(x0, y0), (x0 + 6.0, y0),
                    (x0 + 6.0, y0 - 40.0), (x0, y0 - 40.0)])
    polys = [apron, road]
    roles = [ROLE_APRON, ROLE_SERVICE_ROAD]
    return polys, roles, STRtree(polys)


class TestEdgeSharingContactIsTheApron:

    def test_a_shared_edge_is_seen_and_it_is_the_apron(self):
        polys, roles, tree = _contact_fixture(0.0)
        assert LC.edge_shared_roles(polys[1], tree, polys, roles, 1) == {
            ROLE_APRON}

    def test_a_free_road_two_metres_away_is_not_contact(self):
        """The ruling's boundary is EDGE-SHARING; 2 m is a near miss and a
        near miss is REPORTED, never absorbed."""
        polys, roles, tree = _contact_fixture(2.0)
        assert LC.edge_shared_roles(polys[1], tree, polys, roles, 1) == set()

    def test_a_sub_millimetre_gap_is_not_a_shared_edge_either(self):
        """Identity, not proximity: the quantisation is a SPELLING
        tolerance, so even a 1 mm gap — ten times the identity tolerance,
        and still far below any real gap — is not contact."""
        polys, roles, tree = _contact_fixture(0.001)
        assert LC.edge_shared_roles(polys[1], tree, polys, roles, 1) == set()

    def test_an_END_ON_contact_ring_keeps_the_FREE_ROAD_class(self):
        """SUPERSEDED BY THE OWNER, 2026-08-28e (HECA round 5 items
        2/3/4; spec ``heca-round5-drainage-and-ramps-spec.md`` LAW 2).

        This fixture is a road running 40 m AWAY from the apron, sharing
        only its end edge — and until this round it took the apron's 1 %
        along that whole run.  Owner, verbatim: *"THE DEFECT IS SCOPING …
        fix the scoping so the stretch beyond the apron prices and solves
        at the 8 % free class."*  Contact still binds the VALUES at the
        weld (canonical identity, and the contact-DATUM seeding below);
        it no longer prices the cap.  Measured at HECA on the tree that
        carried the old law: service_road 2863 held at 0.010000 over its
        130 m run to taxiway junction -12711."""
        polys, roles, tree = _contact_fixture(0.0)
        _st, caps = LC.station_caps(polys[1], tree, polys, roles, 1)
        got = {c for c in caps if c is not None}
        assert got == {CFG.ROLE_GRADE_LIMITS[ROLE_SERVICE_ROAD]}, (
            "an END-ON contact ring is still priced at the apron cap — "
            "the scoping defect the owner ruled on")
        assert (CFG.ROLE_GRADE_LIMITS[ROLE_APRON]
                < CFG.ROLE_GRADE_LIMITS[ROLE_SERVICE_ROAD])

    def test_the_scope_gate_off_restores_the_ring_wide_pricing(
            self, monkeypatch):
        """The pre-round law, byte-identically, for the A/B arm."""
        monkeypatch.setattr(CFG, "ROAD_CONTACT_CAP_SCOPE", False)
        polys, roles, tree = _contact_fixture(0.0)
        _st, caps = LC.station_caps(polys[1], tree, polys, roles, 1)
        assert {c for c in caps if c is not None} == {
            CFG.ROLE_GRADE_LIMITS[ROLE_APRON]}

    def test_a_road_ALONGSIDE_an_apron_still_takes_the_apron_cap(self):
        """25b's SUBSTANCE is preserved where it is true: a road that
        stands inside or alongside an apron is LATERALLY CONTIGUOUS with
        it, so the perpendicular walk reads the apron at every station and
        the ring prices at 1 % with no contact term at all.  Only the
        END-ON class — 162 of HECA's 469 shared edges, this module's own
        measurement — is released to the free class."""
        apron = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 10.0),
                         (0.0, 10.0)])
        # The road runs ALONG the apron's edge for its first 60 m and
        # then 40 m BEYOND it — the owner's own picture ("cut each road
        # at the stations where it stops being free").
        road = Polygon([(0.0, 10.0), (100.0, 10.0), (100.0, 16.0),
                        (0.0, 16.0)])
        polys = [apron, road]
        roles = [ROLE_APRON, ROLE_SERVICE_ROAD]
        tree = STRtree(polys)
        st, caps = LC.station_caps(road, tree, polys, roles, 1)
        beside = [c for (p, c) in zip(st, caps)
                  if p is not None and c is not None and p[0] <= 55.0]
        beyond = [c for (p, c) in zip(st, caps)
                  if p is not None and c is not None and p[0] >= 65.0]
        assert beside and set(beside) == {
            CFG.ROLE_GRADE_LIMITS[ROLE_APRON]}, (
            "a road ALONGSIDE an apron must still price at the apron cap "
            "— 25b's substance, carried by the lateral walk")
        assert beyond and set(beyond) == {
            CFG.ROLE_GRADE_LIMITS[ROLE_SERVICE_ROAD]}, (
            "the stretch BEYOND the apron must price at the free-road "
            "class (owner 2026-08-28e)")

    def test_a_free_road_keeps_its_own_cap(self):
        polys, roles, tree = _contact_fixture(2.0)
        _st, caps = LC.station_caps(polys[1], tree, polys, roles, 1)
        assert {c for c in caps if c is not None} <= {
            CFG.ROLE_GRADE_LIMITS[ROLE_SERVICE_ROAD]}

    def test_the_gate_off_restores_the_pre_ruling_law(self, monkeypatch):
        monkeypatch.setattr(CFG, "ROAD_APRON_EDGE_CONFORMANCE", False)
        polys, roles, tree = _contact_fixture(0.0)
        _st, caps = LC.station_caps(polys[1], tree, polys, roles, 1)
        assert {c for c in caps if c is not None} <= {
            CFG.ROLE_GRADE_LIMITS[ROLE_SERVICE_ROAD]}

    def test_the_term_never_widens_past_the_apron(self):
        """The ruling names the APRON.  A building pad sharing an edge is
        reported by the attribution tool and ruled on separately — it is
        not quietly folded in here."""
        polys, roles, tree = _contact_fixture(0.0)
        roles = [ROLE_BUILDING, ROLE_SERVICE_ROAD]
        assert LC.edge_shared_roles(polys[1], tree, polys, roles, 1) == set()

    def test_conformance_never_reclassifies_the_ring(self):
        """Amendment 1 clause 1: the contact ring REMAINS road-family
        population.  The law pass stamps the contact and carries the
        apron cap; it must not absorb, merge or re-role the shape."""
        from auto_patch import groundside as GS
        from auto_patch.layout import BuiltShape

        polys, roles, _tree = _contact_fixture(0.0)
        apron = BuiltShape(role=ROLE_APRON, polygon=polys[0])
        apron.node_altitudes = [10.0] * len(polys[0].exterior.coords[:-1])
        road = BuiltShape(role=ROLE_SERVICE_ROAD, polygon=polys[1])

        class _L:
            pass

        layout = _L()
        layout.shapes = [apron, road]
        summary = GS.apply_lateral_contiguity_law(layout, "TEST")

        assert summary["apron_contact"] == 1
        assert summary["absorbed"] == 0 and summary["cut"] == 0
        survivors = [s for s in layout.shapes if s is road]
        assert survivors, "the contact ring was absorbed or replaced"
        assert road.role == ROLE_SERVICE_ROAD          # no role conversion
        assert road.apron_contact is True
        # (a) the ring is STAMPED as contact — the value half of the law
        # (the identity welds and the contact-DATUM seeding) is untouched
        # — but an END-ON ring is no longer PRICED at the apron cap
        # (owner 2026-08-28e; see the scoping twin above).
        assert road.lateral_cap is None
        # The apron is untouched — airside is king, and this law reads it.
        assert apron.polygon.equals(polys[0])

    def test_the_gate_off_restores_the_absorption_path(self, monkeypatch):
        """``O4_ROAD_APRON_EDGE_CONFORM=0`` must restore the PRE-RULING law
        exactly — including the absorption the stamp otherwise blocks.  A
        gate that only silenced the cap would leave the arm neither old nor
        new, and the two arms could not be compared."""
        monkeypatch.setattr(CFG, "ROAD_APRON_EDGE_CONFORMANCE", False)
        from auto_patch import groundside as GS
        from auto_patch.layout import BuiltShape

        polys, roles, _tree = _contact_fixture(0.0)
        apron = BuiltShape(role=ROLE_APRON, polygon=polys[0])
        apron.node_altitudes = [10.0] * len(polys[0].exterior.coords[:-1])
        road = BuiltShape(role=ROLE_SERVICE_ROAD, polygon=polys[1])

        class _L:
            pass

        layout = _L()
        layout.shapes = [apron, road]
        summary = GS.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["apron_contact"] == 0
        assert road.apron_contact is False

    def test_a_free_road_is_neither_stamped_nor_capped(self):
        from auto_patch import groundside as GS
        from auto_patch.layout import BuiltShape

        polys, roles, _tree = _contact_fixture(2.0)
        apron = BuiltShape(role=ROLE_APRON, polygon=polys[0])
        apron.node_altitudes = [10.0] * len(polys[0].exterior.coords[:-1])
        road = BuiltShape(role=ROLE_SERVICE_ROAD, polygon=polys[1])

        class _L:
            pass

        layout = _L()
        layout.shapes = [apron, road]
        summary = GS.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["apron_contact"] == 0
        assert road.apron_contact is False
        assert road.lateral_cap is None

    def test_an_apron_is_never_judged_against_itself(self):
        """The term applies to the ROAD family only — an apron sharing an
        edge with another apron is not a road taking a cap."""
        polys, roles, tree = _contact_fixture(0.0)
        roles = [ROLE_APRON, ROLE_APRON]
        _st, caps = LC.station_caps(polys[1], tree, polys, roles, 1)
        assert {c for c in caps if c is not None} <= {
            CFG.ROLE_GRADE_LIMITS[ROLE_APRON]}


# ══════════════════════════════════════════════════════════════════
# (c) part 3 — the seeding: the apron DATUM, not the terrain
# ══════════════════════════════════════════════════════════════════
class _SeedLayout:
    def __init__(self, shapes):
        from auto_patch.canonical_points import CanonicalPointRegistry
        self.icao = "TEST"
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = []
        self._slice_service_subsegments = []

    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)


def _seed_fixture(contact: bool):
    """An apron at 100 m sharing its whole east edge with a 200 m road,
    over terrain 10 m below.  The shared edge's two vertices are
    canonical-identical, so they are exact-vertex ANCHORS carrying the
    apron's value — clause 2(b), automatic.  What the twin measures is
    clause 2(c): what the ring's INTERIOR reaches for."""
    from auto_patch.layout import BuiltShape
    apron_ring = [(-30.0, -3.0), (0.0, -3.0), (0.0, 3.0), (-30.0, 3.0)]
    xs = [0.0, 50.0, 100.0, 150.0, 200.0]
    road_ring = ([(x, -3.0) for x in xs]
                 + [(x, 3.0) for x in reversed(xs)])
    apron = BuiltShape(polygon=Polygon(apron_ring), role=ROLE_APRON)
    road = BuiltShape(polygon=Polygon(road_ring), role=ROLE_SERVICE_ROAD)
    road.lateral_cap = CFG.ROLE_GRADE_LIMITS[ROLE_APRON]
    road.apron_contact = contact
    layout = _SeedLayout([apron, road])
    b2i, nodes = {}, []
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            key = layout.canonical_points.get_or_add(float(x), float(y))
            if key not in b2i:
                b2i[key] = len(nodes)
                nodes.append((float(x), float(y)))

    def _idx(x, y):
        return b2i[layout.canonical_points.get_or_add(float(x), float(y))]

    elev = [90.0] * len(nodes)
    dem = [90.0] * len(nodes)
    for (x, y) in apron_ring:
        elev[_idx(x, y)] = 100.0
    return layout, b2i, elev, dem, _idx


class TestContactSeedingUsesTheApronDatum:

    def _run(self, contact, monkeypatch):
        from auto_patch.elevation_per_surface.route_profile import (
            anchors as ANCH)
        # The free-end DEM tie is its own law and would anchor the far
        # terminus to terrain; this twin isolates the seeding term.
        monkeypatch.setattr(CFG, "SERVICE_CORRIDOR_FREE_END_ANCHOR", False)
        layout, b2i, elev, dem, _idx = _seed_fixture(contact)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.ROLE_GRADE_LIMITS[ROLE_SERVICE_ROAD])
        return elev, _idx

    def test_the_contact_ring_seeds_from_the_datum_not_the_dem(
            self, monkeypatch):
        elev, _idx = self._run(True, monkeypatch)
        # The shared edge holds the apron's value by identity …
        assert elev[_idx(0.0, -3.0)] == pytest.approx(100.0, abs=1e-6)
        # … and the interior is carried outward from it under the apron
        # cap, NOT pulled down to the 90 m terrain.
        assert elev[_idx(50.0, -3.0)] == pytest.approx(100.0, abs=0.01)
        assert elev[_idx(200.0, 3.0)] == pytest.approx(100.0, abs=0.01)

    def test_without_the_contact_stamp_it_follows_the_dem(self, monkeypatch):
        """The control: the same geometry, not stamped as contact, is the
        pre-ruling DEM-follow — it dives toward terrain as far as the cap
        allows."""
        elev, _idx = self._run(False, monkeypatch)
        assert elev[_idx(0.0, -3.0)] == pytest.approx(100.0, abs=1e-6)
        far = elev[_idx(200.0, 3.0)]
        assert far < 99.9, "the control did not DEM-follow at all"

    def test_the_gate_off_restores_the_dem_follow(self, monkeypatch):
        monkeypatch.setattr(CFG, "ROAD_APRON_EDGE_CONFORMANCE", False)
        elev, _idx = self._run(True, monkeypatch)
        assert elev[_idx(200.0, 3.0)] < 99.9


# ══════════════════════════════════════════════════════════════════
# (d) — the spellings that must not drift
# ══════════════════════════════════════════════════════════════════
class TestSpellingsCannotDrift:

    def test_the_seam_audits_road_literals_are_the_layouts_roles(self):
        from auto_patch import mutation_seam_audit as MSA
        assert MSA.ROAD_FAMILY_ROLES == frozenset({ROLE_SERVICE_ROAD,
                                                   ROLE_SERVICE_JUNCTION})

    def test_the_lateral_laws_road_roles_are_the_same_family(self):
        assert LC.ROAD_ROLES == frozenset({ROLE_SERVICE_ROAD,
                                           ROLE_SERVICE_JUNCTION})

    def test_the_apron_contact_role_is_the_layouts_apron(self):
        assert LC.APRON_CONTACT_ROLES == frozenset({ROLE_APRON})

    def test_the_attribution_tool_reads_the_engines_domain(self):
        """Tool discipline: the promoted attribution tool
        (``tools/band_clamp_attrib.py``) must IMPORT the band's role set,
        never re-type it — the defect the census wrappers taught."""
        tools = Path(__file__).resolve().parents[1] / "tools"
        src = (tools / "band_clamp_attrib.py").read_text()
        assert "from auto_patch.elevation_per_surface.raster_reach_band" in src
        assert "band_domain_roles" in src
        assert "DOMAIN_ROLES = band_domain_roles()" in src
