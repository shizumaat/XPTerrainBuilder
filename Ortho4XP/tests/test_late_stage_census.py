"""Twins for spec §55 (15) rule B — THE CENSUS LEARNS THE FLOOR through the
sidecar's ``late_stage`` record (``{"floor_m", "followers"}``): the node
predicate (``check_grade.late_stage_unknown_nodes``), the floor in the three
families that price a pavement pair at a grade (``within_shape``,
``pavement_over_road_cap``, ``cross_shape``), ``cross_shape``'s declared
step, the ONE NUMBER the stage widens by and publishes, the frame twin
against the stage's own unknowns — and the ``hard_conflict`` siding."""
from __future__ import annotations

import inspect
import math
import pickle
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_harness import (_PVC_LAT, _PVC_LON, _families, _pavcap_patch,  # noqa: E402,F401
                          _sloped_rect, cg)

ROLE = "groundside_pavement"
STAGE = {"late_stage": {"floor_m": 1.0, "followers": ["small_roads:-7"]}}


def _way(cg, wid, ref, nids, role=ROLE):
    return cg.Way(wid, role, ref, "", list(nids), [0.0] * len(nids), {"ref": ref, "role": role})


def test_the_unknown_nodes_are_those_only_gap_parts_and_published_followers_carry(cg):
    ways = [_way(cg, "a", "gap:3/s0/lot", ["n1", "n2", "n3"]),
            _way(cg, "b", "pav37", ["n3", "n4"], "apron"),
            _way(cg, "c", "small_roads:-7", ["n2", "n5"], "service_road"),
            _way(cg, "d", "small_roads:-8", ["n6", "n5x"], "service_road")]
    got = cg.late_stage_unknown_nodes(ways, STAGE["late_stage"])
    assert got == {"n1", "n2", "n5"}             # n3 is the apron's: a constant
    assert cg.late_stage_unknown_nodes(ways, None) == set()
    assert cg.late_stage_floor_m(STAGE["late_stage"]) == 1.0
    assert cg.late_stage_floor_m(None) == 0.0


def test_the_key_is_a_registered_law_input_on_both_sides(cg):
    from auto_patch_v2.emit import osm_adapter as oa
    assert "late_stage" in oa.SIDECAR_KEYS
    assert cg.SIDECAR_LAW_KEYS["late_stage"] == "late_stage"
    assert "late_stage" not in cg.SIDECAR_EVIDENCE_KEYS


def test_a_part_chord_inside_the_floor_is_priced_by_neither_grade_family(cg, tmp_path):
    """12 % over 10 m inside one gap part: 1.2 m against ``0.08·10 + 1.0``.
    Without the record (no last stage) the pair is priced as before; a
    STANDING lot at the same slope stays priced with the record."""
    part = [(ROLE, _sloped_rect(0.12), "gap:3/s0/lot")]
    bare = _families(cg, _pavcap_patch(tmp_path, name="bare", rings=part))
    assert bare["within_shape"] and bare["pavement_over_road_cap"]
    fo = _families(cg, _pavcap_patch(tmp_path, name="floor", rings=part, sidecar=STAGE))
    assert fo["within_shape"] == [] and fo["pavement_over_road_cap"] == []
    lot = _families(cg, _pavcap_patch(tmp_path, name="lot", sidecar=STAGE,
                                      rings=[(ROLE, _sloped_rect(0.12), "dsf:pol10")]))
    assert lot["within_shape"] and lot["pavement_over_road_cap"]


def test_a_part_chord_beyond_the_floor_stays_priced(cg, tmp_path):
    """Two points over ``cap + floor / d`` on a 10 m chord — the floor is
    one floor per chord, never a licence."""
    over = cg.PAVEMENT_ROAD_CAP + STAGE["late_stage"]["floor_m"] / 10.0 + 0.02
    fo = _families(cg, _pavcap_patch(tmp_path, name="over", sidecar=STAGE,
                                     rings=[(ROLE, _sloped_rect(over), "gap:3/s0/lot")]))
    assert fo["within_shape"] and fo["pavement_over_road_cap"]


def _two(z_b, gap=0.45):
    a = [(0.0, 0.0, 20.0), (10.0, 0.0, 20.0), (10.0, 8.0, 20.0), (0.0, 8.0, 20.0)]
    b = [(10.0 + gap, 0.0, z_b), (20.0, 0.0, z_b), (20.0, 8.0, z_b), (10.0 + gap, 8.0, z_b)]
    return a, b


def test_cross_shape_takes_the_floor_between_two_unknowns(cg, tmp_path):
    """A lot and its ramp 0.45 m apart, 0.5 m apart in level: over the cap
    on the chord, inside the floor."""
    a, b = _two(20.5)
    rings = [(ROLE, a, "gap:3/s0/lot"), (ROLE, b, "gap:3/s0/ramp0")]
    bare = _families(cg, _pavcap_patch(tmp_path, name="xbare", rings=rings))
    assert bare["cross_shape"]
    fo = _families(cg, _pavcap_patch(tmp_path, name="xfloor", rings=rings, sidecar=STAGE))
    assert fo["cross_shape"] == []


def test_cross_shape_reads_the_declared_step_across_a_knife(cg, tmp_path):
    """Two step parts across a knife (within the family's 0.5 m proximity),
    3 m apart in level: a declared joint
    of that step between them and the pair is the joint's; an under-
    declared joint leaves the excess priced."""
    a, b = _two(23.0)
    rings = [(ROLE, a, "gap:3/s0"), (ROLE, b, "gap:3/s1")]
    mlat, mlon = 111_320.0, 111_320.0 * math.cos(math.radians(_PVC_LAT))

    def joint(step):
        pts = [[_PVC_LAT + y / mlat, _PVC_LON + 10.225 / mlon] for y in (-1.0, 9.0)]
        return {**STAGE, "terrace_joints": [{"points": pts, "step_m": step}]}
    bare = _families(cg, _pavcap_patch(tmp_path, name="kbare", rings=rings, sidecar=STAGE))
    assert bare["cross_shape"], "3 m over 0.45 m is no floor weld"
    fo = _families(cg, _pavcap_patch(tmp_path, name="kjoint", rings=rings, sidecar=joint(3.0)))
    assert fo["cross_shape"] == []
    low = _families(cg, _pavcap_patch(tmp_path, name="klow", rings=rings, sidecar=joint(0.5)))
    assert low["cross_shape"]


def test_the_stage_widens_by_and_publishes_one_number_read_at_one_site():
    """ONE NUMBER, ONE SITE: ``run_late_stage`` reads the law's floor once,
    hands THAT value to the widening and records THAT value for the
    sidecar; the generator's widened row and the census's allowance are
    then the same inequality, ``|dz| <= cap·d + floor``."""
    from auto_patch_v2.model.constraints import ConstraintSet, Diff, Source
    from auto_patch_v2.pipeline import late_stage as ls
    from auto_patch_v2.pipeline import publication as pub
    from auto_patch_v2.pipeline import stage_one_map as som
    src = inspect.getsource(ls.run_late_stage)
    assert src.count("pad_terrace_floor_m") == 1
    assert "widen_floor_m=floor_m" in src and '"floor_m": floor_m' in src
    head = "pavement_max_grade ceiling"
    row = Diff(1, 2, 0.08, 10.0, Source("ceiling", f"{head} (twin)", ("twin",)))
    f = 0.7
    cs, _dropped = som.late_constraints(ConstraintSet.from_rows([row]), {}, frozenset(),
                                        widen_heads=frozenset({head}), widen_floor_m=f)
    (wide,) = [r for r in cs.rows() if isinstance(r, Diff)]
    assert wide.cap * wide.d == pytest.approx(0.08 * 10.0 + f)
    rec = pub.late_stage({"floor_m": f, "followers": ["small_roads:-8", "small_roads:-7"]})
    assert rec == {"floor_m": f, "followers": ["small_roads:-7", "small_roads:-8"]}


def test_a_groundside_tier_relaxation_sides_groundside(cg):
    """Spec §55 (15): the last stage's relaxed rows are GROUNDSIDE-tier
    records; the pad and taxi tiers side as before."""
    recs = [{"tier": "groundside", "row": "gap_piece follows", "s_m": 1.2, "site": [30.0, 31.0]},
            {"tier": "taxi", "row": "pavement_max_grade ceiling", "s_m": 0.4, "site": [30.0, 31.0]},
            {"tier": "pad", "row": "flat", "s_m": 0.3, "site": [30.0, 31.0]}]
    rows = cg._check_hard_conflict(recs)
    assert [cg.row_side(r) for r in rows] == ["groundside", "airside", "airside"]
    assert [r.de_m for r in rows] == [1.2, 0.4, 0.3]


FRAME = Path("/Users/noah/XPTerrainBuilderData/.harness/frames/gaps7/ARM2")


@pytest.mark.skipif(not (FRAME / "solved.pkl").exists(), reason="frame gaps7/ARM2 not mounted")
def test_the_census_unknowns_are_the_stages_by_the_canonical_join(cg):
    """THE FRAME TWIN: over the nodes the census's ways carry, the predicate
    gives the stage's unknown vertices (``late_followers`` less
    ``late_fixed``), joined by the canonical 11-dp lat / lon — and beyond
    them only follower vertices the stage HELD AT IDENTITY (one emitted
    point with a constant; a handful, never a part's own vertex)."""
    from auto_patch_v2.model.planar import is_gap_ref
    from auto_patch_v2.pipeline import capture_state as cs_
    from auto_patch_v2.pipeline.stage_one_map import late_followers
    with open(FRAME / "solved.pkl", "rb") as fh:
        a = pickle.load(fh)
    if a.get(cs_.CAPTURE_STATE_KEY):
        cs_.install(a[cs_.CAPTURE_STATE_KEY])
    pm, fixed = a["pm"], set(a["late_fixed"])
    free, frep = late_followers(pm)
    nodes, ways = cg._parse_osm(FRAME / "HECA_auto.patch.osm")
    got = cg.late_stage_unknown_nodes(
        ways, {"floor_m": 1.0, "followers": frep["follower_ribbon_refs"]})
    to_ll = a["airport"].frame.transformers()[1]

    def key(lat, lon):
        return (round(float(lat), 11), round(float(lon), 11))
    of_ll = {key(*to_ll(*pm.vertices[v].xy)): v for v in pm.vertices}
    census = {key(*nodes[n]) for n in got}
    on_way = {key(*nodes[n]) for w in ways for n in w.nids if n in nodes}
    stage = {k for k, v in of_ll.items() if v in free and v not in fixed} & on_way
    assert len(stage) > 5000 and stage <= census
    extra = census - stage
    assert len(extra) <= 5
    for k in extra:
        v = of_ll[k]
        assert v in fixed and v in free
        assert not any(is_gap_ref(pm.faces[f].ref) for f in pm.vertices[v].incident_faces)
