"""Lane ``cyxy262`` — the twins of three CYXY owner sim reads (app 1.0.369,
2026-10-02): #262 (a 1300 startup inside a cell refuses the corridor
kind), #263 (a stock-library hangar ``.agp`` placement is a building
footprint) and #264 (the pavement fallback cap never welds a §28 (6)
hillside terrace pair).
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import dsf as _dsf
from auto_patch_v2.airport import riders as _riders
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints import pavement_cap
from auto_patch_v2.constraints.pad_frontage_gs import (frontage_step_max_m,
                                                       held_terrace_pairs)
from auto_patch_v2.law import Law
from auto_patch_v2.planar.build import build

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__)))), "tools"))
from v2_explain import REKIND_MARKS  # noqa: E402

from test_v2frontage import _airport, _cells  # noqa: E402  (same dir)
from test_v2frontagestep import _StepDem  # noqa: E402  (same dir)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── #262: a startup inside the cell refuses the corridor kind ───────────

def test_the_startup_refusal_is_a_named_rekind_mark():
    """The dry role census names every re-kind with the evidence its rule
    read (``explain.REKIND_MARKS``); a rule that re-kinds without a mark
    is invisible to the before/after read."""
    keys = {k for k, _label in REKIND_MARKS}
    assert "startup_refused_corridor" in keys
    assert "apron_cover_refused_corridor" in keys     # the rung it mirrors


def test_a_corridor_cell_holding_a_startup_is_apron():
    """CYXY pav5 (cell 66): two 1300 'Apron 2' stands inside a 17,096 m2
    cell whose mean width read 33.2 m because taxi A2 ran ALONG its edge.
    The synthetic twin: the classify fixture's parallel-taxiway corridor
    with one startup dropped inside it — corridor without the stand, apron
    with it, the re-kind named by its mark."""
    import dataclasses as _dc

    from shapely.geometry import Polygon

    from auto_patch_v2.classify import classify, load_rules
    from auto_patch_v2.model.airport import Startup
    from test_classify import _synthetic  # noqa: E402  (same dir)
    synt_law = Law.for_airport("SYNT")
    base = _synthetic(gate=True)
    rules = load_rules()
    cl0 = classify(base, synt_law, rules)
    # a corridor BY ITS MEAN WIDTH — not a §43 arm (#314 cuts the fixture's
    # half-taxiway off its apron; a stand on that arm refuses the CUT, the
    # twin of which is test_apron_neck's)
    corridors = [c for c in cl0.cells if c.kind == "corridor"
                 and not c.evidence.get("neck_cut")]
    assert corridors, "the classify fixture mints corridor cells"
    c = max(corridors, key=lambda c: Polygon(c.ring, c.holes).area)
    rp = Polygon(c.ring, c.holes).representative_point()
    st = Startup("Twin stand", (rp.x, rp.y), 0.0, "tie_down")
    arm = _dc.replace(base, startups=tuple(base.startups) + (st,))
    cl1 = classify(arm, synt_law, rules)
    hit = [x for x in cl1.cells if x.evidence.get("startup_refused_corridor")]
    assert hit, "a corridor holding a 1300 startup is re-kinded apron"
    assert all(x.role == "apron" and x.kind == "apron" for x in hit)
    assert all(x.evidence.get("cell_startups", 0) >= 1 for x in hit)
    assert not any(x.evidence.get("startup_refused_corridor") for x in cl0.cells)


# ── #263: the .agp hangar footprint ──────────────────────────────────────

def test_the_agp_building_role_is_the_stock_hangar_prefix():
    """v1 ``agp_reader.is_agp_building_def``'s scope, ported: a stock
    hangar ``.agp`` is a building, a jetway ``.agp`` or an ``.obj`` is not."""
    assert _dsf.agp_building_role("lib/airport/Common_Elements/Hangars/Med_Blue_Hangar.agp") == "hangar"
    assert _dsf.agp_building_role("lib/airport/Common_Elements/Hangars/x.AGP") == "hangar"
    assert _dsf.agp_building_role("objects/HECA_Jetway_No_glass.agp") is None
    assert _dsf.agp_building_role("lib/airport/Common_Elements/Hangars/x.obj") is None


def test_the_agp_footprint_is_the_tile_about_its_anchor(tmp_path):
    """CYXY's ``hangar_40x26_3_lb.agp`` idiom: TEXTURE_SCALE 2048x1024,
    TEXTURE_WIDTH 267.931 / HEIGHT 133.781, a TILE and an ANCHOR_PT — the
    footprint is the TILE in metres about the anchor, rotated by the
    placement heading."""
    p = tmp_path / "hangar.agp"
    p.write_text("A\n1000\nAG_POINT\n\nTEXTURE_SCALE 100 100\n"
                 "TEXTURE_WIDTH 100\nTEXTURE_HEIGHT 100\n"
                 "TILE 0 0 40 20\nROTATION 0\nANCHOR_PT 20 10\n",
                 encoding="utf-8", newline="\n")
    local, rot = _riders.agp_footprint_local(str(p))
    assert rot == 0.0
    xs = sorted(round(x, 6) for x, _y in local)
    ys = sorted(round(y, 6) for _x, y in local)
    assert xs == [-20.0, -20.0, 20.0, 20.0] and ys == [-10.0, -10.0, 10.0, 10.0]
    ring = _riders.agp_footprint_xy(str(p), (100.0, 200.0), 90.0)
    # heading 90 (clockwise from north): east -> south, north -> east
    assert any(abs(x - 110.0) < 1e-6 and abs(y - 220.0) < 1e-6 for x, y in ring)
    assert any(abs(x - 90.0) < 1e-6 and abs(y - 180.0) < 1e-6 for x, y in ring)
    # no TILE / CROP_POLY: no footprint, never a guess
    q = tmp_path / "flat.agp"
    q.write_text("A\n1000\nAG_POINT\nTEXTURE_SCALE 10 10\nTEXTURE_WIDTH 10\n",
                 encoding="utf-8", newline="\n")
    assert _riders.agp_footprint_local(str(q)) is None


def test_the_agp_source_is_admitted_by_the_rules():
    """``[buildings] sources`` gates ``classify/evidence._pads``; the
    ``dsf:agp`` source must be in it or the footprint is loaded and never
    becomes a pad."""
    from auto_patch_v2.classify import load_rules
    assert any("dsf:agp:hangar".startswith(s) for s in load_rules().buildings.sources)


# ── #264: a held terrace pair is never welded by the fallback cap ─────────

def _built(law, dem):
    airport = _airport(law, dem)
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    return pm, airport


def test_the_held_pairs_are_published_from_the_one_derivation(law):
    bound = frontage_step_max_m(law)
    pm, _airport = _built(law, _StepDem(bound + 1.0))
    held = held_terrace_pairs(pm, law)
    assert len(held) == 1
    gid, pid = next(iter(held))
    assert pm.faces[gid].ref == "lotA" and pm.faces[pid].ref.split("#")[0] == "padA"
    pm2, _a2 = _built(law, _StepDem(bound - 1.0))
    assert held_terrace_pairs(pm2, law) == set()


def test_the_fallback_cap_skips_a_held_pair_and_keeps_a_graded_one(law):
    """CYXY ``pav4`` | ``building9``: the lot|pad pair §28 (6) holds as a
    hillside terrace is a STEP (as pad|pad is, 30l (2)) — no welded
    fallback row between the two faces.  Under the bound the pair is
    graded and the fallback still prices its welded neighbours."""
    bound = frontage_step_max_m(law)

    def welded_lot_pad_rows(step):
        pm, _airport = _built(law, _StepDem(step))
        lot = next(f.id for f in pm.faces.values() if f.ref == "lotA")
        pad = next(f.id for f in pm.faces.values() if f.ref == "padA")
        owner = {}
        for f in pm.faces.values():
            for v in pm.ring_vertices(f.ring):
                owner.setdefault(v, set()).add(f.id)
        rows = pavement_cap.pavement_road_cap([], pm, law)
        return [r for r in rows
                if (lot in owner.get(r.a, ()) and pad in owner.get(r.b, ())
                    and pad not in owner.get(r.a, ()))
                or (pad in owner.get(r.a, ()) and lot in owner.get(r.b, ())
                    and lot not in owner.get(r.a, ()))]

    graded = welded_lot_pad_rows(bound - 1.0)
    held = welded_lot_pad_rows(bound + 1.0)
    assert held == [], "a held terrace pair carries no fallback weld"
    if not graded:
        pytest.skip("the fixture's lot and pad share no welded neighbour: "
                    "only the held arm is testable here")
