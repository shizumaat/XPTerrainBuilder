"""§W2 — THE OPEN-CUT EDGE TAKES THE CORRIDOR PROFILE (the humps).

Spec ``docs/specs/claimed-corridor-wall-survival-spec.md`` §W2, RE-KEYED
by ``docs/specs/linear-transport-redesign-spec.md`` §5.2 (census row
#50) under RULINGS 2026-08-31b.

WHAT THE RE-KEY CHANGED — the REGION, not the law.  The index used to
union the portal walk's published open cut WITH R14-1's claim set
(``tunnel_open_cut_claim_polys``).  That class is retired; the CUT HALF
STANDS ALONE, and it is the half that answers "where does the bore's
ground lie" — the question this seniority asks.  The §W2 law, the
measurement below and every assertion in this file are unchanged; only
the answer to "which region" moved.  (The name
``claim_edge_profile_index`` is the src's, kept so this twin names its
subject.)

MEASURED (OTHH, app 1.0.264, owner site 25.25591,51.6086926).  The
corridor's descent is lawful (~4.5 % against a 5 % cap), but the emitted
ring TENTS: way ``-10051`` reads ``... -964:2.19  -965:4.00  -968:4.00
-969:0.99 ...`` — two vertices pinned at grade in the middle of the
descent.  Both are the TOP ROW of ``authority_retreat_wall`` way
``-12605``, whose face crosses the ramp: the retreat machine writes
``conflict_top`` (the at-grade level the LOSER retreats from) at the
vacated positions, those positions lie on the descending corridor's own
edge, and the emit's nid-level weld then references them from the
corridor ring.  A car driving the ramp climbs 3 m and drops 3 m again.

THE LAW: between a tunnel's mouths the corridor profile is SENIOR on the
open cut's boundary — a crossing grade-level authority takes the corridor's
interpolated altitude at the shared node.  The face still emits (the
``tunnel-corridor-node-book-exclusion-spec`` §3 population is
untouched); only the level it retreats FROM changes.

MECHANISM BEFORE FIX: ``test_the_pin_is_reproduced_with_the_gate_off``
is the interventional twin — it reproduces the pinned TOP ROW on a
synthetic scene, and the ON arm shows it taking the corridor's
interpolated value instead.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch import adjacent_ground as AG
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.layout import (BuiltShape, PavementLayout,
                               ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD,
                               ROLE_TUNNEL_RAMP,
                               SHARED_VERTEX_TOL_M)

FLAG = AG._CLAIM_EDGE_SENIORITY_ENV

#: the at-grade level the OTHH pin shipped
GRADE_Z = 4.0
#: the corridor's own values either side of the pinned run
HIGH_Z = 2.19
LOW_Z = 0.99
#: the junction that loses at the shared node and retreats
BENCH_Z = 2.30


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _scene():
    """A descending corridor host crossed by an at-grade junction.

    The corridor host ring runs along ``y = 0`` from ``x = 0`` (HIGH_Z)
    to ``x = 40`` (LOW_Z); the junction sits on that edge and holds a
    grade-level bench.  The junction's mid-ring vertices at ``x = 10``
    and ``x = 30`` are the OTHH ``-965``/``-968`` pair: they lie ON the
    corridor's descending edge, and the retreat face's TOP ROW is what
    ships their altitude.
    """
    lay = PavementLayout(icao="KFAKE", anchor=(25.25, 51.60))
    lay.canonical_points = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    # THE CROSSING AUTHORITY.  A grade-level ring whose bottom edge lies
    # on the corridor's descending edge; the two mid-edge vertices are
    # the contested ones (a ring CORNER can only retreat along its
    # diagonal, which the emitter refuses).
    junction = BuiltShape(
        polygon=Polygon([(0, 0), (10, 0), (30, 0), (40, 0),
                         (40, 30), (0, 30)]),
        role=ROLE_SERVICE_JUNCTION,
        node_altitudes=[BENCH_Z] * 6)
    # THE DESCENDING CORRIDOR HOST — the ring the claim dug.  Its top
    # edge carries the profile the crossing authority must take.
    host = BuiltShape(
        polygon=Polygon([(0, 0), (40, 0), (40, -60), (0, -60)]),
        role=ROLE_SERVICE_ROAD,
        node_altitudes=[HIGH_Z, LOW_Z, LOW_Z, HIGH_Z])
    # THE PIN: a grade-level authority claiming the two shared nodes.
    pin = BuiltShape(
        polygon=Polygon([(10, 0), (30, 0), (30, 12), (10, 12)]),
        role=ROLE_SERVICE_ROAD,
        node_altitudes=[GRADE_Z] * 4)
    # THE CARVE STRUCTURE the wall is lawful at (owner 2026-08-07:
    # "walls are lawful ONLY at tunnel/bridge carve structures") — the
    # portal furniture of the very corridor being descended.
    carve = BuiltShape(polygon=_rect(12, 1, 28, 8),
                       role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                       node_altitudes=[LOW_Z] * 5)
    lay.shapes.extend([pin, junction, host, carve])
    # THE PUBLISHED REGION — ``bridges.publish_tunnel_open_cut_regions``'
    # own output, never re-derived here.
    lay.tunnel_open_cut_polys = [_rect(-5, -60, 45, 20)]
    return lay, junction, host, pin


def _walls(lay):
    return [s for s in lay.shapes
            if (getattr(s, "ref", "") or "") == "authority_retreat_wall"]


def _top_row_values(lay):
    """Every altitude a retreat face ships at ``y == 0`` — the row the
    OTHH pin lives in."""
    out = []
    for w in _walls(lay):
        ring = list(w.polygon.exterior.coords)[:-1]
        alts = list(w.node_altitudes or ())
        for (x, y), a in zip(ring, alts):
            if abs(y) < 1e-6 and a is not None:
                out.append(round(float(a), 2))
    return out


def test_the_pin_is_reproduced_with_the_gate_off(monkeypatch):
    """MECHANISM: with §W2 off, the face's top row ships the AT-GRADE
    level on the corridor's descending edge — the OTHH tent."""
    monkeypatch.setenv(FLAG, "0")
    lay, junction, host, pin = _scene()
    AG.emit_authority_retreat_walls(lay)
    top = _top_row_values(lay)
    assert top, "no retreat face was emitted — the scene does not pin"
    assert max(top) >= GRADE_Z - 0.05, (
        f"expected the at-grade pin {GRADE_Z} in the face's top row, "
        f"got {top}")


def test_the_corridor_profile_is_senior_on_its_own_edge(monkeypatch):
    """§W2 ON: the same face ships the corridor's INTERPOLATED altitude
    at those nodes (between {HIGH_Z} and {LOW_Z}), never the grade."""
    monkeypatch.delenv(FLAG, raising=False)
    lay, junction, host, pin = _scene()
    AG.emit_authority_retreat_walls(lay)
    top = _top_row_values(lay)
    assert top, "the face stopped emitting — §W2 must not suppress it"
    assert max(top) < GRADE_Z - 0.5, (
        f"a top-row vertex is still pinned at grade: {top}")
    assert min(top) >= LOW_Z - 0.35 and max(top) <= HIGH_Z + 0.35, (
        f"top row {top} is not the corridor's own descending profile "
        f"({LOW_Z}..{HIGH_Z})")


def test_it_can_only_lower(monkeypatch):
    """The cut can only DIG, and so can its seniority: a corridor
    value ABOVE the crossing authority's level is never adopted."""
    monkeypatch.delenv(FLAG, raising=False)
    lay, junction, host, pin = _scene()
    # host now stands ABOVE the pin everywhere
    host.node_altitudes = [GRADE_Z + 3.0, GRADE_Z + 1.0,
                           GRADE_Z + 1.0, GRADE_Z + 3.0]
    AG.emit_authority_retreat_walls(lay)
    top = _top_row_values(lay)
    assert top and max(top) >= GRADE_Z - 0.05, (
        f"the pass RAISED a retreat level: {top}")


def test_a_flat_ring_in_the_cut_publishes_no_seniority():
    """SCOPE: the index is built from rings that DESCEND through the cut.
    A flat ring inside it (a bore FLOOR, an at-grade neighbour) is not a
    corridor — this is what keeps the tunnel-corridor exclusion spec's §3
    retreat faces emitting unchanged."""
    lay, junction, host, pin = _scene()
    host.node_altitudes = [LOW_Z] * 4          # flat floor, not a descent
    pin.node_altitudes = [LOW_Z] * 4
    junction.node_altitudes = [LOW_Z] * 6
    assert AG.claim_edge_profile_index(lay) is None


def test_no_published_cut_means_no_index(monkeypatch):
    """No cut published ⇒ no index ⇒ the pass is byte-identical.  The
    region is READ, never derived (one authority)."""
    monkeypatch.delenv(FLAG, raising=False)
    lay, junction, host, pin = _scene()
    del lay.tunnel_open_cut_polys
    assert AG.claim_edge_profile_index(lay) is None


def test_the_index_reads_the_CUT_only_never_the_retired_claim_half(
        monkeypatch):
    """Census #50 / redesign spec §5.2: the union lost its claim half.
    A layout publishing ONLY the retired ``tunnel_open_cut_claim_polys``
    builds no index — the attribute is dead, not silently still read."""
    monkeypatch.delenv(FLAG, raising=False)
    lay, junction, host, pin = _scene()
    cut = lay.tunnel_open_cut_polys
    del lay.tunnel_open_cut_polys
    lay.tunnel_open_cut_claim_polys = cut       # the retired attribute
    assert AG.claim_edge_profile_index(lay) is None
    # …and the same polygons published as the CUT do build one, so the
    # twin above cannot pass because the scene stopped descending.
    lay2, _j, _h, _p = _scene()
    assert AG.claim_edge_profile_index(lay2) is not None


def test_gate_off_builds_no_index(monkeypatch):
    monkeypatch.setenv(FLAG, "0")
    lay, junction, host, pin = _scene()
    assert AG.claim_edge_profile_index(lay) is None
