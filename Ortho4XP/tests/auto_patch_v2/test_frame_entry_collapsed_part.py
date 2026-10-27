"""Twin for #1472 (CYVR): A REPAIR'S OPERAND IS AN AREA.

The placement snap can collapse one tiny part of a footprint's
MultiPolygon to zero area.  GEOS's ``make_valid`` of that MultiPolygon
repairs each part, gets a point or a line for the collapsed one, and its
union of the parts refuses the mix (``Overlay input is mixed-dimension``)
— CYVR's whole patch was lost to it in ``door_wells.read_family`` →
``obj8.above_grade_footprint`` → ``frame_entry.enter``.  ``enter`` now
drops the parts that hold no area before each repair, as it already did
after it.  Red on main 7a11600c0."""
from __future__ import annotations

import numpy as np
import pytest
import shapely
from auto_patch_v2.airport import frame_entry as fe
from auto_patch_v2.airport import obj8_clip
from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Polygon

#: a fuzz-found operand: part 1 collapsed to one point, part 2 a bowtie
_COLLAPSED = Polygon([(0, 1), (0, 1), (0, 1), (0, 1)])
_BOWTIE = Polygon([(1.5, 1.5), (1, 1), (0.5, 0.5), (2, 1), (1.5, 1.5)])
_OPERAND = MultiPolygon([_COLLAPSED, _BOWTIE])


def test_the_operand_is_what_geos_refuses():
    """The mechanism, pinned: if GEOS ever repairs this itself the twin
    below is no longer the witness."""
    with pytest.raises(GEOSException, match="mixed-dimension"):
        shapely.make_valid(_OPERAND)


@pytest.mark.parametrize("q", [0.0, 0.5])
def test_enter_repairs_a_footprint_with_a_collapsed_part(q):
    out = fe.enter([_OPERAND], fe.IDENTITY, q)
    g = out[0]
    assert g is not None and g.is_valid
    assert g.geom_type in ("Polygon", "MultiPolygon")
    assert g.area == pytest.approx(shapely.make_valid(_BOWTIE).area, abs=q * q + 1e-9)


def test_enter_drops_a_previous_rounds_lines_before_the_repair():
    """A round's ``make_valid`` hands back lines beside the polygons; the
    next round's operand is their areal part only."""
    gc = GeometryCollection([_BOWTIE, LineString([(0, 0), (3, 0)]), _COLLAPSED])
    g = fe.enter([gc], fe.IDENTITY, 0.0)[0]
    assert g is not None and g.is_valid and g.geom_type in ("Polygon", "MultiPolygon")


def test_a_bowtie_reading_zero_area_is_not_dropped():
    """The pre-repair floor is the HULL's area: a symmetric bowtie's signed
    ring area reads 0, and it still repairs to two triangles."""
    bow = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])
    assert bow.area == 0.0
    g = fe.enter([MultiPolygon([bow, _COLLAPSED])], fe.IDENTITY, 0.0)[0]
    assert g is not None and g.area == pytest.approx(2.0)


def test_valid_input_is_untouched():
    sq = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    out = fe.enter([sq, None, Polygon()], fe.IDENTITY, 0.0)
    assert out[0].equals(sq) and out[1] is None and out[2] is None


def test_clipped_ring_repair_keeps_only_area():
    """``obj8_clip._union_rings``: a repaired ring's lines never reach the
    union (the areal part of each repair, ``geom/parts.areal_part``)."""
    spike = [(0, 0), (2, 0), (2, 2), (1, 2), (1, 3), (1, 2), (0, 2)]
    u = obj8_clip._union_rings([np.asarray(spike, dtype=float)])
    assert u is not None and u.geom_type in ("Polygon", "MultiPolygon")
    assert u.area == pytest.approx(4.0)
