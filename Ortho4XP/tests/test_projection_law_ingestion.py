"""Twins for the cycle-4 projection-ingestion round.

Spec: ``docs/specs/cycle4-projection-ingestion-spec.md``.  The round's
claim is that ``final_grade_projection``'s constraint set IS the solve's
law — every law input captured ONCE at solve time, carried by CANONICAL
IDENTITY, and consumed verbatim.  These twins pin the parts of that claim
that can be pinned without a build:

1. the carry survives a node-list rebuild (identity, not index);
2. a HANDED zone cap survives into the projection's constraint set —
   BOTH edge sets, and with its application COUNTED, so a plan that
   fails to apply can never read as "the zone quietly grades at the
   strict cap" (the fan-acceptance failure's exact shape);
3. the near-miss building-frontage law reaches the projection at all —
   it needs ``building_seats``, a solve-phase artifact, which is why the
   family used to go missing there;
4. the post-solve mutation set and the law certificate, the two readers
   the round's numbers are quoted from.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from auto_patch.config import POST_SOLVE_IDEMPOTENCE_TOL_M
from auto_patch.elevation_per_surface.node_space import NodeSpaceStore
from auto_patch.elevation_per_surface.route_profile import apron_terrace as AT
from auto_patch.elevation_per_surface.route_profile import solve as RP


# ── 1.  the carry is by identity, never by index ────────────────────────
def test_carried_law_context_survives_a_node_list_rebuild():
    """The solve mints by canonical key; a REBUILT node space resolves the
    same values through different indices.  This is the rod-key lesson as
    an assertion: nothing in the carry may be an index."""
    store = NodeSpaceStore()
    # solve-time space: keys 10, 11, 12 at indices 0, 1, 2
    store.mint("solved_values", "scalar", {10: 100.0, 11: 101.5, 12: 99.25})
    store.mint("building_seats", "scalar", {11: 101.5})
    store.mint("gs_witness", "keyset", {12})

    # projection space: SAME keys, different indices, one key gone (the
    # decimator deleted its vertex) and one index beyond the node count.
    rebuilt = {12: 0, 10: 1, 99: 2}
    n = 3
    values = store.view_scalar("solved_values", rebuilt, n)
    assert values == {0: 99.25, 1: 100.0}
    assert store.view_scalar("building_seats", rebuilt, n) == {}
    assert store.view_keyset("gs_witness", rebuilt, n) == {0}


def test_carried_field_is_lifted_into_the_passs_crown_frame():
    """The law lives in uncrowned z'; the carry is minted in EMITTED space,
    so the view must add the pass's own crown drop — otherwise every
    crowned node reads as post-solve moved by its crown."""
    store = NodeSpaceStore()
    store.mint("solved_values", "scalar", {7: 50.0})
    got = store.view_scalar("solved_values", {7: 0}, 1, crown_of={0: 0.3})
    assert got[0] == pytest.approx(50.3)


# ── 2.  a handed zone cap survives into the projection's law ────────────
def _fan_plan_5pct(shape_id):
    """A one-zone 5 % fan-ramp plan over a 100 m x 100 m square."""
    from shapely.geometry import Polygon
    poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    plan = AT.FanRampPlan()
    plan.add(shape_id, {"shape_id": shape_id, "cap": 0.05, "polygon": poly,
                        "buildings": (), "area_m2": poly.area})
    return plan


def test_handed_zone_cap_reaches_both_of_the_projections_edge_sets():
    """THE FAN RAIL.  A 5 % zone cap handed to the solve must arrive in the
    projection's constraint set on BOTH edge sets — relief granted only in
    one is taken straight back by the other."""
    shape_id = 4242
    plan = _fan_plan_5pct(shape_id)
    node_xy = {0: (10.0, 10.0), 1: (60.0, 10.0), 2: (10.0, 500.0)}
    apron_cap = 0.01

    # within-shape entry: one chord inside the zone, one leaving it
    entry = {"shape_id": shape_id, "role": "apron", "ref": None,
             "nodes": [0, 1, 2],
             "edges": [(0, 1, apron_cap * 50.0), (0, 2, apron_cap * 490.0)]}
    n_sc = AT.apply_fan_ramp_caps(plan, [entry], node_xy)
    assert n_sc == 1, "the in-zone chord must take the zone cap"
    inside = next(e for e in entry["edges"] if {e[0], e[1]} == {0, 1})
    leaving = next(e for e in entry["edges"] if {e[0], e[1]} == {0, 2})
    assert inside[2] == pytest.approx(0.05 * 50.0)
    assert leaving[2] == pytest.approx(apron_cap * 490.0), (
        "a chord that leaves the zone keeps the strict apron cap — "
        "movement surfaces are never relaxed")

    # unified-graph edge set: the same law, the same call shape
    u_edges = [(0, 1, apron_cap * 50.0), (0, 2, apron_cap * 490.0)]
    u_edges, n_u = AT.apply_fan_ramp_caps_to_edges(plan, u_edges, node_xy)
    assert n_u == 1
    assert u_edges[0][2] == pytest.approx(0.05 * 50.0)
    assert u_edges[1][2] == pytest.approx(apron_cap * 490.0)


def test_the_projection_applies_the_carried_plans_and_counts_them():
    """No silent narrowing (spec requirement 3).  ``final_grade_projection``
    must apply BOTH carried plans to BOTH edge sets, and must RECORD each
    application — a bare ``except: pass`` around a law makes a failed plan
    read as a clean strict-cap result."""
    tree = ast.parse(inspect.getsource(RP.final_grade_projection))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    for applier in ("_apply_fan_fp", "_apply_fan_u_fp",
                    "_apply_terr_fp", "_apply_terr_u_fp"):
        assert applier in called, (
            f"{applier} is not called: the projection would enforce a "
            f"different law than the solve on one of its two edge sets")
    # every applier's result is recorded in the ingestion ledger
    recorded = {n.slice.value for n in ast.walk(tree)
                if isinstance(n, ast.Subscript)
                and isinstance(n.value, ast.Name)
                and n.value.id == "_fp_law_counts"
                and isinstance(n.slice, ast.Constant)}
    assert {"fan_sc", "fan_u", "terrace_sc", "terrace_u",
            "frontage_near_miss"} <= recorded


def test_the_projection_builds_its_frontage_law_from_the_carried_seats():
    """The near-miss frontage family needs ``building_seats`` — a SOLVE
    artifact.  The projection must read the carried seats and call the
    SAME constructor the solve used, never a parallel implementation."""
    src = inspect.getsource(RP.final_grade_projection)
    assert 'view_scalar("building_seats"' in src
    assert "near_miss_building_frontage_edges" in src
    solve_src = inspect.getsource(RP.solve_route_profile)
    assert 'mint(\n        "building_seats"' in solve_src or (
        '"building_seats", "scalar"' in solve_src), (
        "the solve must MINT the seats it built; without the carry the "
        "projection cannot enforce the frontage law at all")


# ── 3.  the two readers the round's numbers come from ───────────────────
def test_post_solve_mutation_set_partitions_new_moved_and_untouched():
    carried = {0: 10.0, 1: 20.0, 2: 30.0}          # index 3 is NEW
    elev = [10.0, 20.005, 31.0, 5.0]
    untouched, n_new, moved = post_call(carried, elev)
    assert n_new == 1                               # index 3
    assert untouched == {0, 1}                      # 1 is inside 0.01 m
    assert [round(m[0], 3) for m in moved] == [1.0]  # index 2


def post_call(carried, elev):
    return RP.post_solve_mutation_set(carried, elev, len(elev),
                                      tol=POST_SOLVE_IDEMPOTENCE_TOL_M)


def test_post_solve_mutation_set_is_inert_without_a_carry():
    """A layout that never ran the solve (probes, unit tests) partitions to
    nothing — the projection then behaves exactly as it did before."""
    untouched, n_new, moved = post_call({}, [1.0, 2.0, 3.0])
    assert (untouched, n_new, moved) == (set(), 0, [])


def test_law_certificate_names_the_family_and_counts_both_hard():
    joint = [
        {"role": "apron", "ref": None,
         "edges": [(0, 1, 0.10), (1, 2, 5.0)]},
        {"family": "unified_graph", "edges": [(0, 2, 0.10)]},
        {"family": "rod_interval", "edges": [(0, 1, -0.10, 0.10)]},
    ]
    cert = RP.projection_law_certificate(joint, [0.0, 1.0, 2.0], 3, {0, 2})
    assert cert["apron:-"][0] == 1                  # (0,1) is 0.9 over
    assert cert["apron:-"][1] == pytest.approx(0.9)
    assert cert["apron:-"][2] == 0                  # node 1 is free
    assert cert["unified_graph"] == (1, pytest.approx(1.9), 1)
    assert cert["rod_interval"][0] == 1             # dz -1.0 below the slab


def test_law_certificate_ignores_edges_outside_the_node_space():
    cert = RP.projection_law_certificate(
        [{"family": "u", "edges": [(0, 9, 0.0)]}], [0.0, 1.0], 2, set())
    assert cert["u"] == (0, 0.0, 0)


# ── 4.  the harness reader (who_wrote --author) ─────────────────────────
def _who_wrote_module():
    import importlib.util
    path = (Path(__file__).resolve().parents[1]
            / "tools" / "harness" / "who_wrote.py")
    spec = importlib.util.spec_from_file_location("who_wrote_twin", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Shape:
    role = "apron"
    ref = ""
    polygon = None

    def __init__(self):
        self.node_altitudes = None


def test_displacement_census_classifies_against_the_solve():
    """The reader for requirement 2.  A value the projection moves is
    ``untouched`` only when the SOLVE wrote it and nothing else did — the
    class that must be empty for the requirement to hold."""
    ww = _who_wrote_module()
    probe = ww.AuthorshipProbe(_Shape, authors=("final_grade_projection",),
                               author_tol=0.01)
    s = _Shape()
    probe._record_author(s, "apron", [1.0, 2.0, 3.0],
                         "solve.py:1:solve_route_profile")
    # another post-solve pass moves vertex 1
    probe._record_author(s, "apron", [1.0, 2.9, 3.0],
                         "groundside.py:2:emit_something")
    # the projection moves vertex 0 (untouched) and vertex 1 (already moved)
    probe._record_author(s, "apron", [4.0, 5.0, 3.0],
                         "solve.py:3:final_grade_projection")
    rows, totals = probe.author_report()
    by_class = {r["class"]: r for r in rows}
    assert by_class["untouched"]["n_moved"] == 1
    assert by_class["untouched"]["max_m"] == pytest.approx(3.0)
    assert by_class["moved_post_solve"]["n_moved"] == 1
    assert totals[("final_grade_projection", "untouched")]["n_moved"] == 1


def test_displacement_census_calls_a_reshaped_ring_new_geometry():
    """A ring the post-solve passes reshaped carries law pairs the solve
    never saw; moves there are the projection's legitimate residual job,
    not second authorship."""
    ww = _who_wrote_module()
    probe = ww.AuthorshipProbe(_Shape, authors=("final_grade_projection",),
                               author_tol=0.01)
    s = _Shape()
    probe._record_author(s, "apron", [1.0, 2.0],
                         "solve.py:1:solve_route_profile")
    probe._record_author(s, "apron", [1.0, 2.0, 2.5],   # planarize insert
                         "planarize.py:2:insert")
    probe._record_author(s, "apron", [1.4, 2.0, 2.5],
                         "solve.py:3:final_grade_projection")
    rows, _ = probe.author_report()
    assert [r["class"] for r in rows] == ["new_geometry"]
