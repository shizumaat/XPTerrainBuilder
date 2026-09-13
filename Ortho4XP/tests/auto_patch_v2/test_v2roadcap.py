"""§37 A ROAD KEEPS ITS OWN LONGITUDINAL LAW; A ROAD FLIPS BY SHARE; THE
BANK IS EMITTED WHERE IT IS LOAD-BEARING — lane ``v2roadcap``'s twins
(owner RULINGS 2026-09-13q, KCLT items 5 / 7 / 8; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §37).

(1) Lateral contiguity exists so a road does not TEAR against the surface
    beside it — a LATERAL relation.  Binding the road's LONGITUDINAL law
    to it too made KCLT's east access road fall 1.4 % where its DEM falls
    9 % and end +14.22 m in the air.  The transverse cap takes the
    contiguous class's; the longitudinal cap stays the road's own 8 %.
(2) A LOT flips on an EDGE (§27, owner 12c); a STRIP-class face — a road
    by evidence — flips only on a SHARE of its perimeter.
(3) A foot station is emitted only where the ring stands more than
    ``bank_materiality_m`` off the DEM at its foot (twinned in
    ``test_v2bank.py`` beside the rest of the bank's law), and the mesh
    reads a load-bearing RUN of one ring as an open chain.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify import load_rules
from auto_patch_v2.constraints import roads
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.pipeline.publication import face_tags
from tests.auto_patch_v2.test_m3b import law, synthetic     # noqa: F401
from tests.auto_patch_v2.test_classify import _lot_flip_case


# ── §37 (1) LATERAL CONTIGUITY BINDS THE TRANSVERSE CAP ONLY ────────────

def test_the_contiguity_cap_is_the_transverse_cap_only(synthetic, law):  # noqa: F811
    """The road beside the apron keeps its own 8 % LONGITUDINAL cap and
    takes the apron's 1.5 % across its section."""
    airport, pm, _s, _cl = synthetic
    apron_cap = law.tables.common.roles["apron"].longitudinal
    road = next(f for f in pm.faces.values() if f.role == "service_road")
    caps = roads.road_law_caps(pm, law, airport)
    assert caps[road.id] == pytest.approx(apron_cap)       # the walk is unchanged
    rc = role_cap(law, "service_road")
    rows = [r for r in roads.road_within_shape(pm, law, airport)
            if f"face:{road.id}" in r.source.inputs]
    assert rows
    longitudinal = {round(r.cap, 6) for r in rows
                    if "longitudinal" in r.source.ruling}
    transverse = {round(r.cap, 6) for r in rows
                  if "cross_section" in r.source.ruling}
    assert longitudinal == {round(rc.longitudinal, 6)}     # 8 %, the road's own
    assert transverse == {round(min(rc.transverse, apron_cap), 6)}
    assert rc.longitudinal > apron_cap                     # the point of the twin


def test_the_way_tag_is_the_transverse_one(synthetic, law):   # noqa: F811
    """The contiguity cap reaches both censuses under
    ``o4_grade_law_cap_t``.  The bare ``o4_grade_law_cap`` binds a way's
    WHOLE within-shape reading (``check_grade._role_grade_limit``), which
    is the longitudinal law §37 (1) gives back to the road, so v2 must not
    stamp the contiguity cap there."""
    airport, pm, _s, _cl = synthetic
    road = next(f for f in pm.faces.values() if f.role == "service_road")
    tags = face_tags(pm, law, airport)
    assert "o4_grade_law_cap_t" in tags[road.id]
    assert "o4_grade_law_cap" not in tags[road.id]
    assert float(tags[road.id]["o4_grade_law_cap_t"]) == pytest.approx(
        law.tables.common.roles["apron"].longitudinal)


def test_the_census_reads_the_transverse_tag_and_only_it():
    """``check_grade`` composes the tag into the CROSS-SECTION cap and
    leaves the longitudinal reading alone — one law, both readers."""
    import importlib.util
    import pathlib
    import sys
    root = pathlib.Path(__file__).resolve().parents[2]
    name = "_cg_v2roadcap"
    cg = sys.modules.get(name)
    if cg is None:
        # registering in ``sys.modules`` BEFORE exec is what makes the
        # module's own imports (and its dataclasses) resolve
        spec = importlib.util.spec_from_file_location(
            name, root / "tools" / "check_grade.py")
        cg = importlib.util.module_from_spec(spec)
        sys.modules[name] = cg
        spec.loader.exec_module(cg)
    assert cg.LATERAL_CAP_T_TAG == "o4_grade_law_cap_t"

    class _W:
        tags = {"o4_grade_law_cap_t": "0.015", "role": "service_road"}
        apron_portion_runs = None

    assert cg._lateral_cap_t_tag(_W()) == pytest.approx(0.015)
    assert cg._lateral_cap_tag(_W()) is None
    # the LONGITUDINAL reading is the role's own, untouched by the tag
    assert cg._role_grade_limit(_W(), 0.05) == pytest.approx(
        cg.ROLE_GRADE_LIMITS["service_road"])
    # ... and the tag is applied where the cross-section cap is resolved
    src = pathlib.Path(root / "tools" / "check_grade.py").read_text()
    body = src.split("def _xsec_allowance(", 1)[1].split("\n        if role0", 1)[0]
    assert "_lateral_cap_t_tag(w)" in body


# ── §37 (2) A ROAD FLIPS BY SHARE, A LOT BY EDGE ────────────────────────

def test_a_through_road_grazing_an_apron_stays_a_road():
    """KCLT shapeID 791 in miniature: a long strip touching an apron
    laterally for ~2 % of its perimeter is a road passing an apron."""
    from shapely.geometry import box
    rules = load_rules()
    assert rules.lot.road_airside_edge_frac == 0.2
    road = box(0.0, 0.0, 8.0, 580.0)                  # perimeter 1,176 m
    apron = box(8.0, 100.0, 200.0, 112.0)             # 12 m of lateral edge
    n, _r, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("service_road", "r791", road, None, {}),
    ])
    assert n == 0 and roles[1] == "service_road"      # 12 m of 1,176 = 1 %
    assert 12.0 > rules.lot.airside_edge_min_m        # the EDGE test alone passes


def test_a_lot_still_flips_on_the_edge_alone():
    """§27 is unchanged for the LOT class: an edge, not a share (owner
    12c is about a shape that SITS against airside pavement)."""
    from shapely.geometry import box
    rules = load_rules()
    lot = box(0.0, 0.0, 8.0, 580.0)                   # the same 1,176 m perimeter
    apron = box(8.0, 100.0, 200.0, 112.0)
    n, _r, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("parking_lot", "pav791", lot, None, {"kind": "lot"}),
    ])
    assert n == 1 and roles[1] == "apron"


def test_an_apron_side_lane_keeps_its_flip():
    """LEMD's 61 apron-side service-road faces run ALONGSIDE their apron
    (lateral edges to 828 m): a share, so the §27 flip stands."""
    from shapely.geometry import box
    road = box(0.0, 0.0, 8.0, 580.0)
    apron = box(8.0, 0.0, 200.0, 580.0)               # the full 580 m flank
    n, _r, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("service_road", "lane", road, None, {}),
    ])
    assert n == 1 and roles[1] == "apron"             # 580 m of 1,176 = 49 %


# ── §37 (3) THE MESH READS A LOAD-BEARING RUN ──────────────────────────

def test_the_mesh_closes_an_open_foot_chain_into_its_ribbon():
    """``_bank_rings_from_patches`` read only CLOSED ways, so a
    load-bearing RUN would have taken the whole ring's annulus out of
    ``bank_annulus_blend_values``.  An open chain is closed into the strip
    of ground between it and the design coverage; an implausible closure
    is refused, which leaves those vertices to the harmonic extension —
    this module's standing rule, never the other way round."""
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(
        __file__).resolve().parents[2] / "src"))
    import O4_Mesh_Utils as M
    from shapely.geometry import box

    cov = box(0.0, 0.0, 1.0, 1.0)
    chain = [(-0.001, 0.0), (-0.001, 0.5), (-0.001, 1.0)]
    ribbon = M._close_open_foot(chain, cov)
    assert ribbon is not None and ribbon.area == pytest.approx(0.001, rel=1e-6)
    # a chain that runs far from the coverage sweeps an implausible area
    far = [(-5.0, 0.0), (-5.0, 1.0)]
    assert M._close_open_foot(far, cov) is None
    assert M._close_open_foot([(0.0, 0.0)], cov) is None
