"""The overlay step refuses a 7z archive it cannot open, and says why.

``Utils/lin`` vendors no 7-Zip binary, so on Linux ``unzip_cmd`` was a
bare ``"7z"`` that exists only if the user installed p7zip.  When they
had not, the miss surfaced as a ``FileNotFoundError`` from inside
extraction — it named neither the cause nor the package to install.

The executable is now probed AT USE TIME (7zz / 7z / 7za on PATH, or a
vendored absolute path) and its absence is one refusal line.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
import O4_Overlay_Utils as OVL  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402


# ---------------------------------------------------------------------------
# The probe
# ---------------------------------------------------------------------------
def test_a_vendored_absolute_path_is_used_as_is(tmp_path, monkeypatch):
    vendored = tmp_path / "7zz"
    vendored.write_text("")
    monkeypatch.setattr(OVL, "unzip_cmd", str(vendored))
    monkeypatch.setattr(OVL.shutil, "which", lambda name: "/never/used")
    assert OVL.resolve_unzip_cmd() == str(vendored)


def test_a_missing_vendored_binary_is_not_silently_accepted(
        tmp_path, monkeypatch):
    monkeypatch.setattr(OVL, "unzip_cmd", str(tmp_path / "absent" / "7zz"))
    assert OVL.resolve_unzip_cmd() is None


def test_path_is_probed_in_order(monkeypatch):
    monkeypatch.setattr(OVL, "unzip_cmd", "7z")
    seen = []

    def which(name):
        seen.append(name)
        return "/usr/bin/7za" if name == "7za" else None

    monkeypatch.setattr(OVL.shutil, "which", which)
    assert OVL.resolve_unzip_cmd() == "/usr/bin/7za"
    assert seen == ["7zz", "7z", "7za"]


def test_no_seven_zip_anywhere_is_none(monkeypatch):
    monkeypatch.setattr(OVL, "unzip_cmd", "7z")
    monkeypatch.setattr(OVL.shutil, "which", lambda name: None)
    assert OVL.resolve_unzip_cmd() is None


# ---------------------------------------------------------------------------
# The refusal
# ---------------------------------------------------------------------------
def _overlay_source(tmp_path, lat, lon, payload):
    src = tmp_path / "overlays"
    dsf = src / "Earth nav data" / (FNAMES.long_latlon(lat, lon) + ".dsf")
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(payload)
    return str(src)


def test_a_7z_overlay_without_7zip_refuses_by_name(tmp_path, monkeypatch,
                                                  capsys):
    (lat, lon) = (22, 113)
    monkeypatch.setattr(
        OVL, "custom_overlay_src", _overlay_source(tmp_path, lat, lon, b"7z"))
    monkeypatch.setattr(OVL, "custom_overlay_src_alternate", "")
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    monkeypatch.setattr(FNAMES, "Tmp_dir", str(tmp_dir))
    monkeypatch.setattr(OVL, "unzip_cmd", "7z")
    monkeypatch.setattr(OVL.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        OVL.subprocess, "run",
        lambda *a, **k: pytest.fail("extraction must not be attempted"))
    UI.is_working = 0

    assert OVL.build_overlay(lat, lon) == 0

    out = capsys.readouterr().out
    assert "no 7-Zip executable was found" in out
    assert "p7zip-full" in out
    assert "7zip" in out
    # One refusal line, not a traceback.
    assert "Traceback" not in out


def test_a_plain_dsf_never_looks_for_7zip(tmp_path, monkeypatch):
    """The probe is only reached for an archive — an ordinary overlay DSF
    on a machine with no 7-Zip must still build."""
    (lat, lon) = (22, 113)
    monkeypatch.setattr(
        OVL, "custom_overlay_src",
        _overlay_source(tmp_path, lat, lon, b"XPLNEDSF"))
    monkeypatch.setattr(OVL, "custom_overlay_src_alternate", "")
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    monkeypatch.setattr(FNAMES, "Tmp_dir", str(tmp_dir))
    monkeypatch.setattr(
        OVL, "resolve_unzip_cmd",
        lambda: pytest.fail("a plain DSF must not probe for 7-Zip"))
    UI.is_working = 0

    # DSFTool is absent in the test environment; the call dies there, AFTER
    # the branch under test. Either outcome proves the probe was not run.
    try:
        OVL.build_overlay(lat, lon)
    except Exception:
        pass
    finally:
        UI.is_working = 0
    assert os.path.exists(
        os.path.join(str(tmp_dir), FNAMES.short_latlon(lat, lon) + ".dsf"))
