"""Twins for the scenery_packs.ini tidy-up (O4_Scenery_Packs_Tidy,
``O4_Scenery_Packs.insert_new_packs``; #1729 follow-up).

The rule — a pack the ini does not list yet is filed in its kind's group,
meshes BELOW every ortho so a newly installed mesh never hides our tiles —
lived in the Mac app only (``PackActionService.reconcile``).  It moved to
the engine so the Qt window (Windows, Linux) runs it too.  The golden cases
are the old Swift code's own output, captured before it was deleted; the
engine writes the same bytes, except that it never drops a row (the Mac's
removal of vanished packs stays in Swift) and keeps the file's last line
break where the Swift code wrote a stray blank line before an addition at
the end of the file.
"""

from __future__ import annotations

import pytest

import O4_Scenery_Packs as SP
import O4_Scenery_Packs_Tidy as TIDY
from test_mesh_order import _pack

# Golden cases: inputs, the old Swift reconcile's kinds and its output
# (PackActionService.reconcile, captured at b0b634315 before the rule
# moved).  ``swift_out`` is byte-for-byte what the Mac app wrote.
SWIFT_GOLDEN = {
    'g1': (
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         'SCENERY_PACK Custom Scenery/Alpha Airport/\n'
         'SCENERY_PACK *GLOBAL_AIRPORTS*\n'
         'SCENERY_PACK Custom Scenery/City Landmark/\n'
         'SCENERY_PACK Custom Scenery/Some Library/\n'
         'SCENERY_PACK Custom Scenery/zOrtho A/\n'
         'SCENERY_PACK Custom Scenery/zzz Mesh/'),
        [
            ('Alpha Airport', 'airport'),
            ('City Landmark', 'landmark'),
            ('Some Library', 'library'),
            ('zOrtho A', 'ortho'),
            ('zzz Mesh', 'mesh'),
            ('Beta Airport', 'airport'),
            ('New Overlay', 'landmark'),
            ('aOrtho New', 'ortho'),
        ],
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         'SCENERY_PACK Custom Scenery/Alpha Airport/\n'
         'SCENERY_PACK Custom Scenery/Beta Airport/\n'
         'SCENERY_PACK *GLOBAL_AIRPORTS*\n'
         'SCENERY_PACK Custom Scenery/City Landmark/\n'
         'SCENERY_PACK Custom Scenery/New Overlay/\n'
         'SCENERY_PACK Custom Scenery/Some Library/\n'
         'SCENERY_PACK Custom Scenery/zOrtho A/\n'
         'SCENERY_PACK Custom Scenery/aOrtho New/\n'
         'SCENERY_PACK Custom Scenery/zzz Mesh/')),
    'g2': (
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         'SCENERY_PACK Custom Scenery/Alpha Airport/\n'
         'SCENERY_PACK *GLOBAL_AIRPORTS*\n'
         'SCENERY_PACK Custom Scenery/City Landmark/\n'
         'SCENERY_PACK Custom Scenery/Some Library/\n'
         'SCENERY_PACK Custom Scenery/zOrtho A/\n'
         'SCENERY_PACK Custom Scenery/zzz Mesh/\n'),
        [
            ('Alpha Airport', 'airport'),
            ('City Landmark', 'landmark'),
            ('Some Library', 'library'),
            ('zOrtho A', 'ortho'),
            ('zzz Mesh', 'mesh'),
            ('New Mesh', 'mesh'),
            ('b Ortho', 'ortho'),
            ('A Ortho', 'ortho'),
            ('Lib2', 'library'),
            ('Odd', 'other'),
        ],
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         'SCENERY_PACK Custom Scenery/Alpha Airport/\n'
         'SCENERY_PACK *GLOBAL_AIRPORTS*\n'
         'SCENERY_PACK Custom Scenery/City Landmark/\n'
         'SCENERY_PACK Custom Scenery/Odd/\n'
         'SCENERY_PACK Custom Scenery/Some Library/\n'
         'SCENERY_PACK Custom Scenery/Lib2/\n'
         'SCENERY_PACK Custom Scenery/zOrtho A/\n'
         'SCENERY_PACK Custom Scenery/A Ortho/\n'
         'SCENERY_PACK Custom Scenery/b Ortho/\n'
         'SCENERY_PACK Custom Scenery/zzz Mesh/\n'
         '\n'
         'SCENERY_PACK Custom Scenery/New Mesh/')),
    'g3': (
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         'SCENERY_PACK Custom Scenery/zOrtho4XP_+39-077/\n'
         'SCENERY_PACK_DISABLED Custom Scenery/Gone Pack/\n'
         'SCENERY_PACK Custom Scenery/Unknown Thing/\n'
         'SCENERY_PACK_DISABLED Custom Scenery/Old Mesh/\n'),
        [
            ('zOrtho4XP_+39-077', 'ortho'),
            ('Old Mesh', 'mesh'),
            ('KBWI Airport', 'airport'),
            ('KBWI_Mesh (Verticalsim)', 'mesh'),
            ('Over', 'landmark'),
        ],
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         'SCENERY_PACK Custom Scenery/KBWI Airport/\n'
         'SCENERY_PACK Custom Scenery/Over/\n'
         'SCENERY_PACK Custom Scenery/zOrtho4XP_+39-077/\n'
         'SCENERY_PACK_DISABLED Custom Scenery/Old Mesh/\n'
         '\n'
         'SCENERY_PACK Custom Scenery/KBWI_Mesh (Verticalsim)/')),
    'g4': (
        None,
        [
            ('Apt', 'airport'),
            ('Mesh', 'mesh'),
            ('Ortho', 'ortho'),
        ],
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         '\n'
         'SCENERY_PACK Custom Scenery/Apt/\n'
         'SCENERY_PACK Custom Scenery/Ortho/\n'
         'SCENERY_PACK Custom Scenery/Mesh/')),
    'g5': (
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         'SCENERY_PACK Custom Scenery/Global Airports/\n'
         'SCENERY_PACK Custom Scenery/zOrtho4XP_+40-075/\n'
         'SCENERY_PACK Custom Scenery/Lib/\n'
         'SCENERY_PACK Custom Scenery/Mesh1/\n'
         'SCENERY_PACK Custom Scenery/Apt Late/\n'),
        [
            ('Global Airports', 'airport'),
            ('zOrtho4XP_+40-075', 'ortho'),
            ('Lib', 'library'),
            ('Mesh1', 'mesh'),
            ('Apt Late', 'airport'),
            ('New Apt', 'airport'),
            ('New Lib', 'library'),
            ('New Over', 'landmark'),
        ],
        ('I\n'
         '1000 Version\n'
         'SCENERY\n'
         '\n'
         'SCENERY_PACK Custom Scenery/New Apt/\n'
         'SCENERY_PACK Custom Scenery/Global Airports/\n'
         'SCENERY_PACK Custom Scenery/New Over/\n'
         'SCENERY_PACK Custom Scenery/New Lib/\n'
         'SCENERY_PACK Custom Scenery/zOrtho4XP_+40-075/\n'
         'SCENERY_PACK Custom Scenery/Lib/\n'
         'SCENERY_PACK Custom Scenery/Mesh1/\n'
         'SCENERY_PACK Custom Scenery/Apt Late/\n')),
}

# Where the engine's bytes differ from the Swift code's, and why.
_END = "SCENERY_PACK Custom Scenery/%s/"
ENGINE_DELTA = {
    # Keeps the last line break instead of a blank line before the mesh.
    "g2": [("zzz Mesh/\n\n" + _END % "New Mesh",
            "zzz Mesh/\n" + _END % "New Mesh" + "\n")],
    # Also never drops a row: the two packs not on disk stay listed.
    "g3": [("zOrtho4XP_+39-077/\nSCENERY_PACK_DISABLED Custom Scenery/Old Mesh/\n\n"
            + _END % "KBWI_Mesh (Verticalsim)",
            "zOrtho4XP_+39-077/\n"
            "SCENERY_PACK_DISABLED Custom Scenery/Gone Pack/\n"
            "SCENERY_PACK Custom Scenery/Unknown Thing/\n"
            "SCENERY_PACK_DISABLED Custom Scenery/Old Mesh/\n"
            + _END % "KBWI_Mesh (Verticalsim)" + "\n")],
    # No ini: X-Plane's header, then the packs, ending in a line break.
    "g4": [("SCENERY\n\n\n", "SCENERY\n\n"),
           (_END % "Mesh", _END % "Mesh" + "\n")],
}


def _expected(case):
    text = SWIFT_GOLDEN[case][2]
    for old, new in ENGINE_DELTA.get(case, ()):
        assert old in text
        text = text.replace(old, new)
    return text


def _install(tmp_path, ini, kinds):
    csd = tmp_path / "Custom Scenery"
    csd.mkdir()
    for name, _kind in kinds:
        (csd / name).mkdir()
    if ini is not None:
        (csd / SP.INI_FILENAME).write_bytes(ini.encode("utf-8"))
    return csd


def _read(csd):
    return (csd / SP.INI_FILENAME).read_bytes().decode("utf-8")


@pytest.mark.parametrize("case", sorted(SWIFT_GOLDEN))
def test_files_new_packs_as_the_mac_app_did(tmp_path, case):
    ini, kinds, _swift = SWIFT_GOLDEN[case]
    csd = _install(tmp_path, ini, kinds)
    reply = TIDY.tidy_scenery_packs(str(csd), dict(kinds))
    assert _read(csd) == _expected(case)
    listed = {name for name, _ in kinds if ini and "/%s/" % name in ini}
    assert sorted(reply["added"]) == sorted(
        name for name, _ in kinds if name not in listed)


def test_byte_equal_cases_need_no_delta():
    # g1 (no final line break) and g5 (every addition mid-file) are the
    # Swift bytes exactly.
    for case in ("g1", "g5"):
        assert case not in ENGINE_DELTA


def test_crlf_and_windows_paths_are_kept(tmp_path):
    csd = tmp_path / "Custom Scenery"
    csd.mkdir()
    for name in ("zOrtho4XP_+39-077", "Airport X", "KBWI_Mesh", "Somewhere Else"):
        (csd / name).mkdir()
    ini = ("I\r\n1000 Version\r\nSCENERY\r\n\r\n"
           "SCENERY_PACK Custom Scenery\\Airport X\\\r\n"
           "SCENERY_PACK *GLOBAL_AIRPORTS*\r\n"
           "SCENERY_PACK_DISABLED C:\\X-Plane 12\\Custom Scenery\\Somewhere Else\\\r\n"
           "SCENERY_PACK Custom Scenery\\zOrtho4XP_+39-077\\\r\n")
    (csd / SP.INI_FILENAME).write_bytes(ini.encode("utf-8"))
    kinds = {"zOrtho4XP_+39-077": "ortho", "Airport X": "airport",
             "KBWI_Mesh": "mesh", "Somewhere Else": "landmark"}
    reply = TIDY.tidy_scenery_packs(str(csd), kinds)
    assert reply["added"] == ["KBWI_Mesh"]
    assert _read(csd) == ini + "SCENERY_PACK Custom Scenery/KBWI_Mesh/\r\n"


def test_backs_up_once_and_writes_nothing_when_all_listed(tmp_path):
    ini = "I\n1000 Version\nSCENERY\n\nSCENERY_PACK Custom Scenery/A/\n"
    csd = _install(tmp_path, ini, [("A", "ortho"), ("B", "mesh")])
    backup = csd / (SP.INI_FILENAME + SP.BACKUP_SUFFIX)
    reply = TIDY.tidy_scenery_packs(str(csd), {"A": "ortho", "B": "mesh"})
    assert reply == {"added": ["B"], "backup": str(backup)}
    assert backup.read_bytes().decode() == ini
    after_first = _read(csd)
    (csd / "C").mkdir()
    TIDY.tidy_scenery_packs(str(csd), {"C": "mesh"})
    assert backup.read_bytes().decode() == ini, "the backup is the user's own ini"
    before = _read(csd)
    assert TIDY.tidy_scenery_packs(str(csd), {}) == {"added": [], "backup": ""}
    assert _read(csd) == before and after_first != before


def test_hidden_and_global_airports_folders_are_not_filed(tmp_path):
    csd = _install(tmp_path, "I\n1000 Version\nSCENERY\n\n",
                   [(".hidden", "other"), ("Global Airports", "airport")])
    assert TIDY.tidy_scenery_packs(str(csd), {})["added"] == []
    assert not (csd / (SP.INI_FILENAME + SP.BACKUP_SUFFIX)).exists()


def test_unknown_kinds_are_read_from_disk(tmp_path):
    csd = tmp_path / "Custom Scenery"
    csd.mkdir()
    # A base-mesh DSF and no terrain files, named for nothing: a mesh by
    # its header (the Mac scanner reads the same flag).
    _pack(csd, "Airport Ground", overlay=False)
    _pack(csd, "Roads", overlay=True)
    _pack(csd, "zOrtho4XP_+39-077", overlay=False)
    (csd / SP.INI_FILENAME).write_text(
        "I\n1000 Version\nSCENERY\n\n"
        "SCENERY_PACK Custom Scenery/zOrtho4XP_+39-077/\n",
        encoding="utf-8", newline="")
    assert TIDY._classify(str(csd), "Airport Ground") == "mesh"
    assert TIDY._classify(str(csd), "Roads") == "landmark"
    assert TIDY._classify(str(csd), "absent") is None
    reply = TIDY.tidy_scenery_packs(str(csd), {"zOrtho4XP_+39-077": "ortho"})
    assert reply["added"] == ["Roads", "Airport Ground"]
    lines = _read(csd).split("\n")
    ours = lines.index(_END % "zOrtho4XP_+39-077")
    assert lines.index(_END % "Roads") < ours < lines.index(_END % "Airport Ground")


def test_the_command_is_registered():
    import inspect

    from o4_engine import jsonl
    assert '"tidy_scenery_packs": tidy_scenery_packs' in inspect.getsource(jsonl)


def test_the_qt_survey_runs_it(monkeypatch, tmp_path):
    import inspect

    pytest.importorskip("PySide6")
    import O4_Qt_GUI as GUI

    calls = []
    monkeypatch.setattr(TIDY, "tidy_scenery_packs", lambda d, k: calls.append(
        (d, k)) or {"added": [], "backup": ""})

    class Pack:
        def __init__(self, name, kind):
            self.name, self.kind = name, kind

    GUI._tidy_scenery_packs(str(tmp_path), [Pack("M", "mesh"), Pack("O", "ortho")])
    assert calls == [(str(tmp_path), {"M": "mesh", "O": "ortho"})]
    source = inspect.getsource(GUI.MainWindow._refresh_scenery_packs)
    assert "_tidy_scenery_packs(scenery_dir, packs)" in source


# #1988: a new zOrtho4XP tile joins the user's own block of tile rows at
# its alphabetical place; with no tile row yet it goes to the bottom.
_HEAD = "I\n1000 Version\nSCENERY\n\n"


def _row(name, disabled=False):
    return "SCENERY_PACK%s Custom Scenery/%s/\n" % (
        "_DISABLED" if disabled else "", name)


def _tidy(tmp_path, body, kinds, tail="\n"):
    ini = _HEAD + body
    if not tail:
        ini = ini[:-1]
    csd = _install(tmp_path, ini, kinds)
    reply = TIDY.tidy_scenery_packs(str(csd), dict(kinds))
    return _read(csd), reply["added"]


_OTHER = [("Apt", "airport"), ("Lib", "library"), ("Mesh", "mesh")]
_T = "zOrtho4XP_%s"


@pytest.mark.parametrize("tail", ["\n", ""])
def test_new_tiles_join_the_block_mid_file(tmp_path, tail):
    body = (_row("Apt") + _row("Lib") + _row(_T % "+40-075")
            + _row(_T % "+42-071") + _row("Mesh"))
    tiles = [(_T % n, "ortho") for n in ("+40-075", "+42-071", "+41-073",
                                         "+43-070", "+39-077")]
    text, added = _tidy(tmp_path, body, _OTHER + tiles, tail)
    want = _HEAD + (
        _row("Apt") + _row("Lib") + _row(_T % "+39-077")
        + _row(_T % "+40-075") + _row(_T % "+41-073") + _row(_T % "+42-071")
        + _row(_T % "+43-070") + _row("Mesh"))
    assert text == (want if tail else want[:-1])
    assert sorted(added) == sorted(_T % n for n in ("+41-073", "+43-070",
                                                     "+39-077"))


def test_new_tiles_join_a_block_at_the_top(tmp_path):
    # The user keeps tiles above everything, airports included.
    body = _row(_T % "+40-075") + _row("Apt") + _row("Lib") + _row("Mesh")
    kinds = _OTHER + [(_T % "+40-075", "ortho"), (_T % "+41-073", "ortho")]
    text, _added = _tidy(tmp_path, body, kinds)
    assert text == _HEAD + (_row(_T % "+40-075") + _row(_T % "+41-073")
                            + _row("Apt") + _row("Lib") + _row("Mesh"))


def test_disabled_rows_are_part_of_the_block(tmp_path):
    body = (_row("Apt") + _row(_T % "+40-075", True) + _row(_T % "+44-070")
            + _row(_T % "+46-068", True) + _row("Lib") + _row("Mesh"))
    kinds = _OTHER + [(_T % n, "ortho") for n in
                      ("+40-075", "+44-070", "+46-068", "+45-069")]
    text, _added = _tidy(tmp_path, body, kinds)
    assert text == _HEAD + (
        _row("Apt") + _row(_T % "+40-075", True) + _row(_T % "+44-070")
        + _row(_T % "+45-069") + _row(_T % "+46-068", True) + _row("Lib")
        + _row("Mesh"))


def test_two_blocks_take_tiles_by_alphabetical_neighbour(tmp_path):
    # Each new tile goes after the last tile sorting before it — whichever
    # block that row is in — or before the very first tile row.
    body = (_row(_T % "+40-075") + _row(_T % "+41-073") + _row("Apt")
            + _row(_T % "+50-001") + _row("Mesh"))
    kinds = [("Apt", "airport"), ("Mesh", "mesh")] + [
        (_T % n, "ortho") for n in ("+40-075", "+41-073", "+50-001",
                                     "+30-090", "+45-070", "+51-000")]
    text, _added = _tidy(tmp_path, body, kinds)
    assert text == _HEAD + (
        _row(_T % "+30-090") + _row(_T % "+40-075") + _row(_T % "+41-073")
        + _row(_T % "+45-070") + _row("Apt") + _row(_T % "+50-001")
        + _row(_T % "+51-000") + _row("Mesh"))


@pytest.mark.parametrize("tail", ["\n", ""])
def test_no_block_puts_tiles_at_the_bottom(tmp_path, tail):
    body = _row("Apt") + _row("Lib") + _row("Mesh")
    kinds = _OTHER + [(_T % "+41-073", "ortho"), (_T % "+40-075", "ortho"),
                      ("Other Ortho", "ortho")]
    text, added = _tidy(tmp_path, body, kinds, tail)
    # Another ortho kind keeps its group rule (above the mesh); the
    # tiles go below every row, sorted, and the line break stays as found.
    want = _HEAD + (_row("Apt") + _row("Lib") + _row("Other Ortho")
                    + _row("Mesh") + _row(_T % "+40-075")
                    + _row(_T % "+41-073"))
    assert text == (want if tail else want[:-1])
    assert added[-2:] == [_T % "+40-075", _T % "+41-073"]


def test_insert_new_packs_on_lines_directly():
    lines = (_HEAD + _row("Apt") + _row(_T % "+40-075")).split("\n")
    added = SP.insert_new_packs(lines, [_T % "+39-077"],
                                lambda name: "ortho" if "zOrtho" in name
                                else "airport")
    assert added == [_T % "+39-077"]
    assert "\n".join(lines) == _HEAD + (_row("Apt") + _row(_T % "+39-077")
                                        + _row(_T % "+40-075"))
