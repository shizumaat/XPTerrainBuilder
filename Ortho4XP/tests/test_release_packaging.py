"""Tripwires for the Linux AppImage packaging (RELEASES-PLAN §D2, §G).

None of this is reachable from a dev machine — it only ever runs on the
Linux release runner — and each of these is a silent failure there:

* an UNPINNED appimagetool (the mutable ``continuous/`` tag, or a pin with
  no sha256) is an unreviewed build step in every release;
* dropping the AppImage from the release job's ``files:`` list produces a
  green run that publishes only the tar.gz;
* proving the AppImage AFTER the upload proves nothing (the brief's step 4:
  an AppImage that cannot build a tile must not upload);
* a `.desktop` file without ``Categories``/``Terminal``/``Icon`` installs a
  menu entry that does not appear or does not launch;
* an AppRun that drops ``"$@"`` silently discards ``--proj-selfcheck`` and
  ``--engine-jsonl``, so the AppImage stops being usable as the engine.

Hermetic: reads the workflow and the packaging script as text.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_DIR.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
MAKE_APPIMAGE = REPO_ROOT / "scripts" / "make_appimage.sh"

pytestmark = pytest.mark.skipif(
    not WORKFLOW.is_file() or not MAKE_APPIMAGE.is_file(),
    reason="engine used standalone: the app-side release files are absent",
)


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_appimagetool_is_pinned_and_hash_verified(workflow):
    url = re.search(r"APPIMAGETOOL_URL:\s*(\S+)", workflow)
    sha = re.search(r"APPIMAGETOOL_SHA256:\s*([0-9a-f]{64})\b", workflow)
    assert url, "no pinned appimagetool URL"
    assert sha, "no 64-hex appimagetool sha256 recorded in the workflow"
    assert "/releases/download/" in url.group(1)
    assert "/continuous/" not in url.group(1), (
        "continuous/ is a mutable tag — pin a release")
    assert "sha256sum -c -" in workflow, (
        "the recorded sha256 is never checked")


def test_appimage_is_proved_before_it_uploads(workflow):
    prove = workflow.index("Prove the AppImage")
    build = workflow.index("Build AppImage")
    upload = workflow.index("XPTerrainBuilder-*-linux.AppImage\n", prove)
    assert build < prove < upload, (
        "the AppImage must be built, then proved, then uploaded")
    proof = workflow[prove:upload]
    assert "--proj-selfcheck" in proof
    assert "check_frozen_tile.sh" in proof
    # No FUSE on ubuntu-22.04 runners.
    assert "--appimage-extract-and-run" in proof
    assert "--appimage-extract " in proof or "--appimage-extract >" in proof


def test_release_attaches_the_appimage(workflow):
    files = workflow[workflow.index("softprops/action-gh-release"):]
    for pattern in ("-linux.AppImage", "-linux.tar.gz", "-win.zip",
                    "-mac.zip", "-source.tar.gz"):
        assert f"XPTerrainBuilder-*{pattern}" in files, (
            f"the release attaches no {pattern}")


def test_branding_is_generated_before_every_freeze(workflow):
    """Both Qt jobs generate the icon BEFORE PyInstaller reads the spec."""
    positions = [m.start() for m in re.finditer(r"make_icon\.py", workflow)]
    freezes = [m.start() for m in re.finditer(r"PyInstaller Ortho4XP_Qt\.spec",
                                              workflow)]
    assert len(positions) == 2, "expected the Windows and Linux icon steps"
    assert len(freezes) == 2
    for icon_at, freeze_at in zip(positions, freezes):
        assert icon_at < freeze_at
    # The Windows version resource, likewise before its freeze.
    version_at = workflow.index("make_version_resource.py")
    assert version_at < freezes[0]


def test_appimage_script_is_executable():
    mode = MAKE_APPIMAGE.stat().st_mode
    assert mode & stat.S_IXUSR, "make_appimage.sh is not executable"


@pytest.fixture(scope="module")
def script() -> str:
    return MAKE_APPIMAGE.read_text(encoding="utf-8")


def test_desktop_entry_carries_what_a_desktop_reads(script):
    for line in ("[Desktop Entry]", "Type=Application",
                 "Name=XPTerrainBuilder", "Exec=XPTerrainBuilder",
                 "Categories=Utility;", "Terminal=false"):
        assert line in script, f"the .desktop file is missing {line!r}"
    assert "Icon=$ICON_NAME" in script
    assert 'ICON_NAME=xpterrainbuilder' in script
    # Root copy AND hicolor copy: AppImage requires the first, desktops
    # installing the entry read the second.
    assert 'usr/share/icons/hicolor/256x256/apps/$ICON_NAME.png' in script
    assert 'cp "$ICON" "$APPDIR/$ICON_NAME.png"' in script


def test_apprun_forwards_its_arguments(script):
    apprun = script[script.index("cat > \"$APPDIR/AppRun\""):
                    script.index("chmod +x \"$APPDIR/AppRun\"")]
    assert 'exec "$HERE/usr/bin/XPTerrainBuilder" "$@"' in apprun, (
        "AppRun must forward arguments — --proj-selfcheck and "
        "--engine-jsonl arrive that way")


def test_license_payload_is_required_in_the_appimage(script):
    for name in ("LICENSE", "LICENSING.md", "THIRD-PARTY-NOTICES.txt",
                 "gpl.txt", "copyright.txt", "VERSION.txt"):
        assert name in script, f"§G payload {name} not carried"
