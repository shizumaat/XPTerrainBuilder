"""#1710: the tree objects the RECORDED 3D upgrade turns into point forests
are planned out of the object stage (``pack_forests.converted_objects`` /
``without_converted``): the DSF write drops every row and every body of
them, so cutting them only wrote body files no DSF row named (MMUN's
Cancun pack: 3,840 of 22,421)."""
from __future__ import annotations

import json

from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import pack_forests as PF
from auto_patch_v2.airport.file_hash import sha256_file
from auto_patch_v2.model.placement import BACKUP_SUFFIX, PROVENANCE_FILENAME
from auto_patch_v2.model.rebake import Member, RebakePlan, Unit

TREE = "Objects/trees_flat.obj"
SPECIES = "lib/vegetation/trees/evergreen/kapok_*.for"


def _pack(tmp_path, renames, *, sha=None):
    dsf = tmp_path / "+21-087.dsf"
    dsf.write_bytes(b"live")
    (tmp_path / ("+21-087.dsf" + BACKUP_SUFFIX)).write_bytes(b"pristine")
    pristine = sha or sha256_file(str(dsf) + BACKUP_SUFFIX)
    rec = {"dsfs": {dsf.name: {PF.RECORD_KEY: PF.record(pristine, renames, 1, "t")}}}
    (tmp_path / PROVENANCE_FILENAME).write_text(json.dumps(rec))
    B.invalidate_memo()
    return str(dsf)


def test_only_the_recorded_tree_objects_are_converted(tmp_path):
    dsf = _pack(tmp_path, {TREE: SPECIES, "Objects/flat.for": "lib/g8/x.for"})
    assert PF.converted_objects(dsf) == {TREE}, "a .for rename is no object"


def test_a_record_of_another_pristine_file_converts_nothing(tmp_path):
    assert PF.converted_objects(_pack(tmp_path, {TREE: SPECIES}, sha="ff")) == set()


def test_no_backup_converts_nothing(tmp_path):
    dsf = tmp_path / "+21-087.dsf"
    dsf.write_bytes(b"live")
    assert PF.converted_objects(str(dsf)) == set()


def _member(i, res):
    return Member(f"dsf:obj{i}", res, res, res, 0.0)


def test_the_plan_loses_the_converted_members_and_lists_them_skipped():
    plan = RebakePlan("ZZZZ", "p", "/p", (
        Unit("unit:0", (1.0, 2.0), 0.0, (_member(0, TREE), _member(1, "Objects/hangar.obj"))),
        Unit("unit:1", (1.0, 2.0), 0.0, (_member(2, "Objects\\trees_flat.obj"),)),
    ), (("Objects/stock.obj", "stock"),), {})
    out = PF.without_converted(plan, frozenset({TREE}))
    assert [[m.id for m in u.members] for u in out.units] == [["dsf:obj1"]]
    assert dict(out.skipped)[TREE] == PF.CONVERTED_SKIP
    assert dict(out.skipped)["Objects/stock.obj"] == "stock"
    assert PF.without_converted(plan, frozenset()) is plan
    assert PF.without_converted(plan, frozenset({"Objects/none.obj"})) is plan
