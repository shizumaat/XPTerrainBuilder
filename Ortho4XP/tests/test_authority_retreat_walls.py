"""Consensus retirement §2 — THE LOSING CLAIMANT RETREATS.

``layout.to_osm`` emits the precedence WINNER's value at a contested
node (standing law since 2026-08-05; the consensus mean is retired).
Alone that is only half the law: a loser beyond
``VERTEX_ALT_MERGE_TOL_M`` would be silently DRAGGED to the winner's
value — the same defect the mean had, minus the averaging, and the
measured cause of the groundside tear family.

``adjacent_ground.emit_authority_retreat_walls`` is the other half: the
loser retreats ``STACKED_WALL_RETREAT_M`` into its own interior and the
difference ships as a ``retaining_wall`` face.  A loser WITHIN tol
adopts, unchanged.

These twins pin the four things that must hold:
  1. the loser moves and gets a face;
  2. the WINNER never moves (airside-is-king as constraint direction);
  3. within tol nothing happens at all;
  4. no face is minted inside a runway-strip footprint (owner
     2026-08-01, walls at runway edges are never lawful).
"""
import pytest
from shapely.geometry import Polygon

from auto_patch import adjacent_ground as AG
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    ROLE_APRON,
    ROLE_GROUNDSIDE_PAVEMENT,
    SHARED_VERTEX_TOL_M,
)

APRON_Z = 100.0


def _layout(lot_z):
    """An apron and a groundside lot sharing a whole EDGE.

    The apron outranks the lot in ``AUTHORITY_PRECEDENCE``, so the lot is
    the losing claimant at both shared corners.
    """
    layout = PavementLayout(icao="KFAKE", anchor=(51.87, -0.37))
    layout.canonical_points = CanonicalPointRegistry(
        tol_m=SHARED_VERTEX_TOL_M)
    layout.shapes.append(BuiltShape(
        polygon=Polygon([(0, 0), (40, 0), (40, 40), (0, 40)]),
        role=ROLE_APRON, ref="apr",
        node_altitudes=[APRON_Z] * 5))
    layout.shapes.append(BuiltShape(
        polygon=Polygon([(0, 0), (0, -40), (40, -40), (40, 0)]),
        role=ROLE_GROUNDSIDE_PAVEMENT, ref="lot",
        node_altitudes=[lot_z] * 5))
    return layout


def _walls(layout):
    return [s for s in layout.shapes
            if (s.ref or "") == "authority_retreat_wall"]


def test_a_loser_beyond_tolerance_retreats_and_walls():
    """4 m below the apron at a shared edge: the lot retreats and the
    step ships as geometry instead of being dragged up 4 m."""
    layout = _layout(APRON_Z - 4.0)
    lot = layout.shapes[1]
    before = list(lot.polygon.exterior.coords)
    n = AG.emit_authority_retreat_walls(layout)
    assert n > 0, "the losing claimant was not walled"
    assert _walls(layout), "no retaining_wall face was emitted"
    assert list(lot.polygon.exterior.coords) != before, (
        "the loser kept its vertices — it will be dragged at emit")


def test_the_winner_never_moves():
    """Airside-is-king expressed as constraint DIRECTION: only the lower
    party conforms."""
    layout = _layout(APRON_Z - 4.0)
    apron = layout.shapes[0]
    before = list(apron.polygon.exterior.coords)
    before_alts = list(apron.node_altitudes)
    AG.emit_authority_retreat_walls(layout)
    assert list(apron.polygon.exterior.coords) == before
    assert list(apron.node_altitudes) == before_alts


def test_within_tolerance_the_loser_adopts():
    """Inside ``VERTEX_ALT_MERGE_TOL_M`` there is no wall and no retreat
    — the emitter's ordinary adoption stands."""
    layout = _layout(APRON_Z - 0.4)
    lot = layout.shapes[1]
    before = list(lot.polygon.exterior.coords)
    assert AG.emit_authority_retreat_walls(layout) == 0
    assert not _walls(layout)
    assert list(lot.polygon.exterior.coords) == before


def test_no_face_inside_a_runway_strip(monkeypatch):
    """Walls at runway edges are NEVER lawful (owner 2026-08-01): the run
    is skipped and the conflict falls back to adoption."""
    layout = _layout(APRON_Z - 4.0)
    monkeypatch.setattr(
        AG, "runway_strip_wall_keepout",
        lambda _layout, **_kw: Polygon(
            [(-100, -100), (200, -100), (200, 200), (-100, 200)]))
    assert AG.emit_authority_retreat_walls(layout) == 0
    assert not _walls(layout)


def test_the_retreat_machine_has_one_derivation():
    """``emit_stacked_conflict_walls`` and ``emit_authority_retreat_walls``
    must share ``_retreat_run_walls`` — two copies of the retreat is how
    the wall constants drifted into three homes before."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(AG))
    for fn in ("emit_stacked_conflict_walls", "emit_authority_retreat_walls"):
        node = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == fn)
        called = {c.func.id for c in ast.walk(node)
                  if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        assert "_retreat_run_walls" in called, fn
