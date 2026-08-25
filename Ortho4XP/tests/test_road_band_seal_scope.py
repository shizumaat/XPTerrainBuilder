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
(c) An edge-sharing road ring takes the apron cap; a free road 2 m away
    does not (canonical identity, never proximity — the ruling's own
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

    def test_the_contact_ring_takes_the_apron_cap_at_every_station(self):
        """"It becomes part of the apron": the ring takes ONE cap end to
        end, not an apron cap at the contact and a road cap 30 m away —
        the latter is the step the ruling exists to remove."""
        polys, roles, tree = _contact_fixture(0.0)
        _st, caps = LC.station_caps(polys[1], tree, polys, roles, 1)
        got = {c for c in caps if c is not None}
        assert got == {CFG.ROLE_GRADE_LIMITS[ROLE_APRON]}
        assert (CFG.ROLE_GRADE_LIMITS[ROLE_APRON]
                < CFG.ROLE_GRADE_LIMITS[ROLE_SERVICE_ROAD])

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

    def test_an_apron_is_never_judged_against_itself(self):
        """The term applies to the ROAD family only — an apron sharing an
        edge with another apron is not a road taking a cap."""
        polys, roles, tree = _contact_fixture(0.0)
        roles = [ROLE_APRON, ROLE_APRON]
        _st, caps = LC.station_caps(polys[1], tree, polys, roles, 1)
        assert {c for c in caps if c is not None} <= {
            CFG.ROLE_GRADE_LIMITS[ROLE_APRON]}


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
