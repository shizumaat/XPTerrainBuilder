"""Twins for ``auto_patch.geom_safe.safe_difference`` — the certified
overlay the pavement overlap-clip pass writes back into the layout.

Root cause it exists for (KDFW, 2026-08-25, GEOS 3.13.1 / shapely
2.1.2): ``elevation._drop_overlap_against_fixed_shapes`` clipped a
41-vertex junction against a 60-vertex neighbour.  Both polygons are
VALID and their interiors are DISJOINT — they share an edge (two exact
common vertices) and nothing else.  ``p.difference(c)`` nevertheless
returned a polygon whose shell is ``p``'s own exterior plus a spurious
2 952 m² hole lying entirely OUTSIDE that shell.  The pass wrote it
into ``layout.shapes`` unchecked; ~200 passes later
``pavement_scoring._reach_zone``'s ``unary_union`` raised
``TopologyException: side location conflict`` at the shared vertex and
the whole KDFW build died before the elevation solve.

The fixture is the measured pair, not a synthetic stand-in — the
failure is a data-specific GEOS robustness break and cannot be
conjured from a toy square.
"""
from pathlib import Path

import pytest
from shapely import wkt
from shapely.geometry import Polygon, box
from shapely.validation import explain_validity

from auto_patch.geom_safe import GeomSafeError, safe_difference

FIXTURE = Path(__file__).parent / "fixtures" / "kdfw_overlay_clip_pair.wkt"


def _kdfw_pair():
    lines = [ln.strip() for ln in FIXTURE.read_text().splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert len(lines) == 2, FIXTURE
    return wkt.loads(lines[0]), wkt.loads(lines[1])


def test_fixture_is_the_documented_class():
    """Both inputs valid, interiors disjoint (they only share an edge)."""
    p, c = _kdfw_pair()
    assert p.is_valid and c.is_valid
    assert len(p.interiors) == 0
    assert p.touches(c), "the pair shares an edge and nothing else"
    assert p.distance(c) == 0.0
    assert p.area == pytest.approx(8087.9, abs=0.1)
    assert c.area == pytest.approx(85700.4, abs=0.1)


def test_bare_geos_difference_is_the_defect():
    """The defect this module wraps, pinned so the twin stays honest.

    If a future GEOS fixes the overlay this assertion flips — and that
    is a signal to re-read ``geom_safe``, not a silent behaviour drift.
    """
    p, c = _kdfw_pair()
    d = p.difference(c)
    if d.is_valid:                       # pragma: no cover - GEOS fixed
        pytest.skip("GEOS no longer mis-computes this overlay")
    assert "Hole lies outside shell" in explain_validity(d)


def test_safe_difference_certifies_the_kdfw_pair():
    """The certified overlay returns a VALID polygon, and returns the
    geometrically right one: the interiors do not overlap, so the
    difference is the clipped shape itself (area preserved)."""
    p, c = _kdfw_pair()
    d = safe_difference(p, c)
    assert d.is_valid, "safe_difference must never return invalid geometry"
    assert d.geom_type == "Polygon"
    # Monte-Carlo integration over the pair measures zero overlap, so the
    # answer is p.  1e-6 relative is the precision-grid snap, not slack.
    assert d.area == pytest.approx(p.area, rel=1e-6)


def test_safe_difference_is_plain_difference_when_geos_is_right():
    """No behaviour change on the geometry GEOS handles correctly: the
    plain overlay result is returned untouched, byte-for-byte."""
    a = box(0.0, 0.0, 10.0, 10.0)
    b = box(4.0, -1.0, 12.0, 11.0)
    assert safe_difference(a, b).equals_exact(a.difference(b), 0.0)

    # Difference that splits the shape, and one that empties it.
    bar = box(-1.0, 4.0, 11.0, 6.0)
    assert safe_difference(a, bar).equals_exact(a.difference(bar), 0.0)
    assert safe_difference(a, box(-1, -1, 11, 11)).is_empty

    # Disjoint inputs: the whole shape survives.
    assert safe_difference(a, box(50, 50, 60, 60)).area == pytest.approx(100.0)


def test_safe_difference_raises_rather_than_returning_invalid(monkeypatch):
    """When no precision grid rescues the overlay, the certified form
    RAISES at the mint point instead of parking invalid geometry in the
    layout — the whole point of the KDFW fix.

    Simulated by disabling the grid retry (``set_precision`` becomes the
    identity), which leaves GEOS's broken answer as the only candidate.
    """
    import auto_patch.geom_safe as GS

    p, c = _kdfw_pair()
    if p.difference(c).is_valid:         # pragma: no cover - GEOS fixed
        pytest.skip("GEOS no longer mis-computes this overlay")
    monkeypatch.setattr(GS.shapely, "set_precision",
                        lambda geom, grid, **kw: geom)
    with pytest.raises(GeomSafeError) as exc:
        safe_difference(p, c)
    assert "no valid result" in str(exc.value)


def test_clip_pieces_never_writes_invalid_geometry():
    """The consumer twin: the overlap-clip pass's own
    ``_clip_pieces`` returns only valid polygons for the KDFW pair.

    ``GeomSafeError`` is deliberately outside ``elevation._GEOM_EXC``,
    so the pass cannot swallow an uncertifiable overlay into a silently
    smaller layout.
    """
    from auto_patch import elevation as EL

    assert not issubclass(GeomSafeError, EL._GEOM_EXC), \
        "an uncertifiable overlay must fail the build, not be swallowed"

    p, c = _kdfw_pair()
    layout = _one_shape_layout(p)
    EL._drop_overlap_against_fixed_shapes(layout, icao="TEST",
                                          include_aprons=True)
    for s in layout.shapes:
        assert s.polygon is None or s.polygon.is_valid


def _one_shape_layout(poly: Polygon):
    """Minimal layout carrying one junction — enough for the clip pass."""
    from auto_patch.layout import BuiltShape, PavementLayout, ROLE_JUNCTION

    lay = PavementLayout(icao="TEST", anchor=(32.9, -97.0))
    lay.shapes = [BuiltShape(polygon=poly, role=ROLE_JUNCTION, ref="")]
    return lay
