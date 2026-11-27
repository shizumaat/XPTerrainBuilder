"""#2206: THE SHEET'S GEOMETRY ONCE PER STAGED SOLVE (``solve/assembly_memo``).

On ``test_collarlag302``'s synthetic pad: inside a scope a second assembly
on the same map and sheet takes the triangles and the Laplacian already
read, and its problem is the one a fresh assembly builds; a stage's map
carrying other targets (``dataclasses.replace``) still hits; another sheet
is read again (one slot) while its faces' triangles are kept; outside a
scope nothing is held; and the staged solve's surface is bit-identical
with the memo on and off."""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
from auto_patch_v2.solve import assembly_memo as M
from auto_patch_v2.solve import design_assemble, solve_design
from auto_patch_v2.solve import rows as R
from auto_patch_v2.solve.design import DesignReport
from auto_patch_v2.solve.design_roles import bend_roles
from test_collarlag302 import built, problem  # noqa: F401
from test_unitplatform_platform import bank_law, law  # noqa: F401


def _problem_of(base) -> tuple:
    r = base.rows
    return (r.r, r.c, r.v, r.b, list(r.owner), base.red.col.tolist(),
            [(t, h) for t, h, _row in base.one], [(t, h) for t, h, _row in base.eqs],
            base.hard, base.pad_flat, base.one_way,
            None if base.body is None else (base.body.r, base.body.c, base.body.v, base.body.b))


def _counted(monkeypatch, name):
    calls = []
    real = getattr(R, name)

    def run(*a, **k):
        calls.append(1)
        return real(*a, **k)
    monkeypatch.setattr(R, name, run)
    return calls


def test_a_second_assembly_in_a_scope_is_served_and_equal(problem, bank_law, monkeypatch):  # noqa: F811
    pm, cs = problem
    fresh = _problem_of(design_assemble.assemble(pm, cs, bank_law, DesignReport()))
    bend = set(bend_roles(bank_law))
    fid = min(f.id for f in pm.faces.values() if f.role in bend)
    some = set(R._face_triangles(pm, fid)[0])                    # a stage's drop set
    tri = _counted(monkeypatch, "_face_triangles")
    lap = _counted(monkeypatch, "_cotangent_laplacian")
    pm2 = _dc.replace(pm, taxi_trend_z=dict(pm.taxi_trend_z))   # a retarget's map
    with M._scope():
        a = _problem_of(design_assemble.assemble(pm, cs, bank_law, DesignReport()))
        n_tri = len(tri)
        assert n_tri > 0 and len(lap) == 1
        b = _problem_of(design_assemble.assemble(pm2, cs, bank_law, DesignReport()))
        assert (len(tri), len(lap)) == (n_tri, 1)                 # nothing read again
        d = design_assemble.assemble(pm, cs, bank_law, DesignReport(), drop=some)
        assert len(lap) == 2 and len(tri) == n_tri                # a new sheet, old faces
        design_assemble.assemble(pm, cs, bank_law, DesignReport())
        assert len(lap) == 3                                      # one slot: read again
    assert a == fresh and b == fresh
    # it died with the scope
    assert M._SCOPE.memo is None
    assert _problem_of(d) == _problem_of(
        design_assemble.assemble(pm, cs, bank_law, DesignReport(), drop=some))
    assert len(lap) == 4                                          # no scope: read again


def test_the_staged_solve_is_bit_identical_with_the_memo_off(problem, bank_law):  # noqa: F811
    pm, cs = problem
    on = solve_design(pm, cs, bank_law)[0]
    off = solve_design.__wrapped__(pm, cs, bank_law)[0]      # no scope: every piece read
    assert np.array_equal(np.asarray(on.z), np.asarray(off.z))
