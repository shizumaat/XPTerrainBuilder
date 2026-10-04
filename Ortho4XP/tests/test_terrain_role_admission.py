"""Stage B0 terrain-role admission scaffolding tests
(docs/slice_b_solver_absorption_design.md).

Hermetic — a tiny hand-built layout, no fixtures.  Verifies:
  * ``admitted_terrain_roles`` is empty with the master gate off (default) AND
    with the master gate on but every per-role sub-gate off (an empty admitted
    set = a structural no-op — Stage B0's landing condition);
  * each per-role sub-gate admits exactly its terrain role;
  * ``_build_node_list`` is byte-identical (same node list) when the admitted
    set is empty, and grows to include a terrain-role shape's ring vertices only
    when that role is admitted — the object-bridge plate admission pattern.
"""
from shapely.geometry import Polygon

import auto_patch.config as cfg


class _FakeShape:
    def __init__(self, role, polygon, ref=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref


def _square(x0, y0, side=10.0):
    return Polygon([(x0, y0), (x0 + side, y0), (x0 + side, y0 + side),
                    (x0, y0 + side)])


# EVERY terrain-absorption sub-gate, enumerated once.  A test that pins
# "all sub-gates off" or isolates ONE family must control the whole set —
# a family it does not know about defaults ON and either leaks into the
# admitted set or trips a hard-dependency chain.  That is exactly what the
# arc-R RESA family did on 2026-07-25 when its gate flipped to default ON:
# four tests here failed, two on a leaked ``runway_end_resa`` pair and two
# on the fail-loudly dependency guard firing because the RESA gate was on
# while the skirt gate was pinned off.  ``test_subgate_list_is_complete``
# below makes the next family a LOUD failure here rather than a silent
# skew in the tests that use this list.
_SUBGATES = (
    "ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT",
    "ONE_SOLVE_TERRAIN_RUNWAY_END_RESA",
    "ONE_SOLVE_TERRAIN_GAP_FILL_SPINE",
    "ONE_SOLVE_TERRAIN_GRADED_STRIP",
    "ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT",
)


def test_subgate_list_is_complete():
    """``_SUBGATES`` must name every ``ONE_SOLVE_TERRAIN_*`` sub-gate in
    config.  A new terrain family that lands without being added here
    would silently escape every isolation test in this module."""
    found = {n for n in dir(cfg)
             if n.startswith("ONE_SOLVE_TERRAIN")
             and n != "ONE_SOLVE_TERRAIN"
             and isinstance(getattr(cfg, n), bool)}
    assert found == set(_SUBGATES), (
        "sub-gate set drift — add the new gate to _SUBGATES: "
        f"missing {sorted(found - set(_SUBGATES))}, "
        f"stale {sorted(set(_SUBGATES) - found)}")


