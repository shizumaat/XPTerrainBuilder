"""Twin of ``airport/obj8_rest`` and ``parse_obj8(at_rest=...)`` (#1903,
#1984): an OBJ8's ``ANIM`` blocks evaluated at rest put each animated
range where the sim draws it -- a constant offset (the block
``obj8_split`` wraps a split body in) moves it and is no motion; a
keyframed dataref moves it at its rest value and is motion; a rotation
turns by the right-hand rule; a range hidden at rest is dropped.  The
authored parse is unchanged."""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch_v2.airport import obj8  # noqa: E402
from auto_patch_v2.airport.obj8_rest import HIDDEN, AnimStack  # noqa: E402


def _obj(tmp_path, anim: list[str]) -> str:
    """One still triangle at y = 0, then one triangle at (1, 0, 0) ..
    inside ``anim`` (the ANIM lines before its TRIS)."""
    rows = ["VT 0 0 0 0 1 0 0 0", "VT 1 0 0 0 1 0 0 0", "VT 0 0 1 0 1 0 0 0",
            "VT 1 0 0 0 1 0 0 0", "VT 2 0 0 0 1 0 0 0", "VT 1 0 1 0 1 0 0 0"]
    lines = ["I", "800", "OBJ", "", "POINT_COUNTS 6 0 0 6", *rows,
             "IDX 0", "IDX 1", "IDX 2", "IDX 3", "IDX 4", "IDX 5",
             "TRIS 0 3", "ANIM_begin", *anim, "TRIS 3 3", "ANIM_end"]
    p = tmp_path / "x.obj"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(p)


def _moved(g) -> np.ndarray:
    return g.vertices[g.solid[1]]


def test_constant_offset_moves_and_is_no_motion(tmp_path):
    p = _obj(tmp_path, ["ANIM_trans 0 1.2 0 0 1.2 0 0 0 none"])
    authored, rest = obj8.parse_obj8(p), obj8.parse_obj8(p, at_rest=True)
    assert authored.animated.tolist() == [False, True]
    assert _moved(authored)[:, 1].tolist() == [0.0, 0.0, 0.0]
    assert _moved(rest)[:, 1] == pytest.approx([1.2] * 3)
    assert rest.animated.tolist() == [False, False]
    assert rest.vertices[rest.solid[0]].tolist() == authored.vertices[authored.solid[0]].tolist()


def test_keyframes_read_the_rest_value_clamped_and_are_motion(tmp_path):
    p = _obj(tmp_path, ["ANIM_trans_begin sam/jetway/wheels", "ANIM_trans_key 1 0 0 0",
                        "ANIM_trans_key 0 0 5 0", "ANIM_trans_key -1 0 9 0", "ANIM_trans_end"])
    assert _moved(obj8.parse_obj8(p, at_rest=True))[:, 1] == pytest.approx([5.0] * 3)
    assert obj8.parse_obj8(p, at_rest=True).animated.tolist() == [False, True]
    half = obj8.parse_obj8(p, at_rest={"sam/jetway/wheels": 0.5})
    assert _moved(half)[:, 1] == pytest.approx([2.5] * 3)
    past = obj8.parse_obj8(p, at_rest={"sam/jetway/wheels": 7.0})
    assert _moved(past)[:, 1] == pytest.approx([0.0] * 3)


def test_rotation_is_right_handed_and_commands_post_multiply(tmp_path):
    p = _obj(tmp_path, ["ANIM_trans 10 0 0 10 0 0 0 0 none",
                        "ANIM_rotate 0 1 0 90 90 0 0 none"])
    v = _moved(obj8.parse_obj8(p, at_rest=True))
    # (1, 0, 0) turned +90 deg about +y is (0, 0, -1), then moved by +10 x
    assert v[0] == pytest.approx([10.0, 0.0, -1.0], abs=1e-9)


def test_a_range_hidden_at_rest_is_dropped():
    st = AnimStack()
    st.feed(b"ANIM_begin".split())
    st.feed(b"ANIM_hide 0 0 some/ref".split())
    assert st.pose() == HIDDEN
    st.feed(b"ANIM_show -1 1 some/ref".split())
    assert st.pose() is None and st.moving
    st.feed(b"ANIM_end".split())
    assert st.pose() is None and not st.moving


def test_hidden_range_has_no_triangles(tmp_path):
    p = _obj(tmp_path, ["ANIM_hide 0 1 some/ref"])
    assert obj8.parse_obj8(p, at_rest=True).solid.shape[0] == 1
    assert obj8.parse_obj8(p).solid.shape[0] == 2
