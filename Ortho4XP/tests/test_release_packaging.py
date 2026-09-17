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
  ``--engine-jsonl``, so the AppImage stops being usable as the engine;
* a type-2 RUNTIME downloaded at build time from upstream's mutable
  ``continuous`` tag (appimagetool's default) puts unreviewed, drifting
  bytes at the FRONT of every AppImage — the first code a Linux tester
  runs.  It is vendored instead (``scripts/appimage/runtime-x86_64``,
  owner decision 2026-09-17) and pinned by sha256 in the script.

Hermetic: reads the workflow, the packaging script and the vendored
runtime as bytes on disk.
"""

from __future__ import annotations

import hashlib
import re
import stat
import struct
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_DIR.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
MAKE_APPIMAGE = REPO_ROOT / "scripts" / "make_appimage.sh"
APPIMAGE_RUNTIME = REPO_ROOT / "scripts" / "appimage" / "runtime-x86_64"
APPIMAGE_README = REPO_ROOT / "scripts" / "appimage" / "README.md"
LICENSING = REPO_ROOT / "LICENSING.md"

# What the vendored asset is (scripts/appimage/README.md).  Duplicated here
# deliberately: a twin that read the pin out of the thing it checks would
# pass against any substitution.
RUNTIME_SHA256 = (
    "1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf")
RUNTIME_SIZE = 944632
RUNTIME_COMMIT = "75849dce7cc37e4319b633df1f116ca895c71a12"

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


# ---------------------------------------------------------------------------
# The vendored type-2 runtime (owner decision 2026-09-17).
# ---------------------------------------------------------------------------

def _section_offsets(blob: bytes) -> dict[str, tuple[int, int]]:
    """{section name: (file offset, size)} from a little-endian ELF64."""
    e_shoff, = struct.unpack_from("<Q", blob, 0x28)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", blob, 0x3A)

    def header(i):
        off = e_shoff + i * e_shentsize
        name, _typ, _flags, _addr, f_off, size = struct.unpack_from(
            "<IIQQQQ", blob, off)
        return name, f_off, size

    _, stroff, _ = header(e_shstrndx)
    out = {}
    for i in range(e_shnum):
        name, f_off, size = header(i)
        end = blob.index(b"\0", stroff + name)
        out[blob[stroff + name:end].decode()] = (f_off, size)
    return out


def test_vendored_runtime_is_the_recorded_asset():
    assert APPIMAGE_RUNTIME.is_file(), (
        f"the vendored AppImage runtime is missing: {APPIMAGE_RUNTIME} — "
        "without it appimagetool downloads one from a mutable tag")
    blob = APPIMAGE_RUNTIME.read_bytes()
    assert len(blob) == RUNTIME_SIZE
    assert hashlib.sha256(blob).hexdigest() == RUNTIME_SHA256
    # A static-pie ELF64 for x86-64 whose AppImage type-2 magic is already
    # written (upstream's build-runtime.sh dd's it in after strip), so
    # appimagetool has nothing to patch at offset 8.
    assert blob[:4] == b"\x7fELF"
    assert blob[4] == 2, "not ELF64"
    assert blob[5] == 1, "not little-endian"
    assert struct.unpack_from("<H", blob, 0x12)[0] == 0x3E, "not x86-64"
    assert blob[8:11] == b"AI\x02", "AppImage type-2 magic absent at offset 8"


def test_vendored_runtime_provenance_is_recorded():
    readme = APPIMAGE_README.read_text(encoding="utf-8")
    assert RUNTIME_SHA256 in readme, "README records a different sha256"
    assert RUNTIME_COMMIT in readme, "README records no upstream commit"
    assert str(RUNTIME_SIZE) in readme.replace(",", "")


def test_script_pins_the_runtime_and_passes_it_to_appimagetool(script):
    assert "--runtime-file" in script, (
        "appimagetool is not given the vendored runtime — it downloads one")
    pins = re.findall(r"RUNTIME_SHA256=([0-9a-f]{64})\b", script)
    assert pins == [RUNTIME_SHA256], (
        f"make_appimage.sh must pin exactly one sha256, the one the README "
        f"records; found {pins}")
    assert re.search(r"RUNTIME_SIZE=%d\b" % RUNTIME_SIZE, script)
    # Resolved from the SCRIPT's own location, not the caller's cwd: a
    # cwd-relative path turns a moved cwd into a silent network fallback.
    assert 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in script
    assert 'RUNTIME="$SCRIPT_DIR/appimage/runtime-x86_64"' in script
    assert '--runtime-file "$RUNTIME"' in script


def test_script_refuses_a_wrong_or_absent_runtime(script):
    """Absence and mismatch both refuse BY NAME, before anything is built."""
    verify = script[script.index('[ -f "$RUNTIME" ]'):
                    script.index("WORK=")]
    assert 'if [ "$RUNTIME_GOT" != "$RUNTIME_SHA256" ]; then' in verify
    assert verify.count("exit 1") >= 3, (
        "absence, sha mismatch and size mismatch must each refuse")
    assert "$RUNTIME" in verify, "the refusal does not name the file"
    # Runs on the Linux runner, and on a mac for local checks.
    assert "sha256sum" in script and "shasum -a 256" in script
    # BEFORE the build: the verification block precedes the AppDir.
    assert script.index("RUNTIME_GOT=") < script.index('rm -rf "$APPDIR"')


def test_script_fails_if_appimagetool_downloaded_a_runtime(script):
    tail = script[script.index('"$TOOL" --appimage-extract-and-run'):]
    assert 'tee "$TOOL_LOG"' in tail, "appimagetool's output is not captured"
    assert """grep -inE 'download' "$TOOL_LOG\"""" in tail, (
        "nothing checks appimagetool's log for a download")
    assert "appimagetool reported a DOWNLOAD" in tail
    # The log grep is the belt; the artifact proof below it is the braces.
    assert tail.index('tee "$TOOL_LOG"') < tail.index("grep -inE 'download'")


def test_script_proves_the_shipped_appimage_carries_the_vendored_runtime(
        script):
    """The proof is on the ARTIFACT, and it is not 'the file exists'."""
    tail = script[script.index("(3) the SHIPPED artifact"):]
    assert "--appimage-offset" in tail
    assert 'head -c "$EMBED_OFFSET" "$OUT" > "$EMBEDDED"' in tail
    assert 'EMBEDDED_SHA="$(sha256_of "$EMBEDDED")"' in tail
    assert 'cmp -l "$RUNTIME" "$EMBEDDED"' in tail, (
        "a differing prefix must be MEASURED, not waved through")
    # The one region appimagetool may write: the .digest_md5 ELF section.
    # Its offset is asserted against the real section header below, so the
    # allowance cannot quietly widen to cover a substituted runtime.
    off = int(re.search(r"DIGEST_MD5_OFF=(\d+)", script).group(1))
    length = int(re.search(r"DIGEST_MD5_LEN=(\d+)", script).group(1))
    sections = _section_offsets(APPIMAGE_RUNTIME.read_bytes())
    assert sections[".digest_md5"] == (off, length), (
        f"the permitted patch window {(off, length)} is not the runtime's "
        f".digest_md5 section {sections['.digest_md5']}")
    assert length == 16
    # And nothing else is permitted to differ.
    assert "differs OUTSIDE the .digest_md5" in tail
    assert tail.count("exit 1") >= 2


def test_release_workflow_still_pins_appimagetool_itself(workflow):
    """Vendoring the runtime must not have relaxed the tool's own pin."""
    assert re.search(r"APPIMAGETOOL_SHA256:\s*[0-9a-f]{64}\b", workflow)
    assert "sha256sum -c -" in workflow
    linux = workflow[workflow.index("appimagetool (pinned"):]
    build = linux.index("Build AppImage")
    assert linux.index("APPIMAGETOOL=") < build, (
        "the verified tool path must be exported before the build step")


def test_licensing_carries_the_runtime_and_what_it_statically_links():
    """make_notices.py copies LICENSING §3 verbatim into the notices."""
    text = LICENSING.read_text(encoding="utf-8")
    section = text[text.index("## 3."):text.index("## 4.")]
    assert RUNTIME_SHA256 in section
    assert RUNTIME_COMMIT in section
    # The link line of upstream's src/runtime/Makefile at that commit, plus
    # the libc it is built against.  Each needs its licence in the notices.
    for component, licence in (
            ("type-2 runtime", "MIT"),
            ("musl libc", "MIT"),
            ("libfuse 3.15.0", "LGPL v2.1"),
            ("squashfuse 0.5.2", "BSD-2-Clause"),
            ("zstd", "BSD-3-Clause"),
            ("zlib", "zlib license"),
            ("mimalloc", "MIT"),
    ):
        assert component in section, f"{component} missing from LICENSING §3"
        assert licence in section, f"{licence} ({component}) not stated"
    assert "Linux `.AppImage` artifact only" in section, (
        "the notices must say the runtime ships in the AppImage alone")


def test_no_spec_bundles_the_scripts_directory():
    """The runtime must never enter a frozen bundle.

    It lives under scripts/, which no .spec reaches: PyInstaller runs with
    cwd=Ortho4XP/ and every datas source is inside that tree.
    """
    specs = sorted(ENGINE_DIR.glob("*.spec"))
    assert len(specs) == 2, f"expected two .spec files, found {specs}"
    scripts_dir = (REPO_ROOT / "scripts").resolve()
    for spec in specs:
        text = spec.read_text(encoding="utf-8")
        body = text[text.index("datas=["):text.index("hiddenimports=")]
        sources = re.findall(r"\(\s*'([^']+)'\s*,\s*'[^']*'\s*\)", body)
        assert sources, f"{spec.name}: no datas entries parsed"
        for src in sources:
            resolved = (ENGINE_DIR / src).resolve()
            assert scripts_dir not in resolved.parents, (
                f"{spec.name} bundles {src} from {scripts_dir} — the "
                "vendored AppImage runtime must not enter a frozen bundle")
            assert resolved != scripts_dir
        assert "scripts/appimage" not in text
        assert "runtime-x86_64" not in text
