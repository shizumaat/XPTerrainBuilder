"""ROAD ↔ AIRSIDE CROSSING CONFORMANCE — the §2 twin, Amendment 1 frame.

Spec: ``docs/specs/road-airside-crossing-conformance-spec.md`` + Amendment 1
(Fable, 2026-08-26 late).  Owner, verbatim: *service roads crossing
taxiways, like here: 30.104671, 31.3973462, have to grade smoothly to match
the apron elevation, not leave a cliff.*  AIRSIDE IS KING: the road takes
the airside value; the airside surface feels ZERO pull.

WHAT THIS LANE MEASURED BEFORE THE AMENDMENT, and what each clause of it
therefore has a twin for:

* **FRAME** — the carve separates a road ring from the pavement it meets by
  ``GROUNDSIDE_CLEARANCE_M`` and fills the gap with an ``adjacent_ground``
  strip, so a contiguous-run test over the SETTLED arrangement finds no
  paved run at the mouth.  Attempts 1-2 asked there and the owner's site
  was invisible through two HECA builds.  Detection is now asked in the
  SOURCE frame.
* **SCOPE** — "cross-section reaches airside" produced 285 stretches /
  32.1 km at HECA.  A crossing is now a TRAVERSAL: enter and exit.
* **ADOPTION** — registering the stretches as centerlines and seating
  their mouths as solver anchors put terms in the ONE solve, and the one
  solve is global: +124 (attempt 1) and +78 (attempt 2) airside rows
  against a matched flag-off arm, 52 % of them more than 25 m from any
  road and 20 % more than 100 m.  Values are now ADOPTED post-solve onto
  ROAD-FAMILY nodes only, and a vertex any non-road shape also carries is
  FROZEN — so the airside census cannot move.

Hand-computed geometry, no build, no network, no solver.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters (auto_patch/CLAUDE.md, "Import cycle").
import auto_patch.pipeline                                    # noqa: E402,F401
from auto_patch import config as CFG                          # noqa: E402
from auto_patch import grade_graph as GG                      # noqa: E402
from auto_patch import groundside as GS                       # noqa: E402
from auto_patch import lateral_contiguity as LC               # noqa: E402
from auto_patch.enclaves import ENCLAVE_AIRSIDE_ROLES         # noqa: E402
from auto_patch.layout import BuiltShape                      # noqa: E402

CAP = CFG.SERVICE_ROAD_MAX_GRADE

AMBIENT = 100.0                 # what the road solved to on its own
TAXI_Z = AMBIENT + 3.0          # "+3 m over ambient" (spec §2)
TAXI_HALF_W = 11.5              # a code-C taxiway's half width
TAXI_HALF_L = 60.0
ROAD_HALF_W = 3.0
ROAD_END = 60.0
# THE CARVE'S OWN GAP: the road body stands clear of the pavement it meets
# by more than the 2026-08-15 mouth tolerance, which is why that law does
# not reach the owner's site — and why the frame ruling exists.
GAP_M = 1.6
ROAD_NEAR_Y = TAXI_HALF_W + GAP_M         # 13.1


class _Layout:
    def __init__(self, shapes, service_lines=(), corridor_lines=(),
                 source_union=None):
        self.icao = "TEST"
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)
        self.canonical_points = None
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = list(corridor_lines)
        self._slice_service_subsegments = list(service_lines)
        self._apron_spine_subsegments = []
        self.source_pavement_union = source_union


def _taxi_ring():
    return [(-TAXI_HALF_L, -TAXI_HALF_W), (TAXI_HALF_L, -TAXI_HALF_W),
            (TAXI_HALF_L, TAXI_HALF_W), (-TAXI_HALF_L, TAXI_HALF_W)]


def _road_ring(y0, y1):
    ys = [y0]
    step = (y1 - y0) / 4.0
    ys += [y0 + step * k for k in (1, 2, 3)]
    ys.append(y1)
    return ([(-ROAD_HALF_W, y) for y in ys]
            + [(ROAD_HALF_W, y) for y in reversed(ys)])


def _crossing_layout(with_road: bool = True, corridor: bool = False,
                     alongside: bool = False):
    """The spec's §2 geometry.

    The taxiway is ALREADY SOLVED at ``TAXI_Z``; the road bodies stop
    ``GAP_M`` clear of it on both sides (the settled arrangement the carve
    leaves) and the road CENTERLINE runs straight across.  The SOURCE
    pavement union has no such gap — that is the frame the detector reads.

    ``alongside=True`` moves the road so its centerline never enters the
    taxiway: the 25b/25h case, which must produce nothing here.
    """
    taxi = BuiltShape(polygon=Polygon(_taxi_ring()), role="primary_parallel")
    taxi.node_altitudes = [TAXI_Z] * len(_taxi_ring())
    shapes = [taxi]
    lines = []
    if with_road:
        if alongside:
            off = TAXI_HALF_W + GAP_M + ROAD_HALF_W
            body = [(x, off - ROAD_HALF_W) for x in
                    (-40.0, -20.0, 0.0, 20.0, 40.0)]
            body += [(x, off + ROAD_HALF_W) for x in
                     (40.0, 20.0, 0.0, -20.0, -40.0)]
            road = BuiltShape(polygon=Polygon(body), role="service_road")
            road.node_altitudes = [AMBIENT] * len(body)
            road.lateral_cap = None
            shapes.append(road)
            lines = [LineString([(-40.0, off), (40.0, off)])]
        else:
            for (y0, y1) in ((-ROAD_END, -ROAD_NEAR_Y),
                             (ROAD_NEAR_Y, ROAD_END)):
                ring = _road_ring(y0, y1)
                sh = BuiltShape(polygon=Polygon(ring), role="service_road")
                sh.node_altitudes = [AMBIENT] * len(ring)
                sh.lateral_cap = None
                shapes.append(sh)
            lines = [LineString([(0.0, -ROAD_END), (0.0, ROAD_END)])]
    src = unary_union([s.polygon for s in shapes]
                      + ([Polygon([(-ROAD_HALF_W, -ROAD_NEAR_Y),
                                   (ROAD_HALF_W, -ROAD_NEAR_Y),
                                   (ROAD_HALF_W, ROAD_NEAR_Y),
                                   (-ROAD_HALF_W, ROAD_NEAR_Y)])]
                         if (with_road and not alongside) else []))
    return (_Layout(shapes, (), lines, src) if corridor
            else _Layout(shapes, lines, (), src))


def _contacts(layout):
    return GS.road_airside_crossing_contacts(layout, "TEST")


def _adopt(layout):
    return GS.adopt_road_airside_crossing_values(layout, "TEST")


def _road_shapes(layout):
    return [s for s in layout.shapes if s.role == "service_road"]


def _alt_at(layout, x, y):
    for s in layout.shapes:
        ring = list(s.polygon.exterior.coords)[:-1]
        alts = list(s.node_altitudes or [])
        if len(alts) == len(ring) + 1:
            alts = alts[:-1]
        for (px, py), a in zip(ring, alts):
            if abs(px - x) < 1e-6 and abs(py - y) < 1e-6:
                return a
    return None


# ══════════════════════════════════════════════════════════════════════
# Amendment 1 §1 — THE FRAME IS THE SOURCE PAVEMENT
# ══════════════════════════════════════════════════════════════════════

class TestTheFrameIsTheSourcePavement:

    def test_the_crossing_is_seen_across_the_carve_gap(self):
        """The road body stops GAP_M clear of the taxiway — the settled
        arrangement the carve leaves — and the crossing is STILL found,
        because the question is asked of the SOURCE pavement."""
        layout = _crossing_layout()
        s = _contacts(layout)
        assert s["crossings"] == 1, (
            "the crossing was invisible across the carve gap — the "
            "settled-arrangement mis-frame of attempts 1 and 2")
        rec = layout._airside_crossings[0]
        assert rec["length_m"] == pytest.approx(2 * TAXI_HALF_W, abs=6.0)

    def test_the_footprint_reopens_only_the_carve_annulus(self):
        """The source footprint is the settled rings reopened by the
        carve's OWN clearance and clipped back to source pavement — it
        may not invent airside where no source pavement is."""
        layout = _crossing_layout()
        foot = GS.airside_source_footprint(layout)
        assert foot is not None
        assert foot.covers(layout.source_pavement_union.intersection(
            Polygon(_taxi_ring())))
        # Nothing outside the source pavement joined it.
        assert foot.difference(
            layout.source_pavement_union.buffer(1e-9)).area \
            == pytest.approx(0.0, abs=1e-6)


# ══════════════════════════════════════════════════════════════════════
# Amendment 1 §2 — CROSSINGS ONLY
# ══════════════════════════════════════════════════════════════════════

class TestScopeIsCrossingsOnly:

    def test_a_road_ALONGSIDE_airside_is_not_a_crossing(self):
        """"A road running ALONGSIDE airside pavement without its
        centerline entering it stays under the existing 25b/25h law
        untouched."  This is the clause that kills the 32.1 km
        population attempt 2 produced."""
        layout = _crossing_layout(alongside=True)
        assert _contacts(layout)["crossings"] == 0

    def test_a_centerline_wholly_inside_airside_is_not_a_crossing(self):
        """That is the 25h apron-spine case; its own law owns it."""
        layout = _crossing_layout()
        layout._slice_service_subsegments = [
            LineString([(-40.0, 0.0), (40.0, 0.0)])]
        assert _contacts(layout)["crossings"] == 0

    def test_a_road_that_never_meets_airside_produces_nothing(self):
        layout = _crossing_layout()
        layout.shapes = [s for s in layout.shapes
                         if s.role != "primary_parallel"]
        assert _contacts(layout)["crossings"] == 0

    def test_the_register_is_the_canonical_airside_family(self):
        """"read them from one existing register, never a hand list".  A
        ``graded_strip`` is the road's OWN grading product at the road's
        own level — adopting from one pins the road at exactly the value
        the law replaces (the 2026-08-15 carrier adjudication)."""
        assert "graded_strip" not in ENCLAVE_AIRSIDE_ROLES
        assert "building" not in ENCLAVE_AIRSIDE_ROLES
        assert {"apron", "junction", "primary_parallel", "stub",
                "runway"} <= set(ENCLAVE_AIRSIDE_ROLES)
        assert ENCLAVE_AIRSIDE_ROLES <= LC.airside_contact_roles()
        assert "junction" not in LC.APRON_CONTACT_ROLES

    def test_a_corridor_sourced_crossing_is_recognised_too(self):
        """``centerline_specs`` has TWO free-road sources; at HECA the
        roads arrive as corridor COURSES.  Reading only the sliced set
        was attempt 1's measured miss."""
        layout = _crossing_layout(corridor=True)
        assert not layout._slice_service_subsegments
        assert _contacts(layout)["crossings"] == 1


# ══════════════════════════════════════════════════════════════════════
# Amendment 1 §3 — ADOPTION, NEVER CONSTRAINT
# ══════════════════════════════════════════════════════════════════════

class TestNothingEntersTheGradeGraph:

    def test_the_centerline_set_is_UNCHANGED(self):
        """The measured cause of +124/+78 airside rows: registering the
        stretches as centerlines changed ``ctx.centerlines``, and the one
        solve is global.  The detector must leave that set alone."""
        layout = _crossing_layout()
        before = GG.centerline_specs(layout)
        _contacts(layout)
        after = GG.centerline_specs(layout)
        assert [(sp[1], sp[2], sp[3][0]) for sp in before] == \
               [(sp[1], sp[2], sp[3][0]) for sp in after]
        assert not [sp for sp in after if sp[3][0] == "airside_conform"]

    def test_no_solver_anchor_or_pin_is_published(self):
        layout = _crossing_layout()
        _contacts(layout)
        for attr in ("_airside_conform_pins", "_airside_conform_subsegments",
                     "_airside_conform_caps"):
            assert not getattr(layout, attr, None)


class TestTheRoadAdoptsTheAirsideValue:

    def test_the_road_arrives_at_the_taxiways_value(self):
        """The acceptance: no step across the contact."""
        layout = _crossing_layout()
        _contacts(layout)
        out = _adopt(layout)
        assert out["mouths"] == 2 and out["seeded"] >= 2
        for y in (-ROAD_NEAR_Y, ROAD_NEAR_Y):
            for x in (-ROAD_HALF_W, ROAD_HALF_W):
                got = _alt_at(layout, x, y)
                assert got == pytest.approx(TAXI_Z, abs=0.01), (
                    f"road contact node ({x}, {y}) at {got} against a "
                    f"taxiway at {TAXI_Z} — the owner's cliff")

    def test_the_road_descends_away_at_no_more_than_its_own_cap(self):
        layout = _crossing_layout()
        _contacts(layout)
        _adopt(layout)
        for s in _road_shapes(layout):
            ring = list(s.polygon.exterior.coords)[:-1]
            alts = list(s.node_altitudes)
            if len(alts) == len(ring) + 1:
                alts = alts[:-1]
            for ((xa, ya), za) in zip(ring, alts):
                for ((xb, yb), zb) in zip(ring, alts):
                    d = ((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5
                    if d < 1e-6:
                        continue
                    assert abs(za - zb) <= CAP * d + 1e-6, (
                        f"road pair {d:.1f} m apart grades "
                        f"{abs(za - zb) / d:.4f} against a {CAP} cap")
        # …and the far end is on its way back to ambient: the mouth is a
        # mouth, not a lift of the whole road.
        assert _alt_at(layout, -ROAD_HALF_W, -ROAD_END) < TAXI_Z

    def test_AIRSIDE_IS_KING_the_taxiway_is_BYTE_IDENTICAL(self):
        """The hard gate of Amendment 1 §3, at unit level: the pass may
        not write one airside value."""
        layout = _crossing_layout()
        taxi = [s for s in layout.shapes if s.role == "primary_parallel"][0]
        before = list(taxi.node_altitudes)
        before_ring = list(taxi.polygon.exterior.coords)
        _contacts(layout)
        _adopt(layout)
        assert list(taxi.node_altitudes) == before
        assert list(taxi.polygon.exterior.coords) == before_ring

    def test_a_vertex_a_NON_ROAD_shape_also_carries_is_FROZEN(self):
        """The construction that makes the gate structural: a welded
        vertex keeps its solved value and anchors the road, and the pass
        never writes it."""
        layout = _crossing_layout()
        weld = (-ROAD_HALF_W, -ROAD_NEAR_Y)
        pad_ring = [weld, (weld[0] - 8.0, weld[1]),
                    (weld[0] - 8.0, weld[1] - 8.0), (weld[0], weld[1] - 8.0)]
        pad = BuiltShape(polygon=Polygon(pad_ring), role="building")
        pad.node_altitudes = [AMBIENT] * len(pad_ring)
        layout.shapes.append(pad)
        _contacts(layout)
        out = _adopt(layout)
        assert out["frozen"] >= 1
        assert _alt_at(layout, *weld) == pytest.approx(AMBIENT), (
            "a vertex a building pad also carries was written — the pass "
            "is no longer road-family-only")

    def test_the_adoption_reads_the_SETTLED_airside_surface(self):
        """A pure lookup: move the taxiway and the road follows it — the
        direction the law allows — and nothing moves the other way."""
        layout = _crossing_layout()
        taxi = [s for s in layout.shapes if s.role == "primary_parallel"][0]
        taxi.node_altitudes = [TAXI_Z + 2.0] * len(taxi.node_altitudes)
        _contacts(layout)
        _adopt(layout)
        assert _alt_at(layout, -ROAD_HALF_W, -ROAD_NEAR_Y) == \
            pytest.approx(TAXI_Z + 2.0, abs=0.01)
        assert all(a == pytest.approx(TAXI_Z + 2.0)
                   for a in taxi.node_altitudes)


# ══════════════════════════════════════════════════════════════════════
# §1.4 — THE FLAG
# ══════════════════════════════════════════════════════════════════════

class TestTheFlag:

    def test_the_flag_is_default_on(self):
        assert CFG.ROAD_AIRSIDE_CROSSING_CONFORM is True

    def test_flag_off_mints_nothing_and_reproduces_the_step(self, monkeypatch):
        monkeypatch.setenv("O4_ROAD_AIRSIDE_CROSSING_CONFORM", "0")
        for m in ("auto_patch.config", "auto_patch.groundside"):
            importlib.reload(sys.modules[m])
        try:
            import auto_patch.groundside as GS2
            import auto_patch.lateral_contiguity as LC2
            layout = _crossing_layout()
            s = GS2.road_airside_crossing_contacts(layout, "TEST")
            assert s["on"] is False and s["crossings"] == 0
            out = GS2.adopt_road_airside_crossing_values(layout, "TEST")
            assert out["moved"] == 0 and out["mouths"] == 0
            assert LC2.airside_contact_roles() == LC2.APRON_CONTACT_ROLES
            # THE STEP COMES BACK.
            got = _alt_at(layout, -ROAD_HALF_W, -ROAD_NEAR_Y)
            assert abs(TAXI_Z - got) > 1.0, (
                "the flag-off arm must reproduce the owner's cliff")
        finally:
            monkeypatch.delenv("O4_ROAD_AIRSIDE_CROSSING_CONFORM",
                               raising=False)
            for m in ("auto_patch.config", "auto_patch.groundside"):
                importlib.reload(sys.modules[m])
