"""Consensus retirement §2 — THE LOSING CLAIMANT RETREATS.

``layout.to_osm`` emits the precedence WINNER's value at a contested
node (standing law since 2026-08-05; the consensus mean is retired).
Alone that is only half the law: a loser beyond
``VERTEX_ALT_MERGE_TOL_M`` would be silently DRAGGED to the winner's
value — the same defect the mean had, minus the averaging, and the
measured cause of the groundside tear family.

``adjacent_ground.emit_authority_retreat_walls`` is the other half: the
loser retreats into its own interior and the difference ships as a face.
A loser WITHIN tol adopts, unchanged.

THE WALLS RULING (owner 2026-08-07, executed R19-4) decides WHICH face:
a retaining wall ONLY at a carve structure (tunnel/bridge portal,
abutment); everywhere else the vacated band is a graded FEATHER under
the loser's own role and cap — "where ground must change height it
grades ... tight spots get steep slopes, never walls".

These twins pin what must hold:
  1. the loser moves and gets a FEATHER, graded inside its own cap, and
     no wall;
  2. at a carve structure the wall stays, with its own retreat;
  3. the WINNER never moves (airside-is-king as constraint direction);
  4. within tol nothing happens at all;
  5. no face is minted inside a runway-strip footprint (owner
     2026-08-01, walls at runway edges are never lawful);
  6. a feather that does not FIT is not forced — the loser adopts, and
     no wall is minted in its place.
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


def _layout(lot_z, lot_depth=200.0, carve=False):
    """An apron and a groundside lot sharing a whole EDGE.

    The apron outranks the lot in ``AUTHORITY_PRECEDENCE``, so the lot is
    the losing claimant at both shared corners.  ``lot_depth`` is how
    much room the lot has for the feather run (``spread / cap``);
    ``carve`` puts a tunnel ramp at the shared edge, which is where a
    retaining wall is still lawful.
    """
    layout = PavementLayout(icao="KFAKE", anchor=(51.87, -0.37))
    layout.canonical_points = CanonicalPointRegistry(
        tol_m=SHARED_VERTEX_TOL_M)
    # The apron abuts the MIDDLE of the lot's top edge, so the two
    # contested vertices are mid-ring on the lot (the production
    # geometry: a lot welded to a road/apron along part of an edge).  A
    # ring CORNER can only retreat along the diagonal of its two edges,
    # which is why the fixture must not make the contested vertices
    # corners.
    layout.shapes.append(BuiltShape(
        polygon=Polygon([(100, 0), (140, 0), (140, 40), (100, 40)]),
        role=ROLE_APRON, ref="apr",
        node_altitudes=[APRON_Z] * 5))
    layout.shapes.append(BuiltShape(
        polygon=Polygon([(0, 0), (0, -lot_depth), (400, -lot_depth),
                         (400, 0), (140, 0), (100, 0)]),
        role=ROLE_GROUNDSIDE_PAVEMENT, ref="lot",
        node_altitudes=[lot_z] * 7))
    if carve:
        from auto_patch.layout import ROLE_TUNNEL_RAMP
        layout.shapes.append(BuiltShape(
            polygon=Polygon([(110, 2), (130, 2), (130, 12), (110, 12)]),
            role=ROLE_TUNNEL_RAMP, ref="ramp",
            node_altitudes=[APRON_Z - 6.0] * 5))
    return layout


def _walls(layout):
    return [s for s in layout.shapes
            if (s.ref or "") == "authority_retreat_wall"]


def _feathers(layout):
    return [s for s in layout.shapes
            if (s.ref or "") == "authority_retreat_feather"]


def test_a_loser_beyond_tolerance_welds_and_emits_nothing():
    """S6 · WELD OR GAP (owner 2026-08-13, RULINGS "TRANSITION MACHINERY
    RETIRES") — THE RETIRED-EMITTER TWIN.

    4 m below the apron at a shared edge, no carve structure in sight.
    The feather is RETIRED: the loser is left exactly where it is, no
    face of any kind is minted, and the shared node is resolved by the
    single-authority §1 law at ``to_osm`` (the precedence winner's value
    is emitted) — which is the WELD the ruling requires of two surfaces
    that touch.  What used to be the "dragged up 4 m" failure mode is
    now the LAW: touching surfaces agree at shared nodes.
    """
    layout = _layout(APRON_Z - 4.0)
    lot = layout.shapes[1]
    before = list(lot.polygon.exterior.coords)
    n = AG.emit_authority_retreat_walls(layout)
    assert n == 0, (
        "the retired feather path still emitted a face — weld-or-gap "
        "leaves NO transition geometry away from a carve structure")
    assert not _walls(layout), "no wall away from a carve structure"
    assert not _feathers(layout), (
        "a feather survived the retirement — the 2026-08-13 ruling names "
        "feathers explicitly")
    assert list(lot.polygon.exterior.coords) == before, (
        "the loser was MOVED — under weld-or-gap it must keep its "
        "vertices and agree with the winner at the shared node")


def test_a_carve_structure_keeps_its_wall():
    """The ONE admission the ruling leaves: "walls are lawful ONLY at
    tunnel/bridge carve structures (portals, abutments)"."""
    layout = _layout(APRON_Z - 4.0, carve=True)
    n = AG.emit_authority_retreat_walls(layout)
    assert n > 0
    assert _walls(layout), (
        "the portal's wall was retired too — the ruling's own exception")


def test_a_tight_spot_welds_too_and_never_smuggles_a_wall_back():
    """S6 · WELD OR GAP — the tight-spot twin.

    The 2026-08-07 ruling said "tight spots get steep slopes, never walls
    (no tight-spot exception)"; the 2026-08-13 ruling retires the slope
    (feather) as well.  A lot with no room for ``spread / cap`` therefore
    gets NOTHING here — it welds at the shared node like any other loser.
    The point the test still guards is unchanged and is the reason it
    stays: a tight spot must never be the back door through which the
    wall role returns.
    """
    layout = _layout(APRON_Z - 4.0, lot_depth=6.0)
    assert AG.emit_authority_retreat_walls(layout) == 0
    assert not _walls(layout), (
        "a tight spot smuggled the wall role back in")
    assert not _feathers(layout), (
        "a tight spot smuggled the retired feather back in")


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
