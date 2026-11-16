"""#1918 (owner RULINGS 2026-11-06d (1), 2026-11-15h): an object whose own row
the terrain reading leaves out of the DSF -- a ground shell no seat lays flat,
or a terrain object the user hid ("Hide terrain objects", ticked by default)
-- leaves the terrain solve exactly as A7's hidden concave shell does: read
as a floor or shell it owns no ground (``object_floor.owns_ground``); a rider
of its frame is not hidden (``ground_shell.hidden_by_pack``)."""
from __future__ import annotations

import dataclasses as dc
import types

import numpy as np
from auto_patch_v2.airport import ground_shell as GS
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import object_floor as OF
from test_cut_shell1883 import _section, _shell
from test_hanging_objects1298 import LAW, THICK, _placed, _write


def _drawing(law):
    """``law`` with A7's own hiding off: the shell is drawn unless the
    terrain reading hides its row."""
    st = law.tables.structures
    ob = dc.replace(st.tunnel.object, hide_concave_shells=False)
    st = dc.replace(st, tunnel=dc.replace(st.tunnel, object=ob))
    return dc.replace(law, tables=dc.replace(law.tables, structures=st))


def _model(oid, ground):
    return types.SimpleNamespace(id=oid, ground=ground)


def _read(tmp_path, model=None):
    """A concave shell A7 draws: it owns its ground unless the pack hides it."""
    shell = _placed(_shell(tmp_path), "dsf:obj1")
    shell.terrain_model = model
    rail = _placed(_write(tmp_path / "rail.obj", [_section([-1.0, 1.0], [-7.9, -7.9])]),
                   "dsf:obj3")
    floors, notes = OF.read_object_floors(
        [shell, rail], O.ResourceCache(THICK), _drawing(LAW), {},
        shells={"dsf:obj1": ("dsf:obj3", None)},
        ground=lambda xs, ys: np.full(len(xs), 100.0))
    return next(f for f in floors if f.object_id == "dsf:obj1"), notes


def test_a_shell_the_pack_hides_owns_no_ground(tmp_path):
    drawn, notes = _read(tmp_path)
    assert not drawn.hidden and OF.owns_ground(drawn), notes
    hid, _ = _read(tmp_path, _model("dsf:obj1", GS.HIDDEN))
    assert hid.hidden and not OF.owns_ground(hid) and OF.has_footprint(hid)
    kept, _ = _read(tmp_path, _model("dsf:obj1", GS.SEATED))
    assert not kept.hidden and OF.owns_ground(kept)


def test_a_rider_of_a_hidden_frame_is_not_hidden():
    assert GS.hidden_by_pack(types.SimpleNamespace(id="a", terrain_model=_model("a", GS.HIDDEN)))
    assert not GS.hidden_by_pack(types.SimpleNamespace(id="b",
                                                       terrain_model=_model("a", GS.HIDDEN)))
    assert not GS.hidden_by_pack(types.SimpleNamespace(id="a", terrain_model=None))
