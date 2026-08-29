"""Scorer v2 — the CLASS-CHANGE BOUNDARY CUT (owner RULINGS 2026-08-29d).

Spec: ``docs/specs/scorer-v2-class-boundary-spec.md``.  Founding site:
HECA's authored apron back edge, where the package's own layers all stop
and a parking lot begins, and where the global slice minted ONE 401,100 m²
face across the wall.

What can be wrong here is the DISCRIMINATOR, not the geometry: cut too
eagerly and the round re-runs the §H3 severance failure (IoU 0.8221,
+61/+37/+435 census, shipped OFF); cut too rarely and the owner's wall
stays buried.  So these twins pin BOTH directions, and they pin the three
predicates the spec REFUSES as triggers.
"""
from types import SimpleNamespace

# Import through the package entry point FIRST: auto_patch has a
# documented ``junction_repair`` <-> ``elevation`` import cycle and
# reaching a leaf module first raises (auto_patch/CLAUDE.md, "Gotchas").
import auto_patch.pipeline  # noqa: F401
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from auto_patch.pavement.global_slice import (
    SliceFace,
    split_faces_at_class_change,
)
from auto_patch.pavement_classification import authored_class_regions


def _box(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _face(poly, kind="apron", ids=(0,)):
    return SliceFace(polygon=poly, centerline_ids=list(ids), kind=kind)


# ── the discriminator, both directions ───────────────────────────────

class TestTheCutDiscriminator:

    #: an airside-class region (reaches the runway) and a groundside-class
    #: one (a lot), with the authored edge at x = 100.
    AIR = _box(0, 0, 100, 100)
    GND = _box(140, 0, 200, 100)

    def test_a_face_carrying_both_classes_is_cut_at_the_authored_edge(self):
        face = _face(_box(0, 0, 200, 100))
        out, stats = split_faces_at_class_change(
            [face], self.AIR, self.GND)
        assert stats["faces_cut"] == 1
        sides = {f.class_side: f.polygon.area for f in out}
        assert set(sides) == {"airside", "groundside"}
        assert sides["airside"] == pytest.approx(100 * 100)
        assert sides["groundside"] == pytest.approx(100 * 100)
        # the cut is AT the authored edge, not somewhere convenient
        air = [f for f in out if f.class_side == "airside"][0]
        assert air.polygon.bounds[2] == pytest.approx(100.0)

    def test_a_face_on_ONE_class_is_returned_untouched_and_unlabelled(self):
        """The byte-identical case, and it is the overwhelming majority.
        One class — or none — is not a disagreement."""
        face = _face(_box(0, 0, 90, 90))
        out, stats = split_faces_at_class_change([face], self.AIR, self.GND)
        assert stats["faces_cut"] == 0
        assert out == [face] and out[0].class_side == ""

    def test_a_face_on_NEITHER_class_never_cuts(self):
        """Ground paint carries no class: 187 emitted rings span more than
        one paint page, and one page covers both sides of the founding
        edge.  Absence of authored evidence is never evidence."""
        face = _face(_box(105, 0, 135, 100))       # the unlabelled gap
        out, stats = split_faces_at_class_change([face], self.AIR, self.GND)
        assert stats["faces_cut"] == 0 and out[0].class_side == ""

    def test_no_groundside_evidence_anywhere_makes_the_law_inert(self):
        face = _face(_box(0, 0, 200, 100))
        out, stats = split_faces_at_class_change([face], self.AIR, None)
        assert out is [face] or out == [face]
        assert stats["faces_cut"] == 0 and stats["reason"]

    def test_a_grazing_class_touch_under_the_floor_does_not_cut(self):
        """Both classes must be present ABOVE the piece floor.  A 1 m²
        clip of the far class is a topology artefact, not a wall."""
        face = _face(_box(0, 0, 141, 100).intersection(
            unary_union([_box(0, 0, 100, 100), _box(140, 0, 141, 1)])))
        out, stats = split_faces_at_class_change(
            [face], self.AIR, self.GND, min_piece_m2=25.0)
        assert stats["faces_cut"] == 0


# ── the two refinements, both measured ───────────────────────────────

class TestPocketsAndFloor:

    AIR = _box(0, 0, 200, 200).difference(_box(90, 90, 110, 110))
    GND = _box(240, 0, 300, 200)

    def test_an_authored_layer_POCKET_stays_with_the_airside_side(self):
        """A hole in the authored layer surrounded by airside-class
        pavement is a texture gap inside the apron, not the far side of a
        wall (HECA: 71 m² across the four cut faces)."""
        face = _face(_box(0, 0, 300, 200))
        out, stats = split_faces_at_class_change([face], self.AIR, self.GND)
        assert stats["faces_cut"] == 1
        assert stats["pockets_kept"] >= 1
        air = unary_union([f.polygon for f in out
                           if f.class_side == "airside"])
        assert air.covers(_box(95, 95, 105, 105)), (
            "the pocket must stay airside — it is enclosed by airside-"
            "class pavement and reaches no authored boundary")
        gnd = unary_union([f.polygon for f in out
                           if f.class_side == "groundside"])
        assert not gnd.intersects(_box(95, 95, 105, 105))

    def test_nothing_is_deleted_by_the_cut(self):
        """Spec §3: re-roled, never removed.  Every square metre that
        leaves the airside side arrives on the groundside side."""
        face = _face(_box(0, 0, 300, 200))
        out, _ = split_faces_at_class_change([face], self.AIR, self.GND)
        assert unary_union([f.polygon for f in out]).area == pytest.approx(
            face.polygon.area, rel=1e-9)


# ── what the groundside side carries ─────────────────────────────────

def test_the_groundside_side_carries_no_centerline_and_no_axis():
    """A taxi route's territory is AIRSIDE evidence.  Carrying it across
    the authored boundary is the inheritance this cut exists to stop."""
    air, gnd = _box(0, 0, 100, 100), _box(140, 0, 200, 100)
    face = SliceFace(polygon=_box(0, 0, 200, 100), centerline_ids=[3, 7],
                     kind="corridor", axis="AXIS")
    out, _ = split_faces_at_class_change([face], air, gnd)
    g = [f for f in out if f.class_side == "groundside"][0]
    a = [f for f in out if f.class_side == "airside"][0]
    assert g.centerline_ids == [] and g.axis is None
    assert a.centerline_ids == [3, 7] and a.axis == "AXIS"


# ── the authored class map ───────────────────────────────────────────

class TestAuthoredClassRegions:
    """The class comes from the AUTHORED layer's own connectivity — the
    standing 2026-06-09 law stated over apt.dat row-110 instead of over
    the merged union, where a pack's ground paint makes it inert."""

    def _layout(self, polys, runway):
        return SimpleNamespace(apt_only_pavement_polys=list(polys),
                               runway_union=runway, shapes=[])

    def test_a_row110_component_reaching_the_runway_is_airside_class(self):
        rwy = _box(-50, 0, 0, 40)
        lay = self._layout([_box(0, 0, 100, 100)], rwy)
        air, gnd = authored_class_regions(lay)
        assert air is not None and air.covers(_box(10, 10, 20, 20))
        assert gnd is None or gnd.is_empty

    def test_a_row110_component_that_does_not_reach_is_groundside_class(self):
        rwy = _box(-50, 0, 0, 40)
        lay = self._layout([_box(0, 0, 100, 100), _box(200, 0, 260, 60)], rwy)
        air, gnd = authored_class_regions(lay)
        assert gnd is not None and gnd.covers(_box(210, 10, 220, 20))
        assert not air.covers(_box(210, 10, 220, 20))

    def test_the_runway_itself_is_airside_class(self):
        """Packs draw runways as row-100, so no row-110 ring covers them."""
        rwy = _box(-50, 0, 0, 40)
        lay = self._layout([_box(0, 0, 100, 100)], rwy)
        air, _ = authored_class_regions(lay)
        assert air.covers(_box(-40, 10, -30, 20))

    def test_no_runway_union_means_no_class_evidence_at_all(self):
        lay = self._layout([_box(0, 0, 100, 100)], None)
        assert authored_class_regions(lay) == (None, None)

    def test_the_answer_is_memoized_on_the_layout(self):
        lay = self._layout([_box(0, 0, 100, 100)], _box(-50, 0, 0, 40))
        first = authored_class_regions(lay)
        assert authored_class_regions(lay) is first
        assert lay._authored_class_regions is first


# ── the REFUSED predicates (the lane's refutation record) ────────────

class TestTheRefusedPredicatesAreNotTriggers:
    """Spec §2.  Each of these fired far too wide when measured, and the
    numbers are the reason they are refused — a later round must not
    quietly reintroduce one as "the obvious test"."""

    def test_a_bare_source_union_gap_is_not_a_trigger(self):
        """HECA's real source union is ONE component; the 45.75 m gap is
        visible only in the apt.dat-only layer.  Two authored components
        with NO class disagreement (both reach the runway) must not cut."""
        rwy = _box(-50, 0, 0, 40)
        lay = SimpleNamespace(
            apt_only_pavement_polys=[_box(0, 0, 100, 100),
                                     _box(-50, 60, 0, 100)],
            runway_union=rwy, shapes=[])
        air, gnd = authored_class_regions(lay)
        assert gnd is None or gnd.is_empty, (
            "both components touch the runway: same class, no cut")
        face = _face(_box(-60, 0, 200, 100))
        assert split_faces_at_class_change([face], air, gnd)[1][
            "faces_cut"] == 0

    def test_depth_beyond_the_authored_layer_is_not_a_trigger(self):
        """38 of 59 HECA aprons carry an off-row-110 piece deeper than
        20 m; a face that merely extends a long way past the authored
        pavement, with no groundside-class evidence out there, is not a
        class change."""
        air = _box(0, 0, 100, 100)
        face = _face(_box(0, 0, 400, 100))          # 300 m of paint-only
        assert split_faces_at_class_change([face], air, None)[1][
            "faces_cut"] == 0
        assert split_faces_at_class_change(
            [face], air, _box(1000, 0, 1100, 100))[1]["faces_cut"] == 0
