"""A tile's build identity in the GLOBAL cfg (owner engine log, 1.0.510:
"Global config file contains an invalid line: default_website=USA2").

``default_website`` / ``default_zl`` / ``zone_list`` are per-tile keys
(``O4_Cfg_Vars.BUILD_IDENTITY_KEYS``): the global reader has no
``global_`` twin for them, so a stray line in the global cfg -- the
2026-11-12 Fly pane wrote ``default_website`` there until #2018 moved
it to ``fly_photo_source`` -- warned on every engine start AND set the
module value every new ``Tile`` copies.  The reader now skips the line
and drops it from the file once; a tile cfg keeps its own.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Cfg_Vars as CV  # noqa: E402

SRC = str(Path(__file__).resolve().parents[1] / "src")


def test_build_identity_keys_have_no_global_twin():
    for key in CV.BUILD_IDENTITY_KEYS:
        assert key in CV.list_tile_vars
        assert CV.global_prefix + key not in CV.cfg_vars


def test_the_global_cleanup_drops_a_stray_provider(tmp_path):
    cfg = tmp_path / "XPTerrainBuilder.cfg"
    cfg.write_text("mesh_zl=19\ndefault_website=USA2\n", encoding="utf-8",
                   newline="")
    lines = CV.cleanup_retired_cfg_keys(
        str(cfg), dropped=CV.BUILD_IDENTITY_KEYS)
    assert lines == ["removed per-tile key default_website from "
                     + os.path.abspath(str(cfg))]
    assert cfg.read_text(encoding="utf-8") == "mesh_zl=19\n"
    assert "default_website=USA2" in Path(str(cfg) + ".bak").read_text(
        encoding="utf-8")


def test_a_tile_cfg_keeps_its_provider(tmp_path):
    cfg = tmp_path / "XPTerrainBuilder_+25+051.cfg"
    body = "default_website=Arc\ndefault_zl=16\n"
    cfg.write_text(body, encoding="utf-8", newline="")
    assert CV.cleanup_retired_cfg_keys(str(cfg)) == []
    assert cfg.read_text(encoding="utf-8") == body


def test_the_engine_start_reads_it_silently_and_no_tile_inherits_it(
        tmp_path):
    """The import-time global read (a fresh interpreter: it cannot be
    re-triggered in this one)."""
    root = tmp_path / "data"
    root.mkdir()
    (root / "XPTerrainBuilder.cfg").write_text(
        "mesh_zl=19\ndefault_website=USA2\n", encoding="utf-8", newline="")
    probe = (
        "import sys; sys.path.insert(0, %r)\n"
        "import O4_File_Names as F; F.set_data_root(%r)\n"
        "import O4_Config_Utils as C\n"
        "print('TILE_SITE=' + repr(C.Tile(25, 51, '').default_website))\n"
        % (SRC, str(root)))
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                         text=True, timeout=120, cwd=str(tmp_path))
    text = out.stdout + out.stderr
    assert out.returncode == 0, text
    assert "invalid line" not in text
    assert "TILE_SITE=''" in text
    assert "default_website" not in (root / "XPTerrainBuilder.cfg").read_text(
        encoding="utf-8")
