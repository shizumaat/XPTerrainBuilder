"""ROAD ↔ AIRSIDE CROSSING CONFORMANCE — the §2 twin.

Spec: ``docs/specs/road-airside-crossing-conformance-spec.md`` (owner
RULINGS 2026-08-26b item 2).  Owner, verbatim: *service roads crossing
taxiways, like here: 30.104671, 31.3973462, have to grade smoothly to
match the apron elevation, not leave a cliff.*  AIRSIDE IS KING: the road
takes the airside value; the airside surface feels ZERO pull.

WHY NO STANDING LAW FIRED (measured on
``/tmp/harness/HECA_20260826T213425.osm``):

* the free-road width test (2026-07-27 + R7a) reads WIDTH ONLY, and a
  road CROSSING a taxiway is narrow at the crossing — HECA axis 709
  carries cap 0.08 while running at 0.00 m INSIDE junction rings -10250 /
  -12453 / -12452 / -12708;
* the 2026-08-25b edge-conformance term is scoped ``{"apron"}`` and keys
  on literally shared vertices, and the road there shares no node with
  the JUNCTIONS it abuts;
* the 2026-08-15 proximity mouth seat has the right shape but the wrong
  reach: its 1.5 m tolerance is derived from the corridor minter's
  cut-back, and the owner site's contact nodes stand 1.538–1.60 m out.

The spec's §2 twin, verbatim: *synthetic taxiway at +3 m over ambient,
service road crossing it: crossing stretch takes the taxiway values (pins
at entry/exit), road descends both sides at ≤ its cap, taxiway vertices
BYTE-IDENTICAL to a road-less control (airside-is-king assertion); flag
OFF reproduces the step.*

Hand-computed geometry, no build, no network.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters (auto_patch/CLAUDE.md, "Import cycle").
import auto_patch.pipeline                                    # noqa: E402,F401
from auto_patch import config as CFG                          # noqa: E402
from auto_patch import grade_graph as GG                      # noqa: E402
from auto_patch import groundside as GS                       # noqa: E402
from auto_patch import lateral_contiguity as LC               # noqa: E402
from auto_patch.canonical_points import (                     # noqa: E402
    CanonicalPointRegistry)
from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    anchors as ANCH)
from auto_patch.enclaves import ENCLAVE_AIRSIDE_ROLES         # noqa: E402
from auto_patch.layout import BuiltShape                      # noqa: E402

CAP = CFG.SERVICE_ROAD_MAX_GRADE

# The synthetic frame.  A taxiway band running EAST-WEST, a service road
# running NORTH-SOUTH straight across it.
AMBIENT = 100.0                 # the DEM the road would follow
TAXI_Z = AMBIENT + 3.0          # "+3 m over ambient" (spec §2)
TAXI_HALF_W = 11.5              # a code-C taxiway's half width
TAXI_HALF_L = 60.0
ROAD_HALF_W = 3.0
ROAD_END = 60.0
# The owner site's own gap: the road body stands clear of the pavement it
# meets by MORE than the 2026-08-15 mouth tolerance (1.5 m), which is
# exactly why that law does not reach it there.
GAP_M = 1.6
ROAD_NEAR_Y = TAXI_HALF_W + GAP_M         # 13.1


class _Layout:
    def __init__(self, shapes, service_lines=()):
        self.icao = "TEST"
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = []
        self._slice_service_subsegments = list(service_lines)
        self._apron_spine_subsegments = []

    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)


def _taxi_ring():
    return [(-TAXI_HALF_L, -TAXI_HALF_W), (TAXI_HALF_L, -TAXI_HALF_W),
            (TAXI_HALF_L, TAXI_HALF_W), (-TAXI_HALF_L, TAXI_HALF_W)]


def _road_ring(y0, y1):
    """A road body from ``y0`` to ``y1``, with intermediate stations so the
    descent away from the pin has vertices to be measured at."""
    ys = [y0]
    step = (y1 - y0) / 4.0
    ys += [y0 + step * k for k in (1, 2, 3)]
    ys.append(y1)
    return ([(-ROAD_HALF_W, y) for y in ys]
            + [(ROAD_HALF_W, y) for y in reversed(ys)])


def _crossing_layout(with_road: bool = True):
    """The spec's §2 geometry.

    The taxiway is ALREADY SOLVED at ``TAXI_Z``; the road bodies stop
    ``GAP_M`` clear of it on both sides (the slice never emits a service
    face inside airside pavement — at HECA the crossed junctions own that
    ground outright), and the road CENTERLINE runs straight across.
    """
    shapes = [BuiltShape(polygon=Polygon(_taxi_ring()),
                         role="primary_parallel")]
    lines = []
    if with_road:
        south = BuiltShape(polygon=Polygon(_road_ring(-ROAD_END,
                                                      -ROAD_NEAR_Y)),
                           role="service_road")
        north = BuiltShape(polygon=Polygon(_road_ring(ROAD_NEAR_Y,
                                                      ROAD_END)),
                           role="service_road")
        south.lateral_cap = north.lateral_cap = None
        shapes += [south, north]
        lines = [LineString([(0.0, -ROAD_END), (0.0, ROAD_END)])]
    layout = _Layout(shapes, lines)

    b2i, nodes = {}, []
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            key = layout.canonical_points.get_or_add(float(x), float(y))
            if key not in b2i:
                b2i[key] = len(nodes)
                nodes.append((float(x), float(y)))
    elev = [0.0] * len(nodes)
    dem = [AMBIENT] * len(nodes)

    def _idx(x, y):
        return b2i[layout.canonical_points.get_or_add(float(x), float(y))]

    for (x, y) in _taxi_ring():
        elev[_idx(x, y)] = TAXI_Z
    return layout, b2i, elev, dem, _idx


def _contacts(layout):
    return GS.road_airside_crossing_contacts(layout, "TEST")


def _run(layout, b2i, elev, dem):
    return ANCH.apply_service_road_dem_follow(layout, b2i, elev, dem, CAP)


# ══════════════════════════════════════════════════════════════════════
# §1.1 — THE CONTACT POPULATION
# ══════════════════════════════════════════════════════════════════════

class TestTheCrossingIsRecognised:

    def test_the_crossing_stretch_stands_in_airside_pavement(self):
        """The stretch whose CROSS-SECTION reaches airside pavement is
        the conforming one — and only that stretch."""
        layout, *_ = _crossing_layout()
        s = _contacts(layout)
        assert s["conforming"] == 1, (
            "the road crossing the taxiway produced no conforming stretch")
        piece = layout._airside_conform_subsegments[0]
        ys = [p[1] for p in piece.coords]
        assert min(ys) <= -TAXI_HALF_W + 5.0
        assert max(ys) >= TAXI_HALF_W - 5.0
        # …and it does NOT swallow the free road outside the pavement.
        assert piece.length < 2 * TAXI_HALF_W + 4 * GS.\
            AIRSIDE_CROSSING_SAMPLE_STEP_M

    def test_the_free_road_outside_is_untouched(self):
        """A road that never meets airside pavement has no conforming
        stretch at all — the width test's answer is unchanged there."""
        layout, *_ = _crossing_layout()
        layout.shapes = [s for s in layout.shapes
                         if s.role != "primary_parallel"]
        assert _contacts(layout)["conforming"] == 0

    def test_the_register_is_the_canonical_airside_family(self):
        """"read them from one existing register, never a hand list"
        (spec §1.1).  A ``graded_strip`` is the road's OWN grading product
        at the road's own level — a pin to one pins the road at exactly
        the value the law replaces (the 2026-08-15 carrier adjudication),
        so it may never be a conformance carrier."""
        assert "graded_strip" not in ENCLAVE_AIRSIDE_ROLES
        assert "building" not in ENCLAVE_AIRSIDE_ROLES
        assert {"apron", "junction", "primary_parallel", "stub",
                "runway"} <= set(ENCLAVE_AIRSIDE_ROLES)
        assert ENCLAVE_AIRSIDE_ROLES <= LC.airside_contact_roles()

    def test_the_25b_edge_term_now_reaches_a_junction(self):
        """§0's second named reason: the 25b contact term was scoped
        ``{"apron"}``, so a road sharing an edge with a taxi JUNCTION
        conformed to nothing."""
        assert "junction" not in LC.APRON_CONTACT_ROLES
        assert "junction" in LC.airside_contact_roles()


# ══════════════════════════════════════════════════════════════════════
# §1.1 — THE PRICE (the crossed surface's cap, not the road's)
# ══════════════════════════════════════════════════════════════════════

class TestTheCrossingIsPricedAsTheSurfaceItCrosses:

    def test_the_conforming_stretch_carries_the_taxiways_cap(self):
        layout, *_ = _crossing_layout()
        _contacts(layout)
        specs = GG.centerline_specs(layout)
        mine = [sp for sp in specs if sp[3][0] == "airside_conform"]
        assert mine, "the conforming stretch produced no centerline spec"
        _pts, seg_caps, is_svc, _k, _r = mine[0]
        assert seg_caps
        assert all(c == pytest.approx(CFG.TAXI_MAX_GRADE) for c in seg_caps)
        assert seg_caps[0] != pytest.approx(CFG.SERVICE_ROAD_MAX_GRADE)
        # §1.2: it stays a SERVICE centerline.  The pins are
        # one-directional, so no airside reader may take this as a spine.
        assert is_svc is True

    def test_the_remainder_still_prices_as_free_road(self):
        """"Away from the contact the road transitions at its own cap"
        (§1.2).  The same centerline is conforming inside the pavement and
        free road outside it — and it is never registered twice."""
        layout, *_ = _crossing_layout()
        _contacts(layout)
        specs = GG.centerline_specs(layout)
        free = [sp for sp in specs if sp[3][0] == "svc"]
        assert free, "the free-road remainder disappeared"
        for (_pts, seg_caps, _svc, _k, _r) in free:
            assert all(c == pytest.approx(CAP) for c in seg_caps)
        # The conforming span is SUBTRACTED from the free source: the two
        # families together are no longer than the original centerline.
        total = sum(LineString(sp[0]).length
                    for sp in specs if sp[2] and sp[3][0] in
                    ("svc", "airside_conform"))
        assert total <= 2 * ROAD_END + 1e-6

    def test_the_class_is_invisible_to_airside_spine_membership(self):
        """AIRSIDE IS KING (§1.2): unlike the 25h apron spine, this class
        moves NEITHER guard — the airside surface must not read a road."""
        cl = GG.Centerline(pts=[(0.0, -20.0), (0.0, 20.0)],
                           seg_caps=[CFG.TAXI_MAX_GRADE],
                           is_service=True, is_airside_conforming=True)
        assert cl.is_service is True
        assert cl.is_apron_spine is False
        apron = GG.GradeShape(role="apron",
                              ring=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
                              keys=["a", "b", "c"])
        assert GG._reads_service_spines(apron) is False


# ══════════════════════════════════════════════════════════════════════
# §1.2 — THE VALUES (pins at entry/exit; ≤ cap descent away)
# ══════════════════════════════════════════════════════════════════════

class TestTheCrossingTakesTheAirsideValues:

    def test_a_pin_is_minted_at_each_entry_and_exit(self):
        layout, *_ = _crossing_layout()
        s = _contacts(layout)
        assert s["pins"] == 2, "one pin per entry/exit of the airside polygon"
        for pin in layout._airside_conform_pins:
            # Every pin names a carrier AIRSIDE ring edge and a foot — the
            # 2026-08-15 recipe shape, so the hold and the final-moment
            # re-derivation cover it without a second mechanism.
            assert set(pin) == {"xy", "edge_a", "edge_b", "t"}
            assert 0.0 <= pin["t"] <= 1.0
            assert abs(abs(pin["xy"][1]) - TAXI_HALF_W) < \
                GS.AIRSIDE_CROSSING_SAMPLE_STEP_M

    def test_the_road_arrives_at_the_taxiways_value(self):
        """The acceptance: no step across the contact."""
        layout, b2i, elev, dem, idx = _crossing_layout()
        _contacts(layout)
        _run(layout, b2i, elev, dem)
        for y in (-ROAD_NEAR_Y, ROAD_NEAR_Y):
            for x in (-ROAD_HALF_W, ROAD_HALF_W):
                got = elev[idx(x, y)]
                assert got == pytest.approx(TAXI_Z, abs=0.01), (
                    f"road contact node ({x}, {y}) at {got:.3f} against a "
                    f"taxiway at {TAXI_Z:.3f} — the owner's cliff")

    def test_the_road_descends_away_at_no_more_than_its_own_cap(self):
        layout, b2i, elev, dem, idx = _crossing_layout()
        _contacts(layout)
        _run(layout, b2i, elev, dem)
        for sign in (-1.0, +1.0):
            ys = [sign * ROAD_NEAR_Y]
            step = (sign * ROAD_END - sign * ROAD_NEAR_Y) / 4.0
            ys += [sign * ROAD_NEAR_Y + step * k for k in (1, 2, 3, 4)]
            for (ya, yb) in zip(ys, ys[1:]):
                za = elev[idx(-ROAD_HALF_W, ya)]
                zb = elev[idx(-ROAD_HALF_W, yb)]
                run = abs(yb - ya)
                assert abs(zb - za) <= CAP * run + 1e-6, (
                    f"road segment y={ya:.1f}->{yb:.1f} grades "
                    f"{abs(zb - za) / run:.4f} against a {CAP:.4f} cap")
            # …and it does get back toward ambient: the pin is a mouth,
            # not a lift of the whole road.
            assert elev[idx(-ROAD_HALF_W, sign * ROAD_END)] < TAXI_Z

    def test_AIRSIDE_IS_KING_the_taxiway_is_byte_identical(self):
        """"no term of the airside solve may reference the road's
        variables" (§1.2) — asserted against a ROAD-LESS control."""
        lay_a, b2i_a, elev_a, dem_a, idx_a = _crossing_layout(with_road=True)
        _contacts(lay_a)
        _run(lay_a, b2i_a, elev_a, dem_a)
        lay_b, b2i_b, elev_b, dem_b, idx_b = _crossing_layout(with_road=False)
        _contacts(lay_b)
        _run(lay_b, b2i_b, elev_b, dem_b)
        for (x, y) in _taxi_ring():
            assert elev_a[idx_a(x, y)] == elev_b[idx_b(x, y)], (
                f"taxiway vertex ({x}, {y}) moved when a road crossed it")
            # Byte-identical to the value it was SOLVED at, too.
            assert elev_a[idx_a(x, y)] == TAXI_Z

    def test_the_pin_reads_the_airside_edge_and_never_writes_it(self):
        """The pin is a LOOKUP: two airside values in, one service value
        out.  Move the taxiway and the pin follows it — the direction the
        law allows — and nothing moves the other way."""
        layout, b2i, elev, dem, idx = _crossing_layout()
        _contacts(layout)
        for (x, y) in _taxi_ring():
            elev[idx(x, y)] = TAXI_Z + 2.0
        _run(layout, b2i, elev, dem)
        assert elev[idx(-ROAD_HALF_W, -ROAD_NEAR_Y)] == \
            pytest.approx(TAXI_Z + 2.0, abs=0.01)
        for (x, y) in _taxi_ring():
            assert elev[idx(x, y)] == pytest.approx(TAXI_Z + 2.0)


# ══════════════════════════════════════════════════════════════════════
# §1.4 — THE FLAG
# ══════════════════════════════════════════════════════════════════════

class TestTheFlag:

    def test_the_flag_is_default_on(self):
        assert CFG.ROAD_AIRSIDE_CROSSING_CONFORM is True

    def test_flag_off_mints_nothing_and_reproduces_the_step(self, monkeypatch):
        monkeypatch.setenv("O4_ROAD_AIRSIDE_CROSSING_CONFORM", "0")
        for m in ("auto_patch.config", "auto_patch.groundside",
                  "auto_patch.grade_graph"):
            importlib.reload(sys.modules[m])
        try:
            import auto_patch.groundside as GS2
            import auto_patch.grade_graph as GG2
            import auto_patch.lateral_contiguity as LC2
            layout, b2i, elev, dem, idx = _crossing_layout()
            s = GS2.road_airside_crossing_contacts(layout, "TEST")
            assert s["on"] is False
            assert s["conforming"] == 0 and s["pins"] == 0
            assert not [sp for sp in GG2.centerline_specs(layout)
                        if sp[3][0] == "airside_conform"]
            # The 25b contact set falls back to the apron exactly.
            assert LC2.airside_contact_roles() == LC2.APRON_CONTACT_ROLES
            # …and THE STEP COMES BACK: the road follows ambient terrain
            # 3 m below the pavement it crosses.
            ANCH.apply_service_road_dem_follow(layout, b2i, elev, dem, CAP)
            got = elev[idx(-ROAD_HALF_W, -ROAD_NEAR_Y)]
            assert abs(TAXI_Z - got) > 1.0, (
                "the flag-off arm must reproduce the owner's cliff")
        finally:
            monkeypatch.delenv("O4_ROAD_AIRSIDE_CROSSING_CONFORM",
                               raising=False)
            for m in ("auto_patch.config", "auto_patch.groundside",
                      "auto_patch.grade_graph"):
                importlib.reload(sys.modules[m])
