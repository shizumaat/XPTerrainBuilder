"""ISSUE #1275 — no emitted face ring is a bow-tie, and none ships silently.

KMCI's terminal + garage pad (``building26/b0``, ``b1``) and the plateau
aprons it fronts shipped self-intersecting (segment i crossing segment i+2
on their shared edge, 39.2996647, -94.7192985 and 39.3000385, -94.7224811);
``O4_Vector_Map.include_patches`` dropped the rings at verbosity 2 and the
mesh kept the raw DEM under them, a +5.8 m ridge across the gate apron.

THE MINT, measured on the KMCI capture: the planar map's faces are all
valid (0 of 2,642 invalid); ``emit.osm_adapter.merge_sub_spacing`` folded
them — collapsing a sub-spacing pair moves a ring edge onto the survivor,
and the moved edge crossed the ring two segments back.  The twins below
hold the three answers: the merge refuses a folding pair, the emitted
patch's closed ways are all polygons the mesh keeps, and the verify stage
fails the airport on a folded ring.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.emit.osm_adapter import WeldReport, merge_sub_spacing, render_patch
from auto_patch_v2.emit.ring_fold import FAMILY_RING_FOLD, folded, ring_folds, ring_is_simple
from auto_patch_v2.emit.surface import GradedSurface, SurfaceFace, SurfaceVertex
from auto_patch_v2.law import Law

M_LAT = 111_320.0
ORIGIN = (39.2996, -94.7229)

#: THE KMCI HOOK in metres: the ring runs A -> B -> C (a 1 m step out and
#: up, as building26's edge does) and back down past B to D, with E 0.4 m
#: west of D.  D -> E is a sub-spacing pair; E survives (the lower
#: coordinate), and the edge C -> E crosses A -> B: the bow-tie.
HOOK = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (1.2, -5.0), (0.8, -5.0),
        (0.0, -10.0), (-20.0, -10.0), (-20.0, 20.0)]
D, E = 3, 4


@pytest.fixture
def law():
    return Law.for_airport("KMCI")


def _ll(x: float, y: float) -> tuple[float, float]:
    k = M_LAT * math.cos(math.radians(ORIGIN[0]))
    return (ORIGIN[0] + y / M_LAT, ORIGIN[1] + x / k)


def _surface(pts, role="building", ref="building26/b1") -> GradedSurface:
    verts = tuple(SurfaceVertex(i, _ll(*p), 304.89) for i, p in enumerate(pts))
    return GradedSurface(icao="TEST", ruleset="faa", origin=ORIGIN,
                         crs="+proj=tmerc +lat_0=39.2996 +lon_0=-94.7229",
                         identity_dp=11, vertices=verts,
                         faces=(SurfaceFace(1, role, ref, tuple(range(len(pts))), (),
                                            "airside"),),
                         breaklines=(), provenance={})


def test_the_hook_is_simple_and_its_merge_folds_it():
    """The fixture IS the class: the ring as the planar map hands it over
    is simple; the sub-spacing merge alone makes the bow-tie."""
    assert ring_is_simple(HOOK)
    assert math.dist(HOOK[D], HOOK[E]) < 0.5
    pxy = dict(enumerate(HOOK))
    assert folded([list(range(len(HOOK)))], {D: E}, pxy) == [0]
    assert folded([list(range(len(HOOK)))], {}, pxy) == []


def test_the_merge_refuses_a_pair_that_folds_a_ring(law):
    """A MERGE NEVER FOLDS A RING: the pair stays as written, the refusal
    is counted, and the ring the patch carries is simple."""
    rep = WeldReport()
    out = merge_sub_spacing(_surface(HOOK), law, rep)
    assert rep.fold_refused == 1
    assert rep.merged == 0
    assert len(out.faces[0].ring) == len(HOOK)
    assert ring_folds(out) == []


def test_a_pair_that_folds_nothing_still_merges(law):
    """The refusal reads the fold, not the pair: the same 0.4 m pair on a
    straight run of the ring merges as before."""
    pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (5.2, 10.0), (4.8, 10.0),
           (0.0, 10.0)]
    rep = WeldReport()
    out = merge_sub_spacing(_surface(pts), law, rep)
    assert rep.merged == 1 and rep.fold_refused == 0
    assert len(out.faces[0].ring) == len(pts) - 1


def _closed_ways(text: str) -> dict[str, list[tuple[float, float]]]:
    root = ET.fromstring(text)
    nodes = {n.get("id"): (float(n.get("lon")), float(n.get("lat")))
             for n in root.iter("node")}
    out = {}
    for w in root.iter("way"):
        refs = [nd.get("ref") for nd in w.iter("nd")]
        if len(refs) >= 4 and refs[0] == refs[-1]:
            out[w.get("id")] = [nodes[r] for r in refs]
    return out


def test_every_closed_way_of_the_emitted_patch_is_a_polygon_the_mesh_keeps(law):
    """THE TWIN OVER THE EMIT: the merge then the writer, read back the way
    ``include_patches`` reads a patch (``Polygon(way).is_valid and
    .area``) — no closed way would be dropped."""
    surf = merge_sub_spacing(_surface(HOOK), law, WeldReport())
    text, _ways, _nodes = render_patch(surf, law)
    ways = _closed_ways(text)
    assert ways
    for wid, pts in ways.items():
        pg = Polygon(pts)
        assert pg.is_valid and pg.area > 0.0, f"way {wid} would be dropped"


def test_ring_folds_names_a_bowtie_face():
    """The emit-stage reading: one row per non-simple ring, naming it."""
    bow = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
    rows = ring_folds(_surface(bow))
    assert len(rows) == 1
    assert "building26/b1" in rows[0]["way_a"]


def test_verify_fails_the_airport_on_a_folded_ring():
    """An invalid ring never ships silently: the verify stage turns the
    emit stage's ``ring_folds`` into a DEFECT, which the app driver and the
    harness both fail the airport on."""
    from auto_patch_v2.pipeline.verify_stage import Verdict, install
    v = Verdict(rows={}, defects={}, under_floor={},
                preference={"over_preference": 0, "rows": 0, "max_grade": 0.0},
                census_s=0.0, wall_s={})
    report = {"ring_folds": [{"way_a": "building building26/b1 face 344",
                              "reading": "ring is not a simple ring",
                              "magnitude_m": 0.0, "site_ll": []}]}
    install("TEST", v, False, report, {}, lambda _m: None, 0.0)
    assert report["verify"]["defects"] == {FAMILY_RING_FOLD: 1}
    clean: dict = {"ring_folds": []}
    install("TEST", v, False, clean, {}, lambda _m: None, 0.0)
    assert clean["verify"]["defects"] == {}


def test_include_patches_names_a_dropped_ring_at_verbosity_zero(monkeypatch):
    """The mesh's last line of defence is LOUD: a patch ring it cannot take
    is an ERROR naming the patch file and the way, never a verbosity-2
    "Skipping invalid patch polygon." (#1275)."""
    import O4_UI_Utils as UI
    import O4_Vector_Map as VM
    said: list[str] = []
    monkeypatch.setattr(UI, "loud_warning", lambda *a: said.append(" ".join(map(str, a))))
    dt = {"w": {"-10349": {"role": "building", "ref": "building26/b1"}}}
    VM._say_dropped_patch_ring("KMCI_auto.patch.osm", "-10349", dt, "not a valid polygon")
    assert len(said) == 1
    assert "ERROR" in said[0] and "KMCI_auto.patch.osm" in said[0]
    assert "-10349" in said[0] and "building26/b1" in said[0]


# --- issue #1606: a SHORE WELD move never folds a ring -----------------------

#: THE KRNT SLIVER in metres (runway 3's zone-2 strip, 47.5005308,
#: -122.2164140): the ring's far edge S0 -> S1 runs 0.2 m off the shore and
#: snaps onto the water's two vertices; the spike R stands 0.3 m off the
#: same water edge, mid-edge, and the weld projects it onto that edge —
#: onto the ring's own snapped far edge: a self-touch the mesh drops.
SLIVER = [(0.0, 1.2), (20.0, 1.2), (20.0, -10.0), (11.0, -10.0), (10.0, 0.7),
          (9.0, -10.0), (0.0, -10.0)]
R = 4
SHORE = ((0.0, 1.0), (20.0, 1.0))


def _weld(pts):
    from auto_patch_v2.emit.osm_adapter import weld_to_shore
    rep = WeldReport()
    out = weld_to_shore(_surface(pts, role="graded_strip",
                                 ref="adjacent_ground:runway:3:zone2#9"),
                        Law.for_airport("KMCI"),
                        [(_ll(*SHORE[0]), _ll(*SHORE[1]))], rep)
    return out, rep


def test_the_weld_alone_folds_the_sliver(monkeypatch):
    """The fixture IS the class: with the refusal off, the weld's snap +
    projection turn the simple sliver into a ring the mesh drops."""
    import auto_patch_v2.emit.osm_adapter as oa
    assert ring_is_simple(SLIVER)
    monkeypatch.setattr(oa, "refuse_moves_that_fold", lambda *a, **k: [])
    out, rep = _weld(SLIVER)
    assert rep.snapped == 2 and rep.projected == 1
    assert len(ring_folds(out)) == 1


def test_the_weld_refuses_the_move_that_folds_a_ring():
    """A WELD MOVE NEVER FOLDS A RING: the projection is refused, R keeps
    its coordinate and is counted left beside the shore; the snaps stand."""
    out, rep = _weld(SLIVER)
    assert ring_folds(out) == []
    assert rep.weld_refused == 1
    assert rep.snapped == 2 and rep.projected == 0 and rep.stranded == 1
    vll = {v.id: v.ll for v in out.vertices}
    assert vll[R] == _ll(*SLIVER[R])
    assert vll[0] == _ll(*SHORE[0])


def test_a_projection_that_folds_nothing_still_lands():
    """The refusal reads the fold, not the move: with the far edge 3 m off
    the shore the same spike is projected onto the water edge as before."""
    pts = [(0.0, 3.0), (20.0, 3.0)] + SLIVER[2:]
    out, rep = _weld(pts)
    assert rep.weld_refused == 0 and rep.projected == 1
    assert ring_folds(out) == []
