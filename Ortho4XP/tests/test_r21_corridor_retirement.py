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
  does — LOADS, with a loud warning, and never errors.  A user's stale
  cfg must not take a build down.

This file is the converted twin of the retired
``tests/test_r17_corridor_declaration.py``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Cfg_Vars as CV  # noqa: E402
import O4_Config_Utils as CFG  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
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


class TestAStaleCfgStillLoads:
    """The owner's +22+113 cfg carries ``flat_site_declared_corridors=``.
    A retirement that errors on it is a retirement that breaks builds."""

    def test_the_registry_retires_it_LOUDLY(self):
        assert KEY in CV.retired_cfg_keys
        assert CV.retired_cfg_key_warning(KEY)
        assert "RETIRED" in CV.retired_cfg_key_warning(KEY)
        # …and the value is quoted, so a user who wrote a corridor is
        # told exactly which declaration stopped being read.
        assert OWNER_DECL in CV.retired_cfg_key_warning(KEY, OWNER_DECL)

    def test_a_silently_retired_key_stays_silent(self):
        """Not every retirement is loud: a superseded knob nobody needs
        to know about keeps its silent skip."""
        assert CV.retired_cfg_key_warning(
            "airport_elevation_inset_resolution_m") is None

    def test_a_live_key_is_not_a_retirement(self):
        assert CV.retired_cfg_key_warning("flat_site_declared") is None

    def test_the_config_reader_knows_the_retirement(self):
        assert KEY in CFG.RETIRED_CFG_KEYS

    def _tile_with_cfg(self, tmp_path, text):
        build = tmp_path / "zOrtho4XP_+22+113"
        build.mkdir()
        (build / ("Ortho4XP_" + FNAMES.short_latlon(22, 113) + ".cfg")
         ).write_text(text)
        return CFG.Tile(22, 113, str(build))

    def test_the_owners_EMPTY_line_loads_and_warns(self, tmp_path, capsys):
        tile = self._tile_with_cfg(
            tmp_path, "auto_patch=ICAO\n" + KEY + "=\nmesh_zl=19\n")
        assert tile.read_from_config() == 1
        assert "RETIRED" in capsys.readouterr().out
        # the live keys around it still land…
        assert tile.auto_patch == "ICAO"
        assert tile.mesh_zl == 19
        # …and the retired one lands nowhere.
        assert not hasattr(tile, KEY)

    def test_a_cfg_STILL_DECLARING_a_corridor_loads_and_warns(
            self, tmp_path, capsys):
        tile = self._tile_with_cfg(
            tmp_path, KEY + "=" + OWNER_DECL + "\nauto_patch=ICAO\n")
        assert tile.read_from_config() == 1
        output = capsys.readouterr().out
        assert "RETIRED" in output
        assert OWNER_DECL in output
        assert not hasattr(tile, KEY)
        assert tile.auto_patch == "ICAO"

    def test_the_warning_is_not_an_invalid_line_report(self, tmp_path,
                                                       capsys):
        """Before the registry knew it, an unknown key fell into the tile
        reader's generic handler and vanished at verbosity 2.  A setting
        that stopped being read must be VISIBLE."""
        tile = self._tile_with_cfg(tmp_path, KEY + "=" + OWNER_DECL + "\n")
        tile.read_from_config()
        output = capsys.readouterr().out
        assert "invalid line" not in output.lower()
        assert len(re.findall("RETIRED", output)) == 1
