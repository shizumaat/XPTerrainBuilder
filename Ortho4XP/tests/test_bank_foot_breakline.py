"""OWNER RULINGS 2026-09-13cp — AN OPEN BANK FOOT IS A BREAKLINE.

THE DEFECT, measured by scout ``v2lemd329`` on the owner's 1.0.329
+40-004 tile: since §37 (3) ("the bank is emitted where it is
load-bearing") the LEMD patch carried **105 OPEN ``bank_foot`` ways and 0
closed**.  ``O4_Vector_Map.include_patches`` gave ``PATCH_RING_MARKER``
only to a CLOSED way and inserted every open one as ``DUMMY`` (attr 0),
so the foot stopped being the INTERP_ALT flood barrier and the Dirichlet
datum of R18-1b and dropped out of ``patches_area``.  The bank annulus
came back with 15 valued vertices where the run before had 33,377, the
harmonic extension interpolated the vacated corridor from remote data,
and road ribbons authored at 588-590 m emitted at 568 — a 20.7 m canyon
at 40.465414, -3.5531888, 1,400 INTERP_ALT nodes off by more than 2 m
tile-wide.

Four laws, all headless and synthetic:

* THE MARKER — an open load-bearing run wears ``PATCH_RING_MARKER``.
* THE COVERAGE IS THE EMITTER'S — ``_close_open_foot`` is gone, and an
  open chain is LINEWORK the mesh never closes into a region itself.
* THE LOUD BAR — a collapsed annulus REFUSES with the counts.
* THE INTERIM BELT — a bare-INTERP_ALT (attr 8) input node leaves the
  free set of ``interpolate_free_interior_altitudes``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Mesh_Utils as MESH  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402

STRIDE = 6
BARE_INTERP_ALT = VECT.Vector_Map.dico_attributes["INTERP_ALT"]


# ── THE MARKER ────────────────────────────────────────────────────────
class TestOpenRunWearsTheMarker:
    def test_the_feature_register_is_what_a_CLOSED_way_would_wear(self):
        # SCOPE, stated once: the open ways whose CLOSED form is a patch
        # ring.  ``crown_spine`` / ``terrain_edge`` are always open and
        # never wore the marker — widening to them is a new law.
        from auto_patch_v2.emit import osm_adapter as OSM_A

        assert VMAP.OPEN_BREAKLINE_FEATURES == ("bank_foot", "structure_rim")
        assert OSM_A.BANK_FEATURE in VMAP.OPEN_BREAKLINE_FEATURES
        assert OSM_A.RIM_FEATURE in VMAP.OPEN_BREAKLINE_FEATURES
        assert OSM_A.RIDGE_FEATURE not in VMAP.OPEN_BREAKLINE_FEATURES
        assert OSM_A.EDGE_FEATURE not in VMAP.OPEN_BREAKLINE_FEATURES

    def test_the_source_gives_an_open_load_bearing_run_the_marker(self):
        # The insertion is inside a 400-line reader with no seam a unit
        # test can reach, so the LAW is asserted on the source: the open
        # branch must consult the register and reach PATCH_RING_MARKER.
        import inspect

        body = inspect.getsource(VMAP.include_patches)
        assert 'dt["w"].get(wayid, {}).get("o4_feature")' in body
        assert "in OPEN_BREAKLINE_FEATURES" in body
        head = body.split("in OPEN_BREAKLINE_FEATURES")[1][:400]
        assert "PATCH_RING_MARKER" in head
        assert '"DUMMY"' in head          # everything else still DUMMY

    def test_an_open_way_with_the_marker_carries_bit_8(self):
        # what the marker BUYS: the INTERP_ALT bit the plague stops on
        # and R18-1b's Dirichlet test reads.
        vector_map = VECT.Vector_Map()
        chain = numpy.array([[0.10, 0.10, 5.0], [0.20, 0.10, 6.0],
                             [0.20, 0.20, 7.0]])
        vector_map.insert_way(chain, VMAP.PATCH_RING_MARKER, check=True)
        markers = list(vector_map.data_edges.values())
        assert markers and all(m == VMAP.PATCH_RING_MARKER for m in markers)
        assert all(m & BARE_INTERP_ALT for m in markers)


# ── THE COVERAGE IS CLOSED AT THE EMITTER ─────────────────────────────
class TestTheMeshNeverClosesTheFootItself:
    def test_the_projection_closure_is_deleted(self):
        assert not hasattr(MESH, "_close_open_foot")
        assert not hasattr(MESH, "BANK_OPEN_CHAIN_AREA_WIDTHS")

    def test_the_OMIT_arm_is_a_law_key_not_an_env_gate(self):
        # ``auto_patch_v2`` reads NO environment by design
        # (``tests/auto_patch_v2/test_model.py``), so the owner's
        # "omit the bank_foot shapes altogether" arm is a law key.
        from auto_patch_v2.law import tables as T

        assert T.load_default().tables.emit.design.bank_omit is True   # owner RULINGS 2026-09-13cy (1.0.330 read)

    def test_the_emitter_emits_a_CLOSED_ring(self):
        # ``emit/bank.py`` is the single closure site: every bank_foot
        # breakline it writes repeats its first vertex.
        import inspect

        from auto_patch_v2.emit import bank as B

        body = inspect.getsource(B.with_bank)
        assert "tuple(ids) + (ids[0],)" in body
        assert "rep.open_chains += int(not closed)" not in body


# ── THE LOUD BAR ──────────────────────────────────────────────────────
class _Tile:
    lat, lon = 40, -4
    build_dir = "/nonexistent"


def _vertices(points):
    array = numpy.zeros(STRIDE * len(points))
    for index, (x, y) in enumerate(points):
        array[STRIDE * index] = x
        array[STRIDE * index + 1] = y
    return array


class TestTheLoudBar:
    """The 1.0.329 numbers refuse; the fixed ones do not."""

    def _arm(self, monkeypatch, annulus, stats):
        from shapely import geometry

        monkeypatch.setattr(MESH, "bank_annulus_polygon",
                            lambda tile: annulus, raising=True)
        MESH.BANK_RINGS_STATS.clear()
        MESH.BANK_RINGS_STATS.update(stats)
        return geometry

    def test_no_bank_foot_at_all_is_a_no_op(self, monkeypatch):
        from shapely import geometry

        self._arm(monkeypatch, geometry.Polygon(),
                  {"foot_closed": 0, "foot_open": 0, "design": 3})
        assert MESH.audit_bank_annulus(
            _Tile(), _vertices([(0.0, 0.0)]), [(0, 0, 0)], {}) == (0, 0)

    def test_the_1_0_329_numbers_REFUSE(self, monkeypatch):
        geom = self._arm(
            monkeypatch, __import__("shapely").geometry.box(0, 0, 1, 1),
            {"foot_closed": 0, "foot_open": 105, "design": 60})
        assert geom is not None
        pts = [(0.1 * i, 0.1 * i) for i in range(1, 10)]
        vertices = _vertices(pts)
        tris = [(i, i, i) for i in range(len(pts))]
        with pytest.raises(MESH.BankAnnulusCollapse) as caught:
            # 1 of 9 valued is 11 %, but the LEMD ratio is 15 / 33,377:
            # 0 valued of 9 candidates is the same collapse.
            MESH.audit_bank_annulus(_Tile(), vertices, tris, {})
        message = str(caught.value)
        assert "THE BANK ANNULUS COLLAPSED" in message
        assert "105 open bank_foot way(s)" in message
        assert "0 of 9" in message

    def test_an_empty_annulus_WITH_feet_present_refuses(self, monkeypatch):
        from shapely import geometry

        self._arm(monkeypatch, geometry.Polygon(),
                  {"foot_closed": 0, "foot_open": 105, "design": 60})
        with pytest.raises(MESH.BankAnnulusCollapse):
            MESH.audit_bank_annulus(
                _Tile(), _vertices([(0.5, 0.5)]), [(0, 0, 0)], {})

    def test_the_FIXED_numbers_pass(self, monkeypatch):
        from shapely import geometry

        self._arm(monkeypatch, geometry.box(0, 0, 1, 1),
                  {"foot_closed": 69, "foot_open": 0, "design": 60})
        pts = [(0.1 * i, 0.1 * i) for i in range(1, 10)]
        blend = {i: 100.0 for i in range(8)}
        assert MESH.audit_bank_annulus(
            _Tile(), _vertices(pts),
            [(i, i, i) for i in range(len(pts))], blend) == (8, 9)

    def test_warn_mode_reports_instead_of_refusing(self, monkeypatch):
        from shapely import geometry

        self._arm(monkeypatch, geometry.box(0, 0, 1, 1),
                  {"foot_closed": 69, "foot_open": 0, "design": 60})
        monkeypatch.setenv(MESH.BANK_ANNULUS_BAR_ENV, "warn")
        pts = [(0.1 * i, 0.1 * i) for i in range(1, 10)]
        assert MESH.audit_bank_annulus(
            _Tile(), _vertices(pts),
            [(i, i, i) for i in range(len(pts))], {}) == (0, 9)


# ── THE INTERIM BELT ──────────────────────────────────────────────────
def _write_poly(tmp_path, edges, nodes):
    node = tmp_path / "Data+40-004.node"
    poly = tmp_path / "Data+40-004.poly"
    node.write_text(
        f"{len(nodes)} 2 1 0\n" + "".join(
            f"{i + 1} {x:.9f} {y:.9f} 0.000000000\n"
            for i, (x, y) in enumerate(nodes)))
    poly.write_text(
        "0 2 1 0\n\n" + f"{len(edges)} 1\n"
        + "".join(f"{k + 1} {a} {b} {m}\n"
                  for k, (a, b, m) in enumerate(edges))
        + "\n0\n\n0\n")
    return poly


class TestTheRibbonBelt:
    def test_bare_INTERP_ALT_endpoints_are_read(self, tmp_path, monkeypatch):
        nodes = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        _write_poly(tmp_path, [(1, 2, BARE_INTERP_ALT),
                               (3, 4, VMAP.PATCH_RING_MARKER)], nodes)
        monkeypatch.setattr(
            MESH.FNAMES, "input_poly_file",
            lambda t: str(tmp_path / "Data+40-004.poly"))
        # the ROAD RIBBON's two nodes, and NOT the patch ring's
        assert MESH.interp_alt_ribbon_vertex_indices(_Tile()) == {0, 1}

    def test_an_unreadable_poly_is_empty_never_a_stopper(self, monkeypatch):
        monkeypatch.setattr(
            MESH.FNAMES, "input_poly_file", lambda t: "/nonexistent/x.poly")
        assert MESH.interp_alt_ribbon_vertex_indices(_Tile()) == set()

    def test_a_ribbon_node_in_the_Dirichlet_set_is_byte_unchanged(self):
        # THE PROMISE R18-1b's own docstring makes: a road ribbon comes
        # out byte-unchanged.  Free, the ribbon node is dragged to the
        # patch ring's value (the LEMD canyon); Dirichlet, it is not.
        vertices = numpy.zeros(STRIDE * 3)
        for index, (x, y, carried) in enumerate(
                [(0.0, 0.0, 600.0), (1.0, 0.0, 600.0), (0.5, 1.0, 589.0)]):
            vertices[STRIDE * index] = x
            vertices[STRIDE * index + 1] = y
            vertices[STRIDE * index + 5] = carried
        free_arm = vertices.copy()
        MESH.interpolate_free_interior_altitudes(free_arm, [(0, 1, 2)], {0, 1})
        assert free_arm[STRIDE * 2 + 5] == pytest.approx(600.0)
        belt_arm = vertices.copy()
        MESH.interpolate_free_interior_altitudes(
            belt_arm, [(0, 1, 2)], {0, 1, 2})
        assert belt_arm[STRIDE * 2 + 5] == pytest.approx(589.0)

    def test_the_caller_joins_the_ribbon_set_before_the_solve(self):
        import inspect

        body = inspect.getsource(MESH.post_process_nodes_altitudes)
        assert "interp_alt_ribbon_vertex_indices(tile)" in body
        assert "audit_bank_annulus(tile, vertices," in body


# ── the harmonic report NAMES the components with no authored vertex ──
def test_the_report_counts_isolated_COMPONENTS():
    vertices = numpy.zeros(STRIDE * 6)
    # one fan with Dirichlet data, one free triangle reaching none of it
    layout = [(0.0, 0.0, 10.0), (1.0, 0.0, 10.0), (0.5, 1.0, 99.0),
              (5.0, 5.0, 7.0), (6.0, 5.0, 7.0), (5.5, 6.0, 7.0)]
    for index, (x, y, carried) in enumerate(layout):
        vertices[STRIDE * index] = x
        vertices[STRIDE * index + 1] = y
        vertices[STRIDE * index + 5] = carried
    report = {}
    MESH.interpolate_free_interior_altitudes(
        vertices, [(0, 1, 2), (3, 4, 5)], {0, 1}, report=report)
    assert report["isolated"] == 3
    assert report["isolated_components"] == 1
