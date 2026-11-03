"""THE MISSED-PAVEMENT DETECTOR (owner RULINGS 2026-10-30e, #1686): a
taxi centreline over ground no standing cell holds is named, with the
pack page that covers it when one does."""
from __future__ import annotations

from types import SimpleNamespace as NS

from auto_patch_v2.classify.centreline_gaps import centreline_pavement_gaps


class _Frame:
    def transformers(self):
        return (lambda lo, la: (lo, la)), (lambda x, y: (y / 1e5, x / 1e5))


def _cell(ring, ref="pav0", **ev):
    return NS(ring=tuple(ring), holes=(), ref=ref, evidence=ev)


def _airport(sheets=()):
    nodes = {1: NS(xy=(0.0, 0.0)), 2: NS(xy=(300.0, 0.0)),
             3: NS(xy=(300.0, 200.0))}
    edges = (NS(a=1, b=2, name="A", is_runway=False),
             NS(a=2, b=3, name="B", is_runway=False),
             NS(a=1, b=3, name="", is_runway=True))
    return NS(taxi_nodes=nodes, taxi_edges=edges, frame=_Frame(),
              gap_sheets=tuple(sheets))


_PAVED_A = _cell([(-10, -20), (310, -20), (310, 20), (-10, 20)])


def test_a_fully_paved_network_reads_zero():
    cells = [_PAVED_A, _cell([(280, -10), (320, -10), (320, 210), (280, 210)])]
    r = centreline_pavement_gaps(_airport(), cells)
    assert r.gaps == () and r.gap_m == 0.0 and round(r.taxi_m) == 500
    assert "0 m of 500 m" in r.lines("ZZQQ")[0]


def test_an_unheld_stretch_is_named_with_its_covering_sheet():
    sheet = NS(id="dsf:gapsheet0", description="Polygons/ConcreteLight.pol",
               outer=((280, 10), (320, 10), (320, 220), (280, 220)), holes=())
    r = centreline_pavement_gaps(_airport([sheet]), [_PAVED_A])
    assert len(r.gaps) == 1
    g = r.gaps[0]
    assert abs(g.length_m - 179.0) < 1.5 and g.names == ("B",)
    assert g.sheet_pages == ("Polygons/ConcreteLight.pol",)
    assert abs(g.site[1] - 300.0 / 1e5) < 1e-9
    lines = r.lines("ZZQQ")
    assert "WARNING" in lines[0] and "ConcreteLight.pol" in lines[1]


def test_gap_pieces_and_pad_roads_hold_nothing():
    """A gap piece follows in the last stage and claims no zone ground:
    a centreline over one is still over unpaved ground."""
    cells = [_PAVED_A,
             _cell([(280, -10), (320, -10), (320, 210), (280, 210)], ref="gap:0"),
             _cell([(280, -10), (320, -10), (320, 210), (280, 210)], pad_road=True)]
    r = centreline_pavement_gaps(_airport(), cells)
    assert len(r.gaps) == 1 and r.gaps[0].sheet_pages == ()
    assert "Global pavement" in r.lines("ZZQQ")[1]
    assert r.record()["gaps"][0]["names"] == ["B"]
