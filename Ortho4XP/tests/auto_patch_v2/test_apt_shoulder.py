"""§40 (6) THE APT.DAT SHOULDER (owner RULINGS 2026-10-20n, 20o, 20p;
issue #1103) as synthetic twins over the M1 synthetic airport
(``test_classify._synthetic``: runway 09/27, 30 m wide, code 2/C, a 20 m
taxi strip leaving its north edge at x = 490..510 with its centreline at
x = 500):

1. the row-100 shoulder code states its width in its hundreds
   (``apt_dat.shoulder_width_m``: 727 -> 7 m; a legacy 0/1/2 -> 0);
2. 20n: the runway's band reads that width as its shoulder where no
   pavement covers it — runway-shoulder cells, ``shoulder_source`` =
   ``apt.dat``, on unpaved ground only (20o, 20p): none overlaps a
   pavement cell, and the taxiway's mouth stays the taxiway's;
3. no apt.dat width, no mint: the classification is the base one;
4. 20o, 20p: a paved shoulder ribbon a taxiway leaves through is shoulder
   up to the taxiway and no further — the taxiway inside the strip is a
   taxi-family face welded to the runway edge, with the apt.dat width as
   the shoulder line and, where the row states none, the ribbon's own
   depth.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.airport.apt_dat import _runway, shoulder_width_m  # noqa: E402
from auto_patch_v2.classify import classify, load_rules  # noqa: E402
from auto_patch_v2.classify.apt_shoulder import APT_SOURCE  # noqa: E402
from auto_patch_v2.classify.roles import TAXI_FAMILY  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import Pavement, Surface  # noqa: E402
from test_classify import _rect, _synthetic  # noqa: E402

#: the synthetic taxi strip's mouth across a 10 m shoulder
MOUTH = box(490.0, 15.0, 510.0, 25.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _airport(shoulder_m: float, ribbon: bool):
    a = _synthetic(gate=True, island=False)
    rw = _dc.replace(a.runways[0], shoulder_m=shoulder_m)
    pav = a.pavements
    if ribbon:     # a 10 m paved shoulder along the north edge, 400 m long
        pav = pav + (Pavement("ribbon", Surface.ASPHALT,
                              _rect(300.0, 15.0, 700.0, 25.0), ()),)
    return _dc.replace(a, runways=(rw,), pavements=pav)


def _poly(c):
    return Polygon(c.ring, c.holes)


def test_row_100_shoulder_code_states_its_width():
    row = ("100 45.00 15 727 0.25 0 3 0 "
           "10 38.5 -28.7 0 0 3 2 1 1 "
           "28 38.5 -28.6 0 0 2 8 0 0").split()
    assert _runway(row).shoulder == 727
    assert shoulder_width_m(727) == 7.0
    assert shoulder_width_m(1200) == 12.0
    assert [shoulder_width_m(c) for c in (0, 1, 2, 26)] == [0.0] * 4


def test_the_band_reads_the_apt_dat_shoulder_on_unpaved_ground(law, rules):
    cl = classify(_airport(10.0, ribbon=False), law, rules)
    apt = [c for c in cl.cells if c.evidence.get("shoulder_source") == APT_SOURCE]
    assert apt, cl.stats
    for c in apt:
        assert (c.role, c.ref, c.kind) == ("runway", "09/27", "runway_shoulder")
        assert (c.code_number, c.code_letter) == (2, "C")
    sh = unary_union([_poly(c) for c in apt])
    # both sides, the slab's length (1000 m + the 60 m overrun), 10 m deep,
    # less the taxi strip's mouth
    assert sh.area == pytest.approx(2 * 10.0 * 1060.0 - MOUTH.area, rel=0.01)
    paved = unary_union([_poly(c) for c in cl.cells if c not in apt
                         and c.role != "graded_strip"])
    assert sh.intersection(paved).area < 1.0       # never crosses pavement
    assert sh.intersection(MOUTH).area < 1.0       # the taxiway keeps its mouth
    assert cl.stats["apt_shoulders"] == len(apt)


def test_no_apt_dat_width_mints_nothing(law, rules):
    base = classify(_synthetic(gate=True, island=False), law, rules)
    cl = classify(_airport(0.0, ribbon=False), law, rules)
    assert cl.stats["apt_shoulders"] == 0
    assert [(c.role, c.ref, c.kind, c.ring) for c in cl.cells] == \
        [(c.role, c.ref, c.kind, c.ring) for c in base.cells]


@pytest.mark.parametrize("shoulder_m", [10.0, 0.0])
def test_a_shoulder_stops_at_a_taxiway_entrance(law, rules, shoulder_m):
    """The ribbon is a §40 shoulder; the taxi strip leaving the runway
    through it — inside the code-2 strip (40 m) — is a taxiway from the
    runway edge out, never shoulder."""
    cl = classify(_airport(shoulder_m, ribbon=True), law, rules)
    sh = unary_union([_poly(c) for c in cl.cells if c.kind == "runway_shoulder"])
    strip = box(490.0, 15.0, 510.0, 40.0)
    assert sh.intersection(strip).area < 1.0, cl.stats
    taxi = [c for c in cl.cells if c.role in TAXI_FAMILY
            and _poly(c).intersection(strip).area > 1.0]
    assert sum(_poly(c).intersection(strip).area for c in taxi) == \
        pytest.approx(strip.area, rel=0.02)
    slab = Polygon(cl.cells[0].ring)                   # the runway body
    assert any(_poly(c).distance(slab) < rules.cells.on_tol_m for c in taxi)
    # the ribbon either side of the entrance is still the runway's shoulder
    ribbon = box(300.0, 15.0, 700.0, 25.0).difference(box(490.0, 15.0, 510.0, 25.0))
    assert sh.intersection(ribbon).area == pytest.approx(ribbon.area, rel=0.02)
    assert cl.stats["shoulder_taxiway_entrances"] >= 1


def test_the_mouth_never_widens_past_the_entrance(rules):
    """#1135: the touch tolerance finds the entrance's seam with the
    shoulder line but never widens the mouth past the entrance's own
    stations — a 1 m buffer carried the mouth 0.68 m past an entrance
    abutting a parallel runway's end, minting a vertex beside that
    runway's corner (EDTK ``runway_step`` 1.66 m)."""
    from types import SimpleNamespace
    from auto_patch_v2.classify.apt_shoulder import _mouth, _shoulder_line
    rw = SimpleNamespace(slab_corners=((0.0, -15.0), (1000.0, -15.0),
                                       (1000.0, 15.0), (0.0, 15.0)),
                         width_m=30.0, shoulder_m=10.0)
    line, half = _shoulder_line(rw, 0.0)
    inside = box(300.0, 15.0, 700.0, 25.0)       # the shoulder ribbon
    comp = box(490.0, 25.0, 510.0, 40.0)         # the entrance beyond it
    m = _mouth(comp, rw, line, half, inside, rules)
    assert m is not None
    x0, _y0, x1, _y1 = m.bounds
    assert (x0, x1) == pytest.approx((490.0, 510.0), abs=1e-6)


def test_polygon_parts_reads_through_a_collection():
    """A MultiPolygon inside a GeometryCollection keeps its polygons (the
    OTHH gap piece a snap-grid collection dropped, #1103)."""
    from auto_patch_v2.classify.evidence import polygon_parts
    from shapely.geometry import GeometryCollection, LineString, MultiPolygon
    a, b = box(0, 0, 1, 1), box(2, 0, 3, 1)
    gc = GeometryCollection([MultiPolygon([a, b]), LineString([(5, 5), (6, 6)]), box(4, 0, 5, 1)])
    assert [p.bounds for p in polygon_parts(gc)] == [a.bounds, b.bounds, (4, 0, 5, 1)]


def test_a_seam_pavement_closes_before_the_shoulder_line_is_not_shoulder(law, rules):
    """20n/20o: a pavement abutting the runway with a small gap (here an
    apron 1.5 m off the south edge, covering the band to beyond its
    shoulder line along its whole length) leaves a SEAM between the two
    pavements, not shoulder ground: it never reaches the shoulder line,
    so no runway-shoulder cell is minted there (HECA: two such seams
    minted 15 ``runway_step`` DEFECT rows).  The north side, unpaved out
    to its line, keeps its shoulder."""
    a = _airport(10.0, ribbon=False)
    a = _dc.replace(a, pavements=a.pavements + (
        Pavement("abutting", Surface.ASPHALT, _rect(-300.0, -60.0, 1300.0, -16.5), ()),))
    cl = classify(a, law, rules)
    apt = [c for c in cl.cells if c.evidence.get("shoulder_source") == APT_SOURCE]
    seam = box(-300.0, -16.5, 1300.0, -15.0)
    assert all(_poly(c).intersection(seam).area < 1.0 for c in apt), cl.stats
    north = unary_union([_poly(c) for c in apt]).intersection(box(-300.0, 15.0, 1300.0, 25.0))
    assert north.area == pytest.approx(10.0 * 1060.0 - MOUTH.area, rel=0.01)
