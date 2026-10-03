"""#148 — a held pad's NEAR-MISS frontage contacts join its hold set.

flat-pad spec v2 §2 / §4; RULINGS 2026-09-30bd (the residual named at the
flatpad128v3 merge), 30bb F4 (``pad_frontage_level`` deleted for held pads:
the datum is the pad's one level, 30l (1)).  A held §20 pad held only its
shared rim; the soft apron it fronts across a sub-metre sliver
(``pads.frontage_contacts``) was priced and could step (HECA
``frontage_near_miss`` 4 -> 10 CRITICAL rows).

The fixture: a runway, an apron ``apronA`` the §20 pad ``padB`` shares its
south rim with, and a second apron ``apronC`` standing 0.6 m east of the pad
(no shared vertex: a near-miss frontage).  The ground under ``apronC`` is
0.5 m higher than under the pad, so a priced coupling loses to the DEM.

* the near-miss contact is in the block's hold set (one derivation, the
  set the §2 interval reads) and sits on the datum within ``hard_tol_m``
  after the solve, beside a rim contact;
* a near-miss contact the datum cannot reach (pinned 10 m up) makes the
  block RESIDUAL there — priced, reported as ``pad_frontage_infeasible`` —
  with the hard set settled: no step dumped elsewhere.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.no_step import hold_pass
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design

RUN_LEN = 1600.0
HALF_W = 22.5
GAP_X = 240.6          # apronC's west edge; padB's east edge is x = 240


class _Dem:
    provenance = {"synthetic": "nearmiss148"}

    def z(self, x: float, y: float) -> float:
        if y <= HALF_W:
            return 700.0
        return 700.0 + 0.002 * x + (0.5 if x > 240.3 else 0.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _airport(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 2 * HALF_W, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
             (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(-300.0, HALF_W, 300.0, 180.0), (),
             None, None, "airside", "apron", {}),
        # the §20 conforming pad (800 m², under cluster_pad_min_m2): its
        # south rim is apronA's
        Cell(2, "building", "padB", _rect(200.0, 180.0, 240.0, 200.0), (),
             None, None, "airside", "pad", {}),
        # a second apron sharing the pad's west rim, so the rim contacts
        # outnumber the near-miss ones (the residual datum is their median)
        Cell(4, "apron", "apronD", _rect(160.0, 180.0, 200.0, 220.0), (),
             None, None, "airside", "apron", {}),
        # a near-miss frontage 0.6 m east of the pad, no shared vertex
        Cell(3, "apron", "apronC", _rect(GAP_X, 182.0, 280.0, 198.0), (),
             None, None, "airside", "apron", {}),
    ]


def _arm(law, **design):
    d0 = law.tables.emit.design
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit,
                                     design=_dc.replace(d0, **design))))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def built(law):
    from auto_patch_v2.model.platform import HELD
    airport = _airport(law)
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    held = {k: dict(v) for k, v in HELD.items()}
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs, held


@pytest.fixture()
def registry(built):
    from auto_patch_v2.model.platform import HELD
    HELD.clear()
    HELD.update({k: dict(v) for k, v in built[2].items()})
    yield HELD


def _near(pm, law):
    from auto_patch_v2.constraints.pads import frontage_contacts
    near_m = float(law.tables.structures.building_pad.frontage_near_miss_m)
    return [(e, j, pid, d) for e, j, pid, d, _b, _f in frontage_contacts(pm, law)
            if pm.faces[pid].ref == "padB" and d <= near_m]


def _solve(pm, cs, lw):
    sol, rep = solve_design(pm, cs, lw, hold=hold_pass(pm, lw))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return np.asarray(sol.z, float), rep


def test_the_near_miss_contact_joins_the_hold_set(law, built, registry):
    from auto_patch_v2.constraints.platform import hold_sets
    pm, _cs, _h = built
    assert registry.get("padB", {}).get("conforming"), "padB is a held §20 pad"
    near = _near(pm, law)
    assert near, "the fixture carries a near-miss frontage"
    sets = {p: set(w) for p, _dv, w, _n, _r in hold_sets(pm, law)}
    es = {e for e, *_r in near}
    assert es <= sets["padB"]
    assert set(registry["padB"]["near_miss_contacts"]) == es
    # a fired edge's FAR endpoint is not in the gap and is not held
    from auto_patch_v2.constraints.pads import frontage_contacts
    far = {e for e, _j, pid, d, _b, _f in frontage_contacts(pm, law)
           if pm.faces[pid].ref == "padB" and e not in es}
    assert far and not (far & sets["padB"])


def test_rim_and_near_miss_contacts_sit_on_the_datum(law, built, registry):
    from auto_patch_v2.model.platform import datum_vertices
    pm, cs, _h = built
    lw = _arm(law, staged_solve=True)
    z, _rep = _solve(pm, cs, lw)
    tol = float(lw.tables.emit.design.hard_tol_m)
    D = z[datum_vertices(pm, lw)["padB"]]
    rim = {v for f in pm.faces.values() if f.ref in ("apronA", "apronD")
           for r in (f.ring, *f.holes) for v in pm.ring_vertices(r)}
    pad = {v for f in pm.faces.values() if f.ref == "padB"
           for r in (f.ring, *f.holes) for v in pm.ring_vertices(r)}
    assert rim & pad, "the pad shares rim contacts with apronA / apronD"
    assert max(abs(z[v] - D) for v in rim & pad) <= tol + 1e-6
    near = _near(pm, law)
    assert max(abs(z[e] - D) for e, *_r in near) <= tol + 1e-6


def test_an_unreachable_near_miss_contact_is_a_reported_needs_split(law, built,
                                                                  registry):
    """Round 5 (owner 2026-10-02, RULINGS 2026-10-02ah (1)): the datum is a
    FREE column; the rim is pinned at 700.5 m and the near-miss frontage
    (apronC) 1 m up, so NO single D serves the block.  The solve keeps the
    datum where the rim's welds hold it, the elastic LP releases ONLY the
    near-miss weld (pad tier; never an apron cap), and the record names the
    block ``needs_split`` with the released contact — the owner's
    two-pads-with-a-cliff class, reported for the base-profile split."""
    from auto_patch_v2.constraints.platform import _conforming_records
    pm, cs, _h = built
    lw = _arm(law, staged_solve=True)
    near = sorted(e for e, *_r in _near(pm, law))
    pad = {v for f in pm.faces.values() if f.ref == "padB"
           for r in (f.ring, *f.holes) for v in pm.ring_vertices(r)}
    rim = sorted(v for v in pad if any(pm.faces[q].ref in ("apronA", "apronD")
                                       for q in pm.vertices[v].incident_faces))
    assert len(rim) > len(near)
    src = Source("fixture", "nearmiss148 twin anchor", ())
    pins = [Pin(v, 700.5, src) for v in rim] + [Pin(q, 701.5, src) for q in near]
    z, rep = _solve(pm, ConstraintSet.from_rows([*cs.rows(), *pins]), lw)
    tol = float(lw.tables.emit.design.hard_tol_m)
    rec = {r["ref"]: r for r in _conforming_records(pm, lw, z)}["padB"]
    assert rec["needs_split"] and rec["released"] >= 1
    # the datum sits at ONE of the two levels the welds can meet (the
    # elastic LP's pick), never between them, and every weld at that level
    # is held
    D = rec["datum"]
    near_tol = 0.05       # the elastic LP's own residual on the kept level (3 dp record)
    assert min(abs(D - 700.5), abs(D - 701.5)) <= near_tol, D
    kept = rim if abs(D - 700.5) <= near_tol else near
    assert max(abs(z[v] - D) for v in kept) <= near_tol
    rel = {tuple(k) for k in rec["released_ll"]}
    lost = near if kept is rim else rim
    assert {tuple(pm.vertices[q].key) for q in lost} & rel
    # nothing but the pad's own hold was relaxed for it
    from auto_patch_v2.solve.feasibility import HARD_CONFLICT
    conf = [r for r in HARD_CONFLICT if "frontage_hold" not in r["row"]
            and "building_pad" in r["row"]]
    assert not conf, conf
    assert any("frontage_hold" in r["row"] for r in HARD_CONFLICT)