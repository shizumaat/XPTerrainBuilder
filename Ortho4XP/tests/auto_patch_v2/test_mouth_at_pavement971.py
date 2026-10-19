"""Twins for issue #971 — A TUNNEL MOUTH STOPS AT THE PAVEMENT (owner
2026-10-19, ``planar/structure_mouth``): a mapped bore's corridor never cuts
a taxiway, nor the pavement over the bore; a ramp entirely within airside
pavement still cuts it.  One synthetic airport per clause; law values read
from the tables, never retyped."""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structure_mouth import mouth_stops
from auto_patch_v2.planar.structure_service import airside_cut_roles
from auto_patch_v2.planar.structures import build_structures


class _FlatDem:
    provenance = {"synthetic": "flat 700 m"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ways():
    """One bore x in [-60, 60] at y = 0, a straight approach each way."""
    t = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    r = {"highway": "secondary", "lanes": "2"}
    return (OsmWay(-101, "big_roads", ((-60.0, 0.0), (60.0, 0.0)), False, t),
            OsmWay(-201, "big_roads", ((60.0, 0.0), (900.0, 0.0)), False, r),
            OsmWay(-202, "big_roads", ((-60.0, 0.0), (-900.0, 0.0)), False, r))


def _airport(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 822.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 822.5), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), _ways(), (), (), pack, _FlatDem(), law.ruleset_key)


def _base_cells():
    return [Cell(0, "runway", "09/27", _rect(-600, 800, 600, 845), (), 3, "D",
                 "airside", "runway", {})]


def _area(cl, ref):
    return sum(Polygon(c.ring, c.holes).area for c in cl.cells
               if c.ref.split("#")[0] == ref)


def test_a_taxiway_over_the_bore_is_never_cut(law):
    """The bore runs under a taxiway whose edge stands 3 m PAST the mapped
    portals (x = ±63): the corridor stood on the taxiway by the old "the
    portal's own pavement" exemption and cut 3 m into it.  Now the mouth
    slides out to where the rim cap clears the taxiway by the gap."""
    tn = law.tables.structures.tunnel
    cells = _base_cells() + [Cell(1, "stub", "twy", _rect(-63, -40, 63, 40), (), None, "D",
                                  "airside", "taxiway", {})]
    cl = Classification(tuple(cells), (), {}, ())
    cl2, tunnels, st = build_structures(_airport(law), cl, law)
    assert len(tunnels) == 2, st.refused
    assert _area(cl2, "twy") == pytest.approx(126.0 * 80.0, abs=1e-6)   # not one m2 cut
    clear = tn.wall_gap_m + tn.wall_gap_m + tn.wall_band_width_m
    for t in tunnels:
        assert abs(t.axis[0][0]) >= 63.0 + clear - 1e-6, t.axis[0]
        assert any("#971" in n and "twy" in n for n in t.notes), t.notes


def test_a_ramp_within_an_apron_still_cuts_it(law):
    """Clause 3 (the owner's exception): an apron the ramp runs INSIDE from
    the mouth for the shortest lawful ramp and more hosts it — the tunnel
    lies within airside pavement and the corridor cuts the apron."""
    cells = _base_cells() + [Cell(1, "apron", "apr", _rect(-400, -60, 400, 60), (), None,
                                  None, "airside", "apron", {})]
    cl = Classification(tuple(cells), (), {}, ())
    cl2, tunnels, st = build_structures(_airport(law), cl, law)
    assert len(tunnels) == 2, st.refused
    assert _area(cl2, "apr") < 800.0 * 120.0 - 100.0
    for t in tunnels:
        assert abs(t.axis[0][0]) == pytest.approx(60.0, abs=0.6)   # the mapped portal
        assert not any("#971" in n for n in t.notes)


def test_road_over_the_bore_stops_the_mouth_the_approach_road_does_not(law):
    """Clause 2 for a groundside road: a road face the bore runs under
    beyond the corridor's cap reach COVERS the tunnel and stops it; the
    approach road's own ribbon, overlapping the bore by its half-width at
    the portal, does not."""
    grid = law.tables.emit.identity.min_distinct_spacing_m
    tn = law.tables.structures.tunnel
    half, rim_off = 3.5, tn.wall_gap_m + tn.wall_band_width_m
    cells = [Cell(0, "service_road", "over", _rect(40, -30, 61, 30), (), None, None,
                  "groundside", "road", {}),
             Cell(1, "service_road", "approach", _rect(57, -3.5, 300, 3.5), (), None, None,
                  "groundside", "road", {})]
    polys = [Polygon(c.ring) for c in cells]
    axis = LineString([(60.0, 0.0), (900.0, 0.0)])
    got = mouth_stops(cells, polys, law, airside_cut_roles(law), axis,
                      [LineString([(-60.0, 0.0), (60.0, 0.0)])], (60.0, 0.0), half, rim_off,
                      (), grid)
    assert [r for _p, r in got] == ["over"]
