"""ADJACENT-GROUND INGESTION — the zone-law CONSTRAINT CONSUMPTION.

The supply half is the INGEST lane's
(``adjacent_ground.build_zone_constraint_table`` →
``layout.adjacent_ground_zone_boxes``, pinned by
``test_zone_constraint_supply``).  These are the twins for the KILL
lane's half: the solve binding the published table as DIRECTED
constraints on band variables it owns.

THE CONTRACT, verbatim from the supply docstring::

    z[node] - ((1-t)*z[foot.a] + t*z[foot.b]) in [floor_off, ceil_off]

seeded at ``dem_seed``.

WHY A BOX.  The datum is a lerp of two variables, which the pairwise
projection cannot state exactly — and does not have to: the constraint
is DIRECTED (pavement gives, zone conforms), so with the datum's
endpoints owned by pavement it collapses EXACTLY to an absolute interval
on the zone variable alone.  That is the strip-fabric box family the
supply docstring names, it is what ``one_solve._node_box_arrays``
consumes, and being per-node it can never pull the pavement.

No network, no DEM, no fixtures: a stub layout and arithmetic.
"""
from __future__ import annotations

import inspect
import math

import pytest

from auto_patch.elevation_per_surface.route_profile import solve as SV


# ── a stub layout: just the canonical registry the consumer reads ────

class _CPS:
    """Exact-coordinate registry (the real one interns within 0.5 m;
    these twins place every point far enough apart that the two agree)."""

    def get_or_add(self, x, y):
        return (round(float(x), 6), round(float(y), 6))


class _Layout:
    def __init__(self, rows, first_zone=2):
        self.canonical_points = _CPS()
        self.adjacent_ground_zone_boxes = rows
        self._adjacent_ground_first_zone_index = first_zone


# node space: 0,1 = pavement ring vertices (the FOOT); 2,3 = band nodes.
_A = (0.0, 0.0)
_B = (10.0, 0.0)
_Z = (5.0, 4.0)
_Z2 = (7.0, 4.0)
_B2I = {(0.0, 0.0): 0, (10.0, 0.0): 1, (5.0, 4.0): 2, (7.0, 4.0): 3}
_ELEV = [100.0, 110.0, 41.5, 41.5]          # foot a=100, foot b=110


def _row(**kw):
    row = {"shape_id": 1, "ref": "apr", "key": (5000, 4000), "xy": _Z,
           "kind": "fill", "depth_m": 3.0,
           "floor_off": -1.0, "ceil_off": 2.0, "snap_tol_m": 0.05,
           "foot": {"a": _A, "b": _B, "t": 0.5, "gap_m": 4.0},
           "host": _A, "host_delta": 0.0, "dem_seed": 41.5}
    row.update(kw)
    return row


def _boxes(rows, elev=None, first_zone=2, n=4):
    layout = _Layout(rows, first_zone=first_zone)
    return SV._zone_foot_boxes(layout, _B2I,
                               list(elev or _ELEV), n, first_zone)


# ── the datum is the FOOT LERP, not a vertex ─────────────────────────

def test_the_box_is_the_foot_lerp_plus_the_published_offsets():
    """The whole point of the handoff: the datum is
    ``(1-t)*z[a] + t*z[b]`` over two variables the solve already owns —
    NOT the frozen-nearest host vertex, which on a long steep edge sits
    metres off the local foot (measured 12 m at the CYXY trench wall)."""
    boxes, stats = _boxes([_row()])
    assert boxes[2] == pytest.approx((105.0 - 1.0, 105.0 + 2.0))
    assert stats[1] == 1 and stats[2] == 0        # foot, not host


@pytest.mark.parametrize("t,datum", [(0.0, 100.0), (0.25, 102.5),
                                     (1.0, 110.0)])
def test_the_parameter_selects_the_point_on_the_edge(t, datum):
    boxes, _ = _boxes([_row(foot={"a": _A, "b": _B, "t": t, "gap_m": 4.0})])
    assert boxes[2] == pytest.approx((datum - 1.0, datum + 2.0))


def test_the_datum_moves_with_the_pavement_never_the_other_way():
    """DIRECTED: the box is a function of the solved pavement, so raising
    the foot raises the whole corridor.  And it is a per-NODE box, so
    there is no channel through which the band could move the foot."""
    lo0, hi0 = _boxes([_row()])[0][2]
    lifted = list(_ELEV)
    lifted[0] += 3.0
    lifted[1] += 3.0
    lo1, hi1 = _boxes([_row()], elev=lifted)[0][2]
    assert (lo1 - lo0, hi1 - hi0) == pytest.approx((3.0, 3.0))


# ── the law's kind rule survives the carry ───────────────────────────

def test_a_cut_row_is_ceiling_only():
    """``floor_off is None`` is the law's CUT rule (below-floor terrain
    inside a cut piece belongs to the fill machinery) — it must arrive as
    an unbounded floor, not as a zero."""
    boxes, _ = _boxes([_row(kind="cut", floor_off=None)])
    lo, hi = boxes[2]
    assert lo == -math.inf
    assert hi == pytest.approx(107.0)


def test_an_unbounded_ceiling_arrives_unbounded():
    boxes, _ = _boxes([_row(ceil_off=None)])
    assert boxes[2][1] == math.inf


def test_the_offsets_are_carried_verbatim_not_re_derived():
    """ONE derivation of the corridor (the supply's).  A consumer that
    recomputed the envelope would be the second copy that made the
    cross-shape collision unarguable for a week."""
    src = inspect.getsource(SV._zone_foot_boxes)
    assert "floor_off" in src and "ceil_off" in src
    for forbidden in ("envelope_at", "zone_corridor_box",
                      "adjacent_ground_envelope", "dem"):
        assert forbidden not in src, forbidden


def test_the_seam_prolongation_shift_is_applied():
    """``host_delta`` is the re-homed-host reference shift; dropping it
    anchors a station a full prolongation away to the cut-back corner."""
    boxes, _ = _boxes([_row(host_delta=2.0)])
    assert boxes[2] == pytest.approx((105.0 + 1.0, 105.0 + 4.0))


# ── the degrade path the contract names ──────────────────────────────

def test_a_footless_row_falls_back_to_the_host_vertex():
    """"Where ``foot`` is ``None`` the legacy pairwise slab against
    ``host`` is the degrade path" — a shape whose ring the march could
    not foot still owes its band a law."""
    boxes, stats = _boxes([_row(foot=None)])
    assert boxes[2] == pytest.approx((99.0, 102.0))   # host = node 0
    assert stats[1] == 0 and stats[2] == 1


def test_an_absent_table_binds_nothing_and_does_not_raise():
    """A layout that predates the supply lane (or an airport with no
    bands) must degrade silently — the legacy host-slab constraints are
    still in ``shape_constraints``."""
    layout = _Layout(None)
    assert SV._zone_foot_boxes(layout, _B2I, list(_ELEV), 4, 2) == (
        {}, (0, 0, 0, 0, 0, 0))


# ── identity: pavement always wins ───────────────────────────────────

def test_a_zone_node_that_adopted_a_pavement_variable_gets_no_box():
    """Pavement value wins at a pavement node — an IDENTITY, not an
    arbitration.  A band law may never constrain a pavement variable."""
    boxes, stats = _boxes([_row(xy=_A)])          # index 0 < first_zone
    assert boxes == {}
    assert stats[3] == 1                          # counted, not silent


def test_a_node_outside_the_pass_node_space_is_skipped():
    boxes, _ = _boxes([_row(xy=_Z2)], n=3)        # index 3 >= n
    assert boxes == {}


# ── cross-shape collision: intersect, never first-claimant-wins ──────

def test_two_shapes_on_one_variable_intersect_their_boxes():
    """``shape_id`` makes the collision VISIBLE; intersecting is the
    honest resolution (the rule ``_box_isect`` already applies to merged
    pad groups).  First-claimant-wins would silently drop a real law."""
    boxes, stats = _boxes([
        _row(shape_id=1, floor_off=-1.0, ceil_off=2.0),
        _row(shape_id=2, floor_off=-0.5, ceil_off=5.0)])
    assert boxes[2] == pytest.approx((104.5, 107.0))
    assert stats[4] == 1 and stats[5] == 0


def test_an_empty_intersection_is_a_declared_conflict():
    """Two corridor laws that cannot both hold at one vertex is a defect
    to ATTRIBUTE at source (``feasibility-is-guaranteed``), so it is
    counted and reported rather than silently resolved."""
    boxes, stats = _boxes([
        _row(shape_id=1, floor_off=-1.0, ceil_off=2.0),
        _row(shape_id=2, floor_off=5.0, ceil_off=6.0)])
    assert stats[5] == 1
    assert boxes[2] == pytest.approx((104.0, 107.0))   # first claimant


# ── the writeback carries, it does not value ─────────────────────────

def test_the_writeback_no_longer_re_derives_from_the_dem():
    """THE handoff item: ``_zv = float(_dem_z)`` discarded the solved
    value for every edge-owning zone node and recomputed
    ``clamp(raw DEM, ref + offsets)``.  A box around a value that IS the
    datum has no slack to remove — which is why the v2 box measured
    vacuous.  The emitted band value must be the SOLVED value."""
    src = inspect.getsource(SV.solve_route_profile)
    zone = src[src.index("ADJACENT-GROUND ZONE-ROW writeback"):]
    zone = zone[:zone.index("RUNWAY-END RESA CUT writeback")]
    body = "\n".join(ln for ln in zone.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "_dem_z" not in body
    assert "_ZONE_SNAP" not in body
    assert "_elev_emit[_zi]" in body


def test_the_seed_is_the_published_dem_seed():
    """The variable starts where the supply says it starts; no consumer
    re-samples the DEM for a band node."""
    src = inspect.getsource(SV.solve_route_profile)
    seed = src[src.index("ADJACENT-GROUND INGESTION, the SEED"):]
    seed = seed[:seed.index("_psub(0.20")]
    assert 'dem_seed' in seed
    assert "elev[_zi] = float(_zs)" in seed
