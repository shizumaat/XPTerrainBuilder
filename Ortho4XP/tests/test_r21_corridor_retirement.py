"""R21 — ``flat_site_declared_corridors`` RETIRES (owner 2026-08-12).

R17-2 asked the owner to type a causeway's bounding box into a per-tile
cfg key.  The owner ruled the mechanism out: "flat-site grading and
seawalls must DETECT land connection automatically so it works for all
airports and users … flat_site_declared_corridors retires."  The law
that replaces it is twinned in
``tests/test_r21_land_connected_continuity.py``; this file asserts the
RETIREMENT — which is a compatibility contract as much as a deletion:

* the key is gone from the registry, the parser is gone from the
  detector, and NOTHING in ``src/`` reads the key any more;
* a cfg that still carries the line — the owner's own +22+113 tile cfg
  does — LOADS, and the reader DELETES the line and says so once
  (owner RULINGS 2026-09-13a (2)); a cfg that cannot be rewritten is
  reported once and carried on with.  A user's stale cfg must not take
  a build down, and must not nag either.

This file is the converted twin of the retired
``tests/test_r17_corridor_declaration.py``.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Cfg_Vars as CV  # noqa: E402
import O4_Config_Utils as CFG  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402
from auto_patch import flat_site as FS  # noqa: E402
from auto_patch import flat_site_mode as FSM  # noqa: E402

KEY = "flat_site_declared_corridors"
OWNER_DECL = "VHHH:22.3125624,113.9426422,22.3145276,113.9469981"


class TestTheKeyIsGone:
    def test_it_is_not_a_setting_any_more(self):
        assert KEY not in CV.cfg_vars
        assert KEY not in CV.list_tile_vars
        assert KEY not in CV.list_vector_vars
        assert KEY not in CV.list_cfg_vars

    def test_the_parser_and_its_delivery_are_gone(self):
        for name in ("declared_flat_corridors", "corridors_for_tile",
                     "corridor_bounds_tile_degrees"):
            assert not hasattr(FS, name), name
        assert not hasattr(FSM, "_declared_corridor_boxes")

    def test_a_substitution_carries_no_corridor_field(self):
        """The wire record between the decision and the bake: a field
        nobody fills is a mechanism waiting to come back."""
        import inspect
        source = inspect.getsource(FSM.flat_site_substitutions)
        assert "declared_corridors" not in source

    def test_nothing_in_src_reads_the_key(self):
        """The claim "no cfg key consumed anywhere", made structurally.
        Only the retirement registry and comments may name it."""
        readers = []
        for path in SRC.rglob("*.py"):
            for number, line in enumerate(
                    path.read_text(errors="ignore").splitlines(), 1):
                if KEY not in line:
                    continue
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("*"):
                    continue
                if path.name == "O4_Cfg_Vars.py":
                    continue                      # the retirement registry
                readers.append("%s:%d %s" % (path.name, number, stripped))
        assert readers == []

    def test_the_vector_map_no_longer_carries_a_corridor_role(self):
        import O4_Vector_Map as VMAP
        assert not hasattr(VMAP, "declared_corridor_rings")
        assert not hasattr(VMAP, "DECLARED_CORRIDOR_ROLE")
        assert "declared_corridor" not in VMAP.GRADED_COVERAGE_ROLES
        assert "declared_corridor" not in VMAP.AIRPORT_ISLAND_INSET_KINDS



class TestAStaleCfgIsCLEANEDUP:
    """The owner's +22+113 cfg carries ``flat_site_declared_corridors=``
    and KCLT's carries two more.  Until 2026-09-13 every read warned
    about them, forever, three times a build.  The owner ruled: find a
    retired key, DELETE it and say so once (RULINGS 2026-09-13a (2)).
    A retirement that errors on a stale line is still a retirement that
    breaks builds — so a cfg that cannot be rewritten carries on."""

    SECOND = "flat_site_declared_elevation_m"

    @staticmethod
    def _reset():
        CV._retired_cfg_reported.clear()

    def _cfg(self, tmp_path, text):
        """A tile build dir carrying *text* as its cfg; returns the path.

        STAMPED (owner RULINGS 2026-09-18c (2)): an UNSTAMPED tile cfg is
        a pre-1.0.352 file, which a reader MOVES aside rather than reads —
        so a fixture testing what the reader does with the file's lines
        must write a file of the current format.  One helper,
        ``SM.tile_cfg_stamp_line()``, the same line the engine writes.
        """
        build = tmp_path / "zOrtho4XP_+22+113"
        build.mkdir()
        path = build / ("Ortho4XP_" + FNAMES.short_latlon(22, 113) + ".cfg")
        path.write_text(SM.tile_cfg_stamp_line() + text)
        return path

    def _tile(self, tmp_path, text):
        path = self._cfg(tmp_path, text)
        return CFG.Tile(22, 113, str(path.parent)), path

    # ── the registry ────────────────────────────────────────────────
    def test_the_registry_still_records_WHY_it_went(self):
        """The line is deleted, but the registry keeps the sentence: it
        is what the docs and this twin read to say what replaced it."""
        self._reset()
        assert KEY in CV.retired_cfg_keys
        assert "RETIRED" in CV.retired_cfg_key_warning(KEY)
        assert OWNER_DECL in CV.retired_cfg_key_warning(KEY, OWNER_DECL)
        # a merely-superseded key carries no sentence…
        assert CV.retired_cfg_key_warning(
            "airport_elevation_inset_resolution_m") is None
        # …and a live key is not a retirement at all.
        assert CV.retired_cfg_key_warning("modify_custom_airports") is None

    def test_the_config_reader_knows_the_retirement(self):
        assert KEY in CFG.RETIRED_CFG_KEYS

    # ── ONE read removes the lines ──────────────────────────────────
    def test_one_read_REMOVES_both_retired_keys_and_backs_them_up(
            self, tmp_path, capsys):
        self._reset()
        text = (KEY + "=" + OWNER_DECL + "\nauto_patch=ICAO\n"
                + self.SECOND + "=123.0\nmesh_zl=19\n")
        tile, path = self._tile(tmp_path, text)
        assert tile.read_from_config() == 1

        # the file has neither retired key…
        after = path.read_text()
        assert KEY not in after
        assert self.SECOND not in after
        # …the live keys around them survived…
        assert "auto_patch=ICAO" in after
        assert "mesh_zl=19" in after
        assert tile.auto_patch == "ICAO"
        assert tile.mesh_zl == 19
        # …the retired ones landed nowhere…
        assert not hasattr(tile, KEY)
        assert not hasattr(tile, self.SECOND)
        # …and the .bak the existing writer makes still carries both.
        backup = Path(str(path) + ".bak")
        assert backup.is_file()
        assert KEY in backup.read_text()
        assert self.SECOND in backup.read_text()

        output = capsys.readouterr().out
        assert len(re.findall("removed retired key " + KEY, output)) == 1
        assert len(re.findall("removed retired key " + self.SECOND,
                              output)) == 1
        assert "WARNING" not in output
        assert "invalid line" not in output.lower()

    def test_the_same_cfg_read_again_says_NOTHING(self, tmp_path, capsys):
        """KCLT's cfg is read three times per build.  The first read
        deletes the lines; the next two have nothing to find."""
        self._reset()
        _, path = self._tile(
            tmp_path, KEY + "=" + OWNER_DECL + "\nauto_patch=ICAO\n")
        for _ in range(3):
            CFG.Tile(22, 113, str(path.parent)).read_from_config()
        output = capsys.readouterr().out
        assert len(re.findall("removed retired key " + KEY, output)) == 1
        assert "WARNING" not in output
        assert KEY not in path.read_text()

    def test_ANOTHER_cfg_carrying_it_is_its_own_cleanup(self, tmp_path,
                                                        capsys):
        self._reset()
        paths = []
        for lat, lon in ((22, 113), (23, 113)):
            build = tmp_path / ("zOrtho4XP_" + FNAMES.short_latlon(lat, lon))
            build.mkdir()
            path = build / ("Ortho4XP_" + FNAMES.short_latlon(lat, lon)
                            + ".cfg")
            path.write_text(SM.tile_cfg_stamp_line()
                            + KEY + "=" + OWNER_DECL + "\n")
            paths.append(path)
            CFG.Tile(lat, lon, str(build)).read_from_config()
        output = capsys.readouterr().out
        assert len(re.findall("removed retired key " + KEY, output)) == 2
        for path in paths:
            assert KEY not in path.read_text()

    # ── a clean cfg is not touched ──────────────────────────────────
    def test_a_cfg_with_no_retired_key_is_untouched_BYTE_FOR_BYTE(
            self, tmp_path, capsys):
        """No retired key, no rewrite: no reordering, no lost comments,
        no .bak churn on every read of every tile cfg in a build."""
        self._reset()
        text = "# a comment\nauto_patch=ICAO\n\nmesh_zl=19\n"
        tile, path = self._tile(tmp_path, text)
        assert tile.read_from_config() == 1
        assert path.read_text() == SM.tile_cfg_stamp_line() + text
        assert not Path(str(path) + ".bak").exists()
        assert "removed retired key" not in capsys.readouterr().out

    # ── a cfg that cannot be rewritten still builds ─────────────────
    def test_a_READ_ONLY_cfg_reports_once_and_carries_on(self, tmp_path,
                                                         capsys):
        self._reset()
        text = KEY + "=" + OWNER_DECL + "\nauto_patch=ICAO\n"
        tile, path = self._tile(tmp_path, text)
        directory = path.parent
        os.chmod(directory, 0o500)          # no new files: no atomic write
        try:
            assert tile.read_from_config() == 1
            assert tile.auto_patch == "ICAO"      # the build carries on
            # read again: the stale line is still there, and still silent
            CFG.Tile(22, 113, str(directory)).read_from_config()
            output = capsys.readouterr().out
            assert len(re.findall("IGNORED", output)) == 1
            assert "INFO" in output
            assert "WARNING" not in output
            assert path.read_text() == (SM.tile_cfg_stamp_line()
                                        + text)   # untouched
            assert not Path(str(path) + ".bak").exists()
        finally:
            os.chmod(directory, 0o700)

    # ── the GLOBAL cfg: the writer drops it too ─────────────────────
    def test_write_global_DROPS_retired_keys(self, tmp_path):
        """``write_global`` preserves unknown keys — that pass-through is
        what would have kept a retired key in the global cfg forever."""
        self._reset()
        path = tmp_path / "Ortho4XP.cfg"
        path.write_text(KEY + "=" + OWNER_DECL + "\n"
                        + self.SECOND + "=123.0\nmesh_zl=19\n"
                        "some_unknown_key=keep me\n")
        SM.write_global({"mesh_zl": "18"}, str(path))
        after = path.read_text()
        assert KEY not in after
        assert self.SECOND not in after
        assert "mesh_zl=18" in after
        assert "some_unknown_key=keep me" in after   # unknown ≠ retired

    def test_the_global_READER_cleans_the_global_cfg(self, tmp_path,
                                                     capsys):
        """The tile and global readers share ONE cleanup, so pointing the
        cleanup at a global cfg does to it exactly what a tile read does
        (the module-level global read runs at import and cannot be
        re-triggered headlessly)."""
        self._reset()
        path = tmp_path / "Ortho4XP.cfg"
        path.write_text(KEY + "=" + OWNER_DECL + "\nmesh_zl=19\n")
        lines = CV.cleanup_retired_cfg_keys(str(path))
        assert lines == ["removed retired key " + KEY + " from "
                         + os.path.abspath(str(path))]
        assert path.read_text() == "mesh_zl=19\n"
        assert KEY in Path(str(path) + ".bak").read_text()

    def test_the_cleanup_never_raises(self, tmp_path):
        """A cleanup that throws is a cleanup that breaks builds."""
        self._reset()
        assert CV.cleanup_retired_cfg_keys(None) == []
        assert CV.cleanup_retired_cfg_keys(str(tmp_path / "nope.cfg")) == []
        assert CV.cleanup_retired_cfg_keys(str(tmp_path)) == []
