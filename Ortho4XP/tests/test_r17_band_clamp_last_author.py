"""R17-1 — THE CLAMP IS THE LAST AUTHOR, AND THERE IS ONE BAND.

(b) The reach-band clamp runs at the END of ``build_airport_pavement``,
after every emitter and both final projections, on the EMITTED
altitudes; a value written after it cannot survive to emit unseen — the
seal names it.

(c) ONE BAND CONSTRUCTION (owner ruling, RULINGS 2026-08-11b): the band
is built once per solve and PUBLISHED; the writeback clamp, this final
clamp and the band-excess report read THAT object.  Measured at VHHH
before this round: the clamp stamped a junction at −12.14 m against a
carried band of [−12.93, −12.14] where the solve had solved 7.01, while
the report REBUILT the band and called the same node 17.23 m below ITS
floor — all 245 "material" rows were that disagreement.

Headless: hand-built layouts, an explicit band closure, no DEM, no
build.
"""

from __future__ import annotations

import sys
from pathlib import Path

from shapely.geometry import Polygon

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from auto_patch.elevation_per_surface import building_feasibility as BF  # noqa: E402
from auto_patch.elevation_per_surface import solver_primitives as SP  # noqa: E402
from auto_patch.layout import BuiltShape, ROLE_JUNCTION, ROLE_RUNWAY  # noqa: E402


class _Layout:
    def __init__(self, shapes):
        self.shapes = shapes
        self.band_clamp_findings = []


def _square(x0=0.0, y0=0.0, side=10.0):
    return Polygon([(x0, y0), (x0 + side, y0), (x0 + side, y0 + side),
                    (x0, y0 + side), (x0, y0)])


def _shape(role=ROLE_JUNCTION, alts=(20.0, 20.0, 20.0, 20.0)):
    s = BuiltShape(role=role, polygon=_square())
    s.node_altitudes = list(alts)
    return s


def _band(floor=4.6, ceiling=9.4):
    return lambda x, y: (floor, ceiling)


class TestOneBandConstruction:
    def test_the_record_is_the_object_every_consumer_reads(self):
        layout = _Layout([])
        band = _band()
        assert BF.band_of_record(layout) is None
        assert BF.publish_band_of_record(layout, band) is band
        assert BF.band_of_record(layout) is band

    def test_the_report_consumes_the_record_and_builds_nothing(
            self, monkeypatch):
        """``route_band_violations`` must not construct a second band when
        the solve published one — that construction IS the defect."""
        from auto_patch import grade_graph_validate as GGV

        def _refuse(*_a, **_k):                            # pragma: no cover
            raise AssertionError("a SECOND band construction")

        monkeypatch.setattr(BF, "reach_band_unified", _refuse)
        s = _shape(alts=(20.0, 20.0, 20.0, 20.0))
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        rows = GGV.route_band_violations(layout)
        # 20 m against a [4.6, 9.4] band: the report SEES the excess and
        # it read the record to see it.
        assert rows and rows[0][1] == "ceil"

    def test_a_layout_that_never_solved_builds_exactly_once(
            self, monkeypatch):
        """No record ⇒ the caller's own construction is the FIRST one,
        not a second — and it becomes the record, so a later reader
        cannot mint another."""
        from auto_patch import grade_graph_validate as GGV
        from auto_patch import grade_graph as GG

        built = []

        def _build(layout, G):
            built.append(G)
            return _band()

        monkeypatch.setattr(BF, "reach_band_unified", _build)
        monkeypatch.setattr(SP, "_build_node_list",
                            lambda layout: ([(0.0, 0.0)], {}))
        monkeypatch.setattr(GG, "build_unified_graph",
                            lambda layout, b2i: object())
        layout = _Layout([_shape()])
        GGV.route_band_violations(layout)
        GGV.route_band_violations(layout)
        assert len(built) == 1
        assert BF.band_of_record(layout) is not None


class TestSealClampsTheEmittedSurface:
    def test_an_out_of_band_value_is_clamped_at_the_seal(self):
        s = _shape(alts=(20.0, 20.0, 20.0, 20.0))
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        assert SP.seal_pavement_to_band(layout, "TEST") == 1
        assert s.node_altitudes == [9.4] * 4
        assert layout.band_clamp_findings
        assert {f[4] for f in layout.band_clamp_findings} == {"ceil"}

    def test_a_value_inside_its_band_is_untouched(self):
        s = _shape(alts=(7.0, 7.0, 7.0, 7.0))
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        assert SP.seal_pavement_to_band(layout, "TEST") == 0
        assert s.node_altitudes == [7.0] * 4
        assert layout.band_clamp_findings == []

    def test_the_runway_datum_is_never_clamped(self):
        s = _shape(role=ROLE_RUNWAY, alts=(20.0, 20.0, 20.0, 20.0))
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        assert SP.seal_pavement_to_band(layout, "TEST") == 0
        assert s.node_altitudes == [20.0] * 4

    def test_no_band_of_record_clamps_nothing(self):
        s = _shape(alts=(20.0, 20.0, 20.0, 20.0))
        layout = _Layout([s])
        assert SP.seal_pavement_to_band(layout, "TEST") == 0
        assert s.node_altitudes == [20.0] * 4

    def test_the_plane_form_survives_the_clamp(self):
        s = BuiltShape(role=ROLE_JUNCTION, polygon=_square())
        s.altitude_high = 20.0
        s.altitude_low = 19.0
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        assert SP.seal_pavement_to_band(layout, "TEST") == 1
        assert s.node_altitudes is None          # still a plane rect
        assert s.altitude_high == 9.4 and s.altitude_low == 9.4


class TestPostClampMutationCannotSurvive:
    def test_the_seal_names_a_post_clamp_author(self):
        s = _shape(alts=(7.0, 7.0, 7.0, 7.0))
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        SP.seal_pavement_to_band(layout, "TEST")
        assert SP.verify_band_seal(layout) == []
        # A post-clamp pass re-authors the surface …
        s.node_altitudes = [7.0, 7.0, 7.0, -12.1]
        moved = SP.verify_band_seal(layout)
        assert moved and moved[0][1] == ROLE_JUNCTION
        assert moved[0][2] > 19.0

    def test_a_sub_materiality_move_is_not_an_author(self):
        s = _shape(alts=(7.0, 7.0, 7.0, 7.0))
        layout = _Layout([s])
        BF.publish_band_of_record(layout, _band())
        SP.seal_pavement_to_band(layout, "TEST")
        s.node_altitudes = [7.0, 7.0, 7.0, 7.005]
        assert SP.verify_band_seal(layout) == []

    def test_an_unsealed_layout_reports_none_not_clean(self):
        assert SP.verify_band_seal(_Layout([_shape()])) is None


class TestTheSealIsTheLastCallInThePipeline:
    def test_no_elevation_author_runs_after_the_seal(self):
        """Structural, not "currently last by luck": nothing between the
        seal call and the pipeline's return may write an altitude."""
        import inspect
        from auto_patch import pipeline as PIPE

        source = inspect.getsource(PIPE.build_airport_pavement)
        assert "seal_pavement_to_band as _seal_band" in source
        tail = source.split("_seal_band(layout, icao)", 1)[1]
        # The tail is reports and bookkeeping only.  These are the
        # pipeline's own elevation authors; none may appear after it.
        for author in ("_late_fgp(", "_reclamp_spines(", "_writeback(",
                       "final_grade_projection(", "_strip_reconcile_passes(",
                       "emit_adjacent_ground_bands(", "emit_gap_fill_spines(",
                       "relevel_pads_to_host_pavement("):
            assert author not in tail, author
