"""#2144 P1: A DECK OF SEPARATE PLACED SPANS IS SEATED AS ONE CHAIN
(``airport/deck_chain``).

Synthetic and hermetic: hand-built span OBJs (a level span and one rising
0.3 m) placed end to end on a sloping ground, read back through the
engine's own reader."""
from __future__ import annotations

import math

import numpy as np
from auto_patch_v2.airport import deck_chain as DC


def _span(path, rise: float = 0.0, soffit: float = 8.0, length: float = 32.6,
          half: float = 5.2) -> str:
    """A box span from z 0 (its origin) to z -length, soffit rising by
    ``rise`` along it."""
    v = []
    for z, y in ((0.0, soffit), (-length, soffit + rise)):
        for x in (-half, half):
            v += [(x, y, z), (x, y + 3.0, z)]
    idx = [0, 1, 2, 1, 3, 2, 4, 6, 5, 5, 6, 7, 0, 4, 1, 1, 4, 5, 2, 3, 6, 3, 7, 6,
           1, 5, 3, 3, 5, 7, 0, 2, 4, 2, 6, 4]
    out = ["I", "800", "OBJ", "", "TEXTURE\tt.dds", f"POINT_COUNTS\t{len(v)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0 1 0\t0 0" for x, y, z in v]
    out += [f"IDX\t{q}" for q in idx] + ["", f"TRIS\t0 {len(idx)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def _row(tmp_path, n: int, gap: float = 0.6, heading: float = 0.0, ground=None):
    """``n`` spans end to end along ``heading``; each row's ``lat`` carries
    the test ground under its origin (``ground(k)``)."""
    flat = DC.piece_of(_span(tmp_path / "flat.obj"))
    rise = DC.piece_of(_span(tmp_path / "rise.obj", rise=0.3))
    out = []
    h = math.radians(heading)
    for k in range(n):
        s = k * (32.6 + gap)
        g = 0.0 if ground is None else ground(k)
        out.append(DC.Placed(k, "objects/span.obj", g, 0.0, heading,
                             (s * math.sin(h), s * math.cos(h)), rise if k % 2 else flat))
    return out


def _ground(la: float, lo: float) -> float:
    return la


def test_a_span_is_a_piece_and_a_cube_is_not(tmp_path):
    p = DC.piece_of(_span(tmp_path / "s.obj", rise=0.3))
    assert p is not None
    assert abs(p.lo[1] + 32.6) < 1e-6 and abs(p.hi[1]) < 1e-6
    assert abs(p.lo[3] - 8.3) < 1e-6 and abs(p.hi[3] - 8.0) < 1e-6
    assert abs(p.lo[2] - 10.4) < 1e-6
    assert DC.piece_of(_span(tmp_path / "c.obj", length=8.0)) is None


def test_spans_end_to_start_join_and_keep_their_authored_heights(tmp_path):
    placed = _row(tmp_path, 6, heading=30.0, ground=lambda k: 0.04 * k * 33.2)
    js = DC.joints(placed, DC.ChainLaw())
    assert len(js) == 5
    zero, rep = DC.chain_seats(placed, _ground, DC.ChainLaw())
    for i, j, si, sj in js:
        assert abs((zero[i] + si) - (zero[j] + sj)) < 1e-9     # no step at a joint
    assert len(rep["chains"]) == 1 and not rep["cut"]


def test_no_ground_seats_nothing(tmp_path):
    zero, _rep = DC.chain_seats(_row(tmp_path, 3), lambda la, lo: None, DC.ChainLaw())
    assert zero == {}


def test_a_gap_or_a_turn_is_no_joint(tmp_path):
    assert DC.joints(_row(tmp_path, 3, gap=2.5), DC.ChainLaw()) == []
    placed = _row(tmp_path, 2)
    turned = [placed[0], DC.Placed(1, "x", 0.0, 0.0, 40.0, placed[1].xy, placed[1].piece)]
    assert DC.joints(turned, DC.ChainLaw()) == []


def test_a_hole_under_one_piece_does_not_pull_the_chain(tmp_path):
    placed = _row(tmp_path, 9, ground=lambda k: -12.0 if k == 4 else 0.0)
    zero, _rep = DC.chain_seats(placed, _ground, DC.ChainLaw())
    assert min(zero.values()) > -1.5                           # the median, not the hole
    assert np.isfinite(list(zero.values())).all()
