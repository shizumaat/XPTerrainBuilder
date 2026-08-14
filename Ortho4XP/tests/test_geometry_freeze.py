"""THE GEOMETRY FREEZE RAIL — twins (staged-solve round S1).

The freeze's whole value is that a post-freeze mutation of solve-consumed
plan geometry becomes a TRACEBACK instead of a silent wrong answer.  These
twins assert exactly that, in both directions:

  * a mutation after the freeze point FAILS — added shape, dropped shape,
    moved vertex, inserted vertex, re-role, reordered ``layout.shapes``;
  * an unchanged layout PASSES, and so does everything the freeze
    deliberately does NOT cover (altitudes, the pre-solve construction
    STORES), because over-freezing would refuse lawful work;
  * the published one-graph accessors are RAIL-CHECKED — handing out a
    band or a graph derived from geometry that has since moved is the
    exact silent failure the freeze exists to stop, so the check lives in
    the accessor and not in the caller's good intentions;
  * ``clear`` lifts the rail, because phase-[6] emission is lawful
    mutation.

The fixtures are deliberately toy ``BuiltShape`` stand-ins: the rail reads
``role``, ``ref`` and ``polygon`` and nothing else, and a twin that needed
a real airport would not be a twin of the rail.
"""
import pytest
from shapely.geometry import Polygon

from auto_patch import geometry_freeze as gf
from auto_patch.geometry_freeze import GeometryFreezeViolation


class _Shape:
    """Minimal ``BuiltShape`` stand-in — the rail reads these three."""

    def __init__(self, role, polygon, ref=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)


def _square(x0=0.0, y0=0.0, w=10.0):
    return Polygon([(x0, y0), (x0 + w, y0), (x0 + w, y0 + w), (x0, y0 + w)])


def _layout():
    return _Layout([_Shape("apron", _square()),
                    _Shape("junction", _square(20.0)),
                    _Shape("runway", _square(40.0), ref="09/27")])


# ── the rail FAILS on every kind of solve-consumed mutation ─────────────

def test_added_shape_fails():
    lay = _layout()
    gf.freeze(lay)
    lay.shapes.append(_Shape("apron", _square(60.0)))
    with pytest.raises(GeometryFreezeViolation) as exc:
        gf.assert_frozen(lay, "twin")
    assert "shape COUNT changed" in str(exc.value)
    assert "3 -> 4" in str(exc.value)


def test_dropped_shape_fails():
    lay = _layout()
    gf.freeze(lay)
    lay.shapes.pop()
    with pytest.raises(GeometryFreezeViolation):
        gf.assert_frozen(lay, "twin")


def test_moved_vertex_fails():
    """A MOVE with the vertex count intact — the snap/weld family."""
    lay = _layout()
    gf.freeze(lay)
    lay.shapes[0].polygon = Polygon(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.5, 10.0)])
    with pytest.raises(GeometryFreezeViolation) as exc:
        gf.assert_frozen(lay, "twin")
    assert "vertex POSITIONS moved" in str(exc.value)
    assert "shape index 0" in str(exc.value)


def test_inserted_vertex_fails():
    """The densify / conformance-weld family: same outline, more nodes."""
    lay = _layout()
    gf.freeze(lay)
    lay.shapes[1].polygon = Polygon(
        [(20.0, 20.0), (25.0, 20.0), (30.0, 20.0),
         (30.0, 30.0), (20.0, 30.0)])
    with pytest.raises(GeometryFreezeViolation) as exc:
        gf.assert_frozen(lay, "twin")
    assert "vertex count" in str(exc.value)


def test_rerole_fails():
    """A re-role changes which law prices the shape — solve-consumed."""
    lay = _layout()
    gf.freeze(lay)
    lay.shapes[0].role = "groundside_pavement"
    with pytest.raises(GeometryFreezeViolation) as exc:
        gf.assert_frozen(lay, "twin")
    assert "role/ref" in str(exc.value)


def test_reordering_shapes_fails():
    """Order IS the signature: ``_build_node_list`` interns ring vertices
    in ``layout.shapes`` order, so a reorder relabels the whole index
    space even though every polygon survives."""
    lay = _layout()
    gf.freeze(lay)
    lay.shapes[0], lay.shapes[1] = lay.shapes[1], lay.shapes[0]
    with pytest.raises(GeometryFreezeViolation):
        gf.assert_frozen(lay, "twin")


def test_second_freeze_on_moved_geometry_fails():
    """``freeze`` is idempotent on unchanged geometry and a REFUSAL on
    changed geometry — a caller cannot re-freeze its way out."""
    lay = _layout()
    gf.freeze(lay)
    gf.freeze(lay)                       # idempotent
    lay.shapes.append(_Shape("apron", _square(60.0)))
    with pytest.raises(GeometryFreezeViolation):
        gf.freeze(lay)


# ── the rail PASSES on everything it deliberately does not cover ────────

def test_unchanged_layout_passes():
    lay = _layout()
    gf.freeze(lay)
    gf.assert_frozen(lay, "twin")


def test_altitudes_are_not_frozen():
    """The solve's whole job is to move altitudes.  Freezing them would
    refuse the solve itself."""
    lay = _layout()
    gf.freeze(lay)
    lay.shapes[0].node_altitudes = [1.0, 2.0, 3.0, 4.0]
    lay.shapes[1].altitude = 42.0
    gf.assert_frozen(lay, "twin")


def test_presolve_stores_are_not_frozen():
    """``gap_fill_presolve`` / ``adjacent_ground_presolve`` hold solver
    variables that lie on NO ring, so they cannot change the graph — the
    adjacent-ground construction legitimately writes its store AFTER the
    freeze point."""
    lay = _layout()
    gf.freeze(lay)
    lay.gap_fill_presolve = [{"spine": [(1.0, 1.0)], "values": None}]
    lay.adjacent_ground_presolve = [{"shape": lay.shapes[0], "fill": []}]
    gf.assert_frozen(lay, "twin")


def test_unfrozen_layout_is_a_no_op():
    """Importing the module must never change a build that does not
    freeze — ``assert_frozen`` on a virgin layout is one ``getattr``."""
    gf.assert_frozen(_layout(), "twin")


# ── the published one-graph accessors are rail-checked ──────────────────

def test_frozen_band_returns_the_published_band():
    lay = _layout()
    gf.freeze(lay)
    band = object()
    gf.publish(lay, nodes=[(0.0, 0.0)], bucket_to_idx={0: 0},
               ctx="ctx", graph="G", band=band)
    assert gf.frozen_band(lay, "twin") is band
    assert gf.frozen_graph(lay, "twin") == ([(0.0, 0.0)], {0: 0}, "ctx", "G")


def test_frozen_band_refuses_after_a_mutation():
    """THE POINT OF THE ACCESSOR: a band derived from geometry that has
    since moved must never be handed out."""
    lay = _layout()
    gf.freeze(lay)
    gf.publish(lay, nodes=[], bucket_to_idx={}, ctx="ctx", graph="G",
               band=object())
    lay.shapes[0].polygon = _square(0.0, 0.0, 11.0)
    with pytest.raises(GeometryFreezeViolation):
        gf.frozen_band(lay, "twin")
    with pytest.raises(GeometryFreezeViolation):
        gf.frozen_graph(lay, "twin")


def test_accessors_are_none_without_a_publication():
    lay = _layout()
    gf.freeze(lay)
    assert gf.frozen_band(lay, "twin") is None
    assert gf.frozen_graph(lay, "twin") is None


def test_clear_lifts_the_rail_and_drops_the_graph():
    """Phase [6] emission is ADDITIVE and lawful, so the rail is lifted
    once the solve has run — and the stale graph goes with it, because
    the two ``final_grade_projection`` builds legitimately rebuild on
    mutated rings."""
    lay = _layout()
    gf.freeze(lay)
    gf.publish(lay, nodes=[], bucket_to_idx={}, ctx="ctx", graph="G",
               band=object())
    assert gf.is_frozen(lay)
    gf.clear(lay)
    assert not gf.is_frozen(lay)
    lay.shapes.append(_Shape("graded_strip", _square(60.0)))
    gf.assert_frozen(lay, "twin")        # no rail, no refusal
    assert gf.frozen_band(lay, "twin") is None
    gf.clear(lay)                        # idempotent


def test_empty_and_degenerate_polygons_do_not_crash_the_signature():
    lay = _Layout([_Shape("apron", None),
                   _Shape("junction", Polygon())])
    gf.freeze(lay)
    gf.assert_frozen(lay, "twin")
    lay.shapes[0].polygon = _square()
    with pytest.raises(GeometryFreezeViolation):
        gf.assert_frozen(lay, "twin")
