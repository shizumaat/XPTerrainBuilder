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
    pm, _airport, _got = _rel(law, _StepDem(2.0))
    pad = next(f for f in pm.faces.values() if f.ref == "padA")
    lot = next(f for f in pm.faces.values() if f.ref == "lotA")
    rim = list(pm.ring_vertices(pad.ring))
    ring = list(pm.ring_vertices(lot.ring))
    front = [v for v in ring if pm.vertices[v].xy[1] <= 261.5]
    assert pair_dem_step_m(pm, front, rim) == pytest.approx(2.0)
    # a vertex with no DEM never disarms: no measurement, no terrace
    assert pair_dem_step_m(pm, [], rim) is None


def test_the_bound_is_the_laws_and_not_a_literal(law):
    """The value is ``law/emit.toml [design] frontage_step_max_m``, read
    through the schema — the sibling of ``pad_frontage_m``, the radius of
    the same relation.  It is a LAW key and not a ``classify [lot]`` one
    because ``constraints`` may not import ``classify``
    (``test_model.test_dependency_direction``)."""
    from auto_patch_v2.law.tables import design as design_law
    assert frontage_step_max_m(law) == design_law(law).frontage_step_max_m
    assert frontage_step_max_m(law) == pytest.approx(4.0)
