"""Spec 2068 A2 F1: a unit's own fences join the one fence list
(``airport/unit_fence``).  A synthetic U fence authored over a slope reads
as one run whose columns carry the author's ground along its foot; a
retaining wall and an elevated run are refused; a DSF line facade is kept
untouched and a re-attach replaces the unit lines."""
from __future__ import annotations

import dataclasses as _dc
import types
import typing as _t

import numpy as np
import pytest
from auto_patch_v2.airport import unit_fence as uf
from auto_patch_v2.airport.rebake_plan import _mpd
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import EdgeLine

LAW = Law.for_airport("SYNT")
ML, MO = _mpd(0.0)


def _to_xy(lon, lat):
    return (lon * MO, lat * ML)


def _quad(a, b, panel):
    """One vertical panel from plan ``a`` to ``b`` (``(x, z, base)``)."""
    (x0, z0, b0), (x1, z1, b1) = a, b
    return [((x0, b0, z0), (x1, b1, z1), (x1, b1 + panel, z1)),
            ((x0, b0, z0), (x1, b1 + panel, z1), (x0, b0 + panel, z0))]


#: a U: west leg climbing south from the unit's zero, the south leg level,
#: the east leg falling
U = [(0.0, 0.0, 0.0), (0.0, 10.0, 4.6), (0.0, 20.0, 4.8), (20.0, 20.0, 4.8),
     (40.0, 20.0, 4.8), (40.0, 10.0, 4.6), (40.0, 0.0, 4.5)]


def _obj(path, cols, panel=3.5):
    tris = [t for a, b in zip(cols, cols[1:], strict=False) for t in _quad(a, b, panel)]
    vt, idx = [], []
    for t in tris:
        for p in t:
            idx.append(len(vt))
            vt.append(p)
    lines = ["A", "800", "OBJ", "", "TEXTURE none", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    lines += [f"IDX {i}" for i in idx]
    lines.append(f"TRIS 0 {len(idx)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return str(path)


@_dc.dataclass(frozen=True)
class _Airport:
    partition: _t.Any
    frame: _t.Any
    edge_lines: tuple = ()


def _airport(path, edge_lines=()):
    part = types.SimpleNamespace(comp=0, base_y=0.0, line=True)
    m = types.SimpleNamespace(id="dsf:obj1", resource="fence.obj", authored_path=path,
                              live_path=path, heading_deg=0.0, parts=(part,), origin=None)
    unit = types.SimpleNamespace(anchor=(0.0, 0.0), agl_m=0.0, members=(m,))
    return _Airport(types.SimpleNamespace(units=(unit,)),
                    types.SimpleNamespace(entry=lambda: _to_xy), tuple(edge_lines))


def test_a_u_fence_reads_one_run_with_its_foot(tmp_path):
    a = uf.attach_unit_fences(_airport(_obj(tmp_path / "u.obj", U)), load_rules(), LAW)
    (el,) = a.edge_lines
    assert el.unit == 0 and el.id == "unit:0:dsf:obj1#0" and not el.closed
    assert len(el.points) == len(U)
    # heading 0: authored x is east, authored -z is north
    got = sorted(zip(el.points, el.base_ys, strict=True))
    want = sorted(((x, -z), b) for x, z, b in U)
    for (p, b), (q, c) in zip(got, want, strict=True):
        assert p == pytest.approx(q, abs=0.05) and b == pytest.approx(c)
    assert el.panel_m == pytest.approx(3.5) and el.half_width_m == 0.0


def test_the_runs_split_at_a_branch_and_drop_short_ones():
    # a T: three arms from one column, one of them 3 m long
    P = np.array([[0, 0, 0], [0, 0, 3], [20, 0, 0], [20, 0, 3], [-20, 0, 0], [-20, 0, 3],
                  [0, 3, 0], [0, 3, 3]], dtype=float)
    tris = np.array([[0, 2, 3], [0, 3, 1], [0, 4, 5], [0, 5, 1], [0, 6, 7], [0, 7, 1]])
    runs = uf._unit_fence_runs(P, tris, 0.5, 6.0)
    assert sorted(len(r[0]) for r in runs) == [2, 2]
    assert all(r[1] == (0.0, 0.0) and r[2] == (3.0, 3.0) for r in runs)


@pytest.mark.parametrize("dy", [-2.0, 1.0])
def test_a_retaining_wall_and_an_elevated_run_are_not_read(tmp_path, dy):
    """Authored 2 m under its zero (a retaining wall, the step itself) or
    1 m over it (elevated): neither stands on the ground it would mark."""
    cols = [(x, z, dy) for x, z, _b in U]
    a = uf.attach_unit_fences(_airport(_obj(tmp_path / "w.obj", cols, 4.0)), load_rules(), LAW)
    assert a.edge_lines == ()


def test_dsf_lines_are_untouched_and_a_reattach_replaces_the_unit_lines(tmp_path):
    dsf = EdgeLine("dsf:line0", "f.fac", ((0.0, 0.0), (50.0, 0.0)), False, 0.0, 2.0, 0.0,
                   0.3, 0.1)
    path = _obj(tmp_path / "u.obj", U)
    a = uf.attach_unit_fences(_airport(path, edge_lines=(dsf,)), load_rules(), LAW)
    assert a.edge_lines[0] is dsf and len(a.edge_lines) == 2
    again = uf.attach_unit_fences(a, load_rules(), LAW)
    assert again.edge_lines == a.edge_lines
