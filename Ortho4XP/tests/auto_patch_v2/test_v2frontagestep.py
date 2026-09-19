"""§28 (6) A HILLSIDE TERRACE IS NOT A FRONTAGE — the twins (owner
RULINGS 2026-09-13o, refined 13p; spec ``auto-patch-v2/
design-surface-spec.md`` §28 (6)).

The site they stand for: CYXY's ``building10`` / ``building9`` are cut
into a hill with their car park and service page arriving a storey above
them (owner 13l item 1).  §28 (1)'s 3,000-weight frontage row graded
those lots down to the pads and made ``dsf:pol129`` a 3.4 m excavation it
can never climb out of at its 8 % cap.  The bound is PER PAIR and it is
read in the ONE derivation of the relation.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints.pad_frontage_gs import (STATS,
                                                       frontage_step_max_m,
                                                       groundside_frontage,
                                                       groundside_frontage_level,
                                                       pair_dem_step_m)
from auto_patch_v2.law import Law
from auto_patch_v2.planar.build import build

from test_v2frontage import _airport, _cells  # noqa: E402  (same dir)


class _StepDem:
    """The LOT's ground stands ``step`` metres above the pad's — a hill
    the buildings are cut into (CYXY) when the step is a storey, a
    terrace the owner ordered graded (LEMD ``building4``) when it is not.
    The pad and its apron are at 700.0 everywhere."""

    provenance = {"synthetic": "hillside"}

    def __init__(self, step: float, spike: float = 0.0, spike_x: float = 60.0):
        self.step = float(step)
        self.spike = float(spike)
        self.spike_x = float(spike_x)

    def z(self, x: float, y: float) -> float:
        if y <= 260.5:
            return 700.0
        if self.spike and abs(x - self.spike_x) < 1.0:
            return 700.0 + self.spike
        return 700.0 + self.step

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rel(law, dem):
    airport = _airport(law, dem)
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    return pm, airport, groundside_frontage(pm, law)


# ── the bound ────────────────────────────────────────────────────────────

def test_a_pair_over_the_bound_mints_no_frontage_row_and_is_counted(law):
    """CYXY's class: the lot's own ground stands a storey above the pad,
    so the pair is a lawful hillside terrace — NO row, the face keeps its
    ground, and the pair is REPORTED (``pairs_held_as_terrace``) rather
    than silently dropped."""
    bound = frontage_step_max_m(law)
    pm, airport, rel = _rel(law, _StepDem(bound + 1.0))
    assert rel == {}
    assert groundside_frontage_level(pm, law, airport) == []
    assert STATS["groundside_frontage_level"]["pairs_held_as_terrace"] == 1


def test_a_pair_under_the_bound_still_takes_the_pads_level(law):
    """LEMD ``building4``'s class, the case 2026-09-12r ordered graded:
    a terrace under the bound is still a frontage and still mints its
    rows."""
    bound = frontage_step_max_m(law)
    pm, airport, rel = _rel(law, _StepDem(bound - 1.0))
    assert rel, "a lot a metre under the bound is still a frontage"
    assert groundside_frontage_level(pm, law, airport)
    assert STATS["groundside_frontage_level"]["pairs_held_as_terrace"] == 0


def test_the_bound_is_per_pair_and_never_per_vertex(law):
    """§28 (6) verbatim: "Per pair, never per vertex (a per-vertex bound
    saw-tooths S2's 16-vertex frontage)".  One frontage vertex standing
    far over the bound does not cost that vertex its row while the pair's
    MEDIAN is under it — the face is graded whole or held whole."""
    bound = frontage_step_max_m(law)
    flat = _StepDem(0.0)
    pm_f, airport_f, rel_f = _rel(law, flat)
    spiked = _StepDem(0.0, spike=bound + 10.0)
    pm_s, airport_s, rel_s = _rel(law, spiked)
    assert rel_s, "the pair's median is under the bound: still a frontage"
    # the SAME followers, spike included — no vertex is dropped on its own
    def followers(pm, airport):
        return sorted(v for r in groundside_frontage_level(pm, law, airport)
                      for v in (r.follows or ()))
    assert followers(pm_s, airport_s) == followers(pm_f, airport_f)
    assert rel_f, "the flat arm is a frontage too"
    assert STATS["groundside_frontage_level"]["pairs_held_as_terrace"] == 0


def test_the_quantity_is_the_planar_maps_own_dem_sample(law):
    """The pair's step is read from ``Vertex.dem_z`` — the production DEM
    taken once at map build — and is the median over the FRONTAGE minus
    the median over the PAD FOOTPRINT (never a second DEM reader, never
    the solved level, which no generator can see)."""
    from auto_patch_v2.constraints.pads import _pad_polys
    pm, _airport, _got = _rel(law, _StepDem(2.0))
    pad = next(f for f in pm.faces.values() if f.ref == "padA")
    lot = next(f for f in pm.faces.values() if f.ref == "lotA")
    rim = list(pm.ring_vertices(pad.ring))
    poly = next(p[3] for p in _pad_polys(pm, law) if p[0] == pad.id)
    ring = list(pm.ring_vertices(lot.ring))
    front = [v for v in ring if pm.vertices[v].xy[1] <= 261.5]
    assert pair_dem_step_m(pm, law, front, pad.id, poly, rim) == pytest.approx(2.0)
    # a vertex with no DEM never disarms: no measurement, no terrace
    assert pair_dem_step_m(pm, law, [], pad.id, poly, rim) is None


def test_the_bound_is_the_laws_and_not_a_literal(law):
    """The value is ``law/emit.toml [design] frontage_step_max_m``, read
    through the schema — the sibling of ``pad_frontage_m``, the radius of
    the same relation.  It is a LAW key and not a ``classify [lot]`` one
    because ``constraints`` may not import ``classify``
    (``test_model.test_dependency_direction``)."""
    from auto_patch_v2.law.tables import design as design_law
    assert frontage_step_max_m(law) == design_law(law).frontage_step_max_m
    assert frontage_step_max_m(law) == pytest.approx(2.4)


# ── the pad's side of the step is its AIRSIDE FRONTAGE ───────────────────
# (owner RULINGS 2026-09-18c (1), Q CYXY-2a option C: "Building pads are
# seated based on their airside frontage, then we leave a gap".)

class _HillDem:
    """A hill rising northwards: the apron band at 700.0, the pad's north
    edge and the lot a storey above it.  CYXY ``building9`` / ``pav4``'s
    own shape — the pad is seated on the apron it fronts (694.108 there,
    measured) while its own northern ground stands with the lot."""

    provenance = {"synthetic": "hill_north"}

    def z(self, x: float, y: float) -> float:
        return 700.0 if y <= 230.0 else 704.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _detached_cells(north_edge_vertices: bool):
    """The CYXY shape: a pad standing 1 m OFF the apron (so its airside
    frontage is a PROXIMITY contact — its southern rim alone, 10ax) with a
    lot 1 m north of it.  ``north_edge_vertices`` adds three mid-edge
    vertices along the pad's NORTH edge: the arrangement's own freedom to
    re-node a pad face (``dba32406``), which is what moves a rim median."""
    from auto_patch_v2.classify.roles import Cell
    from test_v2frontage import RUN_LEN, HALF_W, _rect
    north = (((60.0, 260.0), (20.0, 260.0), (0.0, 260.0), (-20.0, 260.0))
             if north_edge_vertices else ((60.0, 260.0),))
    pad = ((-60.0, 200.0), (60.0, 200.0)) + north + ((-60.0, 260.0),)
    return [Cell(0, "runway", "09/27",
                 _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                 (), 3, "D", "airside", "runway", {}),
            Cell(1, "apron", "apronA", _rect(-260.0, 140.0, 260.0, 199.0),
                 (), None, None, "airside", "apron", {}),
            Cell(2, "building", "padA", pad, (), None, None,
                 "airside", "pad", {}),
            Cell(3, "parking_lot", "lotA", _rect(-60.0, 261.0, 60.0, 361.0),
                 (), None, None, "groundside", "parking_lot", {})]


def _step_of(law, cells):
    from auto_patch_v2.constraints.pad_frontage_gs import (_groundside_geoms,
                                                           pad_airside_frontage)
    from auto_patch_v2.constraints.pads import _pad_polys, pad_fronts_airside
    from shapely.geometry import Point
    airport = _airport(law, _HillDem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    pid, _ref, rim, poly = next(
        p for p in _pad_polys(pm, law) if p[0] in pad_fronts_airside(pm, law))
    r = 3.0
    gvs = next(g[3] for g in _groundside_geoms(pm, law))
    front = [v for v in gvs - set(rim)
             if poly.distance(Point(*pm.vertices[v].xy)) <= r]
    air = pad_airside_frontage(pm, law, pid)
    return pm, pid, poly, rim, front, air


def test_the_pads_datum_is_its_airside_frontage_and_not_the_arranged_rim(law):
    """THE TWIN FOR THE OPTION-C CHANGE.  Two arms of ONE pad differing
    only in the arrangement's re-noding of its NORTH edge — the trim class
    that collapsed CYXY-2/3 (``building9`` 40 -> 26 rim vertices,
    ``building10`` 22 -> 14, RULINGS 2026-09-18c (1)).  The RIM-median
    quantity moves between the arms; §28 (6)'s quantity DOES NOT, because
    the pad's datum is the seat §20 levels it to."""
    import statistics
    from auto_patch_v2.constraints.pad_frontage_gs import pair_dem_step_m
    steps, rim_steps = [], []
    for north in (True, False):
        pm, pid, poly, rim, front, air = _step_of(law, _detached_cells(north))
        assert air and set(air) <= set(rim), "the seat is the pad's own rim vertices"
        assert all(pm.vertices[v].xy[1] < 230.0 for v in air), \
            "the airside frontage is the pad's SOUTHERN edge, on the apron"
        steps.append(pair_dem_step_m(pm, law, front, pid, poly, rim))
        med = lambda vs: statistics.median(  # noqa: E731
            [float(pm.vertices[v].dem_z) for v in vs])
        rim_steps.append(med(front) - med(rim))
    assert steps[0] == pytest.approx(steps[1]), \
        "the quantity may not depend on the arranged pad rim"
    assert steps[0] == pytest.approx(4.0), \
        "the lot stands a storey above the pad's own seat"
    assert abs(rim_steps[0] - rim_steps[1]) > 1.0, \
        "the RETIRED rim quantity does move with the re-noding (the defect)"


def test_the_airside_frontage_is_section_20s_own_contacts(law):
    """No second relation: :func:`pad_airside_frontage` IS
    ``pads.pad_frontage``'s output restricted to the AIRSIDE roles, so §20
    and §28 cannot disagree about where a pad sits."""
    from auto_patch_v2.constraints.pad_frontage_gs import pad_airside_frontage
    from auto_patch_v2.constraints.pads import pad_frontage
    from auto_patch_v2.law.tables import role_side
    pm, pid, _poly, _rim, _front, air = _step_of(law, _detached_cells(True))
    rel = pad_frontage(pm, law)
    assert air == sorted({v for role, cs in rel[pid].items()
                          if role_side(law, role) == "airside" for v in cs})


def test_the_fallback_is_an_area_weighted_dem_over_the_pads_outline(law):
    """§28 (6)'s FALLBACK (owner 2026-09-18c (1)): a pad whose airside
    frontage carries no DEM sample takes an AREA-weighted DEM over its own
    outline — area, not a vertex count, so the arrangement's re-noding
    cannot move it either."""
    from auto_patch_v2.constraints.pad_frontage_gs import (pad_area_weighted_dem,
                                                           pair_dem_step_m)
    got = []
    for north in (True, False):
        pm, pid, poly, rim, front, air = _step_of(law, _detached_cells(north))
        got.append(pad_area_weighted_dem(pm, poly, rim))
        # a pad NOT in the §20 relation has no seat, so the quantity is
        # read against the area weighting instead (never against the rim)
        absent = 1 + max(pm.faces)
        assert pair_dem_step_m(pm, law, front, absent, poly, rim) == \
            pytest.approx(float(pm.vertices[front[0]].dem_z) - got[-1])
    assert got[0] == pytest.approx(got[1]), \
        "an area weighting does not count vertices"
