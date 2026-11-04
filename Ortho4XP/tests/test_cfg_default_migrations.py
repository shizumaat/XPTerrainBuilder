"""Twin of O4_Cfg_Default_Migrations: an automatically stored OLD default
is raised once; a value set by hand is never changed."""

import O4_Cfg_Default_Migrations as M
import O4_Cfg_Vars


def _cfg(tmp_path, body):
    path = tmp_path / "XPTerrainBuilder.cfg"
    path.write_text(body, encoding="utf-8", newline="\n")
    return str(path)


def test_registry_default_is_the_new_one():
    for var, (_old, new) in M.CHANGED_DEFAULTS.items():
        assert str(O4_Cfg_Vars.cfg_vars[var]["default"]) == new


def test_stored_old_default_is_raised_once(tmp_path):
    path = _cfg(tmp_path, "zone_list=[]\nmasks_width=100\n")
    lines = M.migrate_changed_defaults(path)
    assert lines and "masks_width" in lines[0]
    text = open(path, encoding="utf-8").read()
    assert "masks_width=500" in text and "zone_list=[]" in text
    # The user now sets 100 by hand: never rewritten again.
    open(path, "w", encoding="utf-8", newline="\n").write("masks_width=100\n")
    assert M.migrate_changed_defaults(path) == []
    assert "masks_width=100" in open(path, encoding="utf-8").read()


def test_value_chosen_by_hand_is_kept(tmp_path):
    for value in ("250", "[100, 200, 300]"):
        path = _cfg(tmp_path, "masks_width=%s\n" % value)
        (tmp_path / "XPTerrainBuilder.cfg.defaults").unlink(missing_ok=True)
        assert M.migrate_changed_defaults(path) == []
        assert "masks_width=%s" % value in open(path, encoding="utf-8").read()


def test_missing_file_is_a_no_op(tmp_path):
    assert M.migrate_changed_defaults(str(tmp_path / "none.cfg")) == []
