"""#1726 option B EXPERIMENT (owner 2026-11-02T23:28Z "Try B so I can see
it"): a structure member the terrain adapted to, whose SUPPORTS would be
buried, is raised with its whole origin frame so the supports' densest
foot plane stands at grade (``airport/support_raise``).  Synthetic pack in
``tmp_path``; no airport, no corpus.  OFF by default: nothing moves."""
from __future__ import annotations

import dataclasses as _dc
import types

from auto_patch_v2.airport import pack_partition as PPT
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport import support_raise as SR
from auto_patch_v2.law import Law

LAW = Law.load()
Z = 100.0


def _law(on: bool):
    st = LAW.tables.structures
    bp = _dc.replace(st.building_pad, support_raise_members=on)
    return types.SimpleNamespace(tables=types.SimpleNamespace(
        structures=types.SimpleNamespace(building_pad=bp, placement=st.placement)))


def _boxes(tmp_path, name, boxes):
    """An OBJ8 of closed boxes ``(x0, y0, x1, y1)``, 0.3 m deep in z."""
    vt, idx = [], []
    faces = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))
    for x0, y0, x1, y1 in boxes:
        k = len(vt)
        vt += [(x0, y0, 0), (x1, y0, 0), (x1, y0, 0.3), (x0, y0, 0.3),
               (x0, y1, 0), (x1, y1, 0), (x1, y1, 0.3), (x0, y1, 0.3)]
        idx += [k + i for f in faces for i in f]
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    body += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    body += [f"IDX {i}" for i in idx]
    body.append(f"TRIS 0 {len(idx)}")
    (tmp_path / "objects").mkdir(exist_ok=True)
    (tmp_path / "objects" / name).write_text("\n".join(body) + "\n", encoding="utf-8",
                                             newline="\n")
    return "objects/" + name


def _row(path, lat=38.5, lon=-28.7):
    return types.SimpleNamespace(def_path=path, lat=lat, lon=lon, heading_deg=12.0,
                                 kind="OBJECT", elevation=None)


def _pack(tmp_path):
    # 25 poles 0.3 m square standing 6 m below the floor, three deep ones,
    # and a 40 m facade (not a support)
    poles = [(3.0 * k, -6.0, 3.0 * k + 0.3, 0.0) for k in range(25)]
    deep = [(3.0 * k + 1.5, -20.0, 3.0 * k + 1.8, 0.0) for k in range(3)]
    t = _boxes(tmp_path, "t.obj", poles + deep + [(0.0, -0.5, 40.0, 8.0)])
    m = _boxes(tmp_path, "inside.obj", [(0.0, 0.0, 10.0, 3.0)])
    o = _boxes(tmp_path, "other.obj", [(0.0, -6.0, 0.3, 0.0)])
    dump = types.SimpleNamespace(placements=[_row(t), _row(m), _row(o, lat=38.51)])
    plan = types.SimpleNamespace(skipped=((t, PPT.ADAPTED_SKIP),))
    return dump, plan


def test_the_knob_is_off_by_default(tmp_path):
    from auto_patch_v2.geom.foot_planes import support_lift_on
    assert support_lift_on(LAW, "support_raise_members") is False
    dump, plan = _pack(tmp_path)
    assert SR.raised_rows(dump, plan, lambda la, lo: Z, str(tmp_path), LAW, 0.3) == {}


def test_the_frame_rises_to_its_supports_densest_plane(tmp_path):
    dump, plan = _pack(tmp_path)
    got = SR.raised_rows(dump, plan, lambda la, lo: Z, str(tmp_path), _law(True), 0.3)
    # both rows of the adapted member's origin frame, not the other origin
    assert got == {0: Z + 6.0, 1: Z + 6.0}
    assert SR.LAST[dump.placements[0].def_path] == (6.0, 25, 28, 2)


def test_supports_already_at_grade_raise_nothing(tmp_path):
    dump, plan = _pack(tmp_path)
    # the terrain adapted to the poles: the ground under them is 6 m down
    got = SR.raised_rows(dump, plan, lambda la, lo: Z - 6.0 if abs(la - 38.5) > 1e-6 else Z,
                         str(tmp_path), _law(True), 0.3)
    assert got == {}


def test_a_raised_row_is_written_whole_at_the_frame_elevation(tmp_path):
    dump, _plan = _pack(tmp_path)
    rp = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())
    ss = types.SimpleNamespace(unit_seats=())
    conv, msl, _r, _c = PW.dump_rows(dump, rp, ss, (), lambda la, lo: Z, str(tmp_path),
                                     tol_m=0.02, raised={0: 106.0, 1: 106.0})
    seats = {m.index: (m.elevation, m.why) for m in msl}
    assert seats[0] == (106.0, SR.SUPPORT_RAISE) and seats[1] == (106.0, SR.SUPPORT_RAISE)
    assert not {c.index for c in conv} & {0, 1}


@_dc.dataclass(frozen=True)
class _U:
    members: tuple


@_dc.dataclass(frozen=True)
class _P:
    units: tuple


def test_without_rows_drops_the_raised_members():
    m = lambda i: types.SimpleNamespace(id=f"dsf:obj{i}")  # noqa: E731
    p = _P((_U((m(0), m(5))), _U((m(1),))))
    out = SR.without_rows(p, {1, 5})
    assert [[x.id for x in u.members] for u in out.units] == [["dsf:obj0"]]
    assert SR.without_rows(p, {}) is p
