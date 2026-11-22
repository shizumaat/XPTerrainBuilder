"""Twins of #1957: the §60 SURFACE pages are the pavement when the
pavement sources do not carry the taxi network (``airport/network_pages``)."""
from __future__ import annotations

from auto_patch_v2.airport import network_pages as NP
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.airport import Pavement, Surface, TaxiEdge, TaxiNode


def _rect(pid, x0, y0, x1, y1, surface=Surface.CONCRETE, desc=""):
    return Pavement(pid, surface, ((x0, y0), (x1, y0), (x1, y1), (x0, y1)), (), desc)


def _network():
    """A 1,000 m taxiway along y = 0 and a 200 m runway edge (not counted)."""
    nodes = {1: TaxiNode(1, (0.0, 0.0), "both"), 2: TaxiNode(2, (1000.0, 0.0), "both"),
             3: TaxiNode(3, (0.0, 500.0), "both"), 4: TaxiNode(4, (200.0, 500.0), "both")}
    edges = (TaxiEdge(1, 2, "A", False, False, "D"),
             TaxiEdge(3, 4, "09/27", False, True, None))
    return nodes, edges


def test_share_counts_painting_pavement_and_skips_runway_edges():
    nodes, edges = _network()
    pav = (_rect("pav0", 0, -10, 300, 10),
           _rect("pav1", 300, -10, 600, 10, Surface.TRANSPARENT))
    assert abs(NP._network_share(pav, nodes, edges) - 0.3) < 1e-9
    assert NP._network_share((), nodes, edges) == 0.0
    assert NP._network_share(pav, {}, ()) is None


def test_pages_become_sources_when_the_network_is_off_the_sources():
    nodes, edges = _network()
    pav = (_rect("pav0", 0, -10, 100, 10),)                       # 10 %
    pages = (_rect("dsf:gapsheet3", 0, -20, 1000, 20, desc="Material/a.pol"),
             _rect("dsf:gapsheet4", 0, 30, 50, 60, desc="Material/b.pol"))
    dec, taken = NP.decide(pav, pages, nodes, edges, 0.5)
    assert dec.promoted and dec.pages == 2
    assert [p.id for p in taken] == ["dsf:netpage0", "dsf:netpage1"]
    assert [p.description for p in taken] == ["Material/a.pol", "Material/b.pol"]
    assert abs(dec.pages_m2 - (40_000 + 1_500)) < 1e-6
    assert "taken as pavement sources" in dec.line("TEST")


def test_pages_stay_sheets_when_the_sources_carry_the_network():
    nodes, edges = _network()
    pav = (_rect("pav0", 0, -10, 1000, 10),)
    pages = (_rect("dsf:gapsheet0", 0, -20, 1000, 20),)
    dec, taken = NP.decide(pav, pages, nodes, edges, 0.5)
    assert not dec.promoted and taken == ()
    assert "stay gap sheets" in dec.line("TEST")
    # the key at 0 is off; no network, no witness, no line
    assert NP.decide((), pages, nodes, edges, 0.0)[1] == ()
    dec, taken = NP.decide((), pages, {}, (), 0.5)
    assert taken == () and dec.line("TEST") == ""


def test_the_law_key():
    assert load_default().tables.structures.load.network_pages_share_max == 0.5


def test_a_page_that_alone_holds_a_taxiway_is_a_source():
    """RULINGS 2026-10-30e (#2215, KRDU ``Ground/L2.pol`` taxiway A): at or
    above the share, a page carrying the network where no source holds it is
    taken; a page over held ground, a runway slab's ground or a stretch under
    the key stays a sheet."""
    from shapely.geometry import box
    nodes, edges = _network()
    pav = (_rect("pav0", 0, -10, 900, 10),)                        # 90 %
    pages = (_rect("dsf:gapsheet3", 880, -20, 1000, 20, desc="Ground/L2.pol"),
             _rect("dsf:gapsheet4", 0, -20, 500, 20, desc="Ground/ap.pol"),
             _rect("dsf:gapsheet5", 0, 490, 200, 510, desc="Runway.pol"))
    dec, taken = NP.decide(pav, pages, nodes, edges, 0.5, (), 10.0)
    assert dec.promoted and dec.ids == ("dsf:gapsheet3",)
    assert [p.id for p in taken] == ["dsf:netpage0"]
    assert abs(dec.unheld_m - 100.0) < 1e-6
    assert "alone hold 100 m" in dec.line("TEST")
    # the runway slab holds its own ground; a stretch under the key, or the
    # key at 0, takes nothing
    slab = [box(950, -30, 1000, 30)]
    assert NP.decide(pav, pages, nodes, edges, 0.5, slab, 10.0)[0].ids == ("dsf:gapsheet3",)
    assert NP.decide(pav, pages, nodes, edges, 0.5, slab, 60.0)[1] == ()
    assert NP.decide(pav, pages, nodes, edges, 0.5, (), 0.0)[1] == ()


def test_the_unheld_key():
    assert load_default().tables.structures.load.network_page_unheld_min_m == 10.0
