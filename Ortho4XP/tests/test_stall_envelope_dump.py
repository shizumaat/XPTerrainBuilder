"""R1.3 attribution instrument twins (lane r1pins, 2026-09-03).

``_stall_envelope_gap(want_pred=True)`` hands out the predecessor trees of
the SAME two Dijkstras it already runs, so an offline reader can walk a
node's envelope value back to the anchor that set it; the default call is
unchanged.  ``_dump_envelope_inputs`` writes only under
``O4_STALL_ENVELOPE_DUMP`` and never touches ``z``.
"""
import numpy as np
import pytest

from auto_patch.elevation_per_surface.route_profile import one_solve as OS


def _chain():
    # 0 --(1.0)-- 1 --(1.0)-- 2 ; nodes 0 and 2 pinned 10 m apart:
    # infeasible at node 1 by 10 - 2 = 8 m.
    ei = np.asarray([0, 1], dtype=np.intp)
    ej = np.asarray([1, 2], dtype=np.intp)
    eb = np.asarray([1.0, 1.0])
    im = np.zeros(2, dtype=bool)
    wi = np.asarray([0.0, 0.5])     # node 0 pinned (never positive weight)
    wj = np.asarray([0.5, 0.0])     # node 2 pinned
    z = np.asarray([0.0, 5.0, 10.0])
    return ei, ej, eb, im, wi, wj, z


def test_want_pred_is_additive_and_walkable():
    ei, ej, eb, im, wi, wj, z = _chain()
    base = OS._stall_envelope_gap(np, ei, ej, eb, im, wi, wj, z, 3, [(0, 1)])
    assert "pred_upper" not in base
    assert base["infeasible"] == 3 and abs(base["max_gap"] - 8.0) < 1e-9
    det = OS._stall_envelope_gap(np, ei, ej, eb, im, wi, wj, z, 3, [(0, 1)],
                                 want_pred=True)
    assert np.allclose(det["gap"], base["gap"], equal_nan=True)
    assert set(det["anchors"].tolist()) == {0, 2}
    # walk node 1's upper (from the low anchor 0) and lower (from the
    # high anchor 2) predecessor chains back to the virtual source (=n).
    n = 3
    for key, anchor in (("pred_upper", 0), ("pred_lower", 2)):
        pred = det[key]
        cur = 1
        while int(pred[cur]) != n:
            cur = int(pred[cur])
        assert cur == anchor


def test_dump_is_env_gated(tmp_path, monkeypatch):
    ei, ej, eb, im, wi, wj, z = _chain()
    v = OS._stall_envelope_gap(np, ei, ej, eb, im, wi, wj, z, 3, [(0, 1)])
    monkeypatch.delenv("O4_STALL_ENVELOPE_DUMP", raising=False)
    OS._dump_envelope_inputs(np, ei, ej, eb, im, wi, wj, z, 3, [(0, 1)],
                             None, v, "exit")
    assert not list(tmp_path.iterdir())
    monkeypatch.setenv("O4_STALL_ENVELOPE_DUMP", str(tmp_path))
    z_before = z.copy()
    OS._dump_envelope_inputs(np, ei, ej, eb, im, wi, wj, z, 3, [(0, 1)],
                             None, v, "exit")
    files = list(tmp_path.glob("env*_exit_n3_e2.npz"))
    assert len(files) == 1
    got = np.load(files[0])
    assert int(got["infeasible"]) == 3 and np.array_equal(got["z"], z_before)
