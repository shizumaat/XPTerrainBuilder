"""Version scheme tripwire: ``1.50.<build>`` engine, ``1.0.<build>`` app.

Both products carry a tracked MAJOR.MINOR.BUILD version whose build component
the build scripts increment once per build (owner requirement 2026-07-24), so
any binary we hand out is attributable to a commit.  The engine's number also
feeds the auto-patch freshness fingerprint, so it must move for builds and
for nothing else.

Five independent parsers read ``src/O4_Version.py`` textually rather than
importing it — the two PyInstaller specs, ``scripts/make_engine.sh`` (whose
output becomes ``VERSION.txt``, the only way a *frozen* engine can report
itself), the mac app's schema dumper, and the app's Swift reader.  A stray
"equals" sign in a comment silently breaks some of them, so every parser is
replicated here and pinned against the real file.

Pure hermetic: the repo's own files, ``tmp_path`` copies and ``/bin/zsh`` —
no network, no X-Plane install, no freeze.
"""

from __future__ import annotations

import os
import plistlib
import re
import subprocess
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]
ENGINE_VERSION_FILE = ENGINE_DIR / "src" / "O4_Version.py"
QT_SPEC = ENGINE_DIR / "Ortho4XP_Qt.spec"

# The engine is vendored inside the XPTerrainBuilder repo; when it is used
# standalone the app-side files simply are not there.
REPO_ROOT = ENGINE_DIR.parent
APP_VERSION_FILE = REPO_ROOT / "Sources" / "XPTerrainBuilder" / "Resources" / "VERSION"
VERSION_SH = REPO_ROOT / "scripts" / "version.sh"
MAKE_ENGINE = REPO_ROOT / "scripts" / "make_engine.sh"
MAKE_APP = REPO_ROOT / "scripts" / "make_app.sh"
SCHEMA_DUMP = REPO_ROOT / "Sources" / "SceneryKit" / "Resources" / "o4_schema_dump.py"
SWIFT_ENGINE = REPO_ROOT / "Sources" / "SceneryKit" / "OrthoEngine.swift"

app_side = pytest.mark.skipif(
    not VERSION_SH.is_file(),
    reason="engine checked out standalone — no XPTerrainBuilder app tree",
)


def _zsh(script: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a zsh snippet under the build scripts' own shell options."""
    return subprocess.run(
        ["/bin/zsh", "-c", script],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def _helper(script: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a snippet with scripts/version.sh sourced, as the scripts do."""
    preamble = f"set -euo pipefail\nsource {VERSION_SH!s}\n"
    return _zsh(preamble + script, cwd=cwd)


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------
def test_engine_version_is_1_50_with_an_integer_build() -> None:
    text = ENGINE_VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r"^version\s*=\s*'([^']+)'\s*$", text, re.MULTILINE)
    assert match, "src/O4_Version.py must hold a single-quoted version assignment"
    assert re.fullmatch(r"1\.50\.\d+", match.group(1)), match.group(1)


@app_side
def test_app_version_is_1_0_with_an_integer_build() -> None:
    assert re.fullmatch(r"1\.0\.\d+", APP_VERSION_FILE.read_text(encoding="utf-8").strip())


def test_engine_version_file_holds_exactly_one_assignment() -> None:
    """The textual parsers below assume comments plus one assignment."""
    lines = ENGINE_VERSION_FILE.read_text(encoding="utf-8").splitlines()
    code = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    assert len(code) == 1, code
    # Ortho4XP_Qt.spec splits the WHOLE file on its first "=" — a comment
    # carrying one would hand it a mangled version.
    assert "=" not in "\n".join(line for line in lines if line.lstrip().startswith("#"))


# ---------------------------------------------------------------------------
# Every parser in the tree agrees, and none of them truncates the build
# ---------------------------------------------------------------------------
def expected_version() -> str:
    return re.search(
        r"^version\s*=\s*'([^']+)'", ENGINE_VERSION_FILE.read_text(encoding="utf-8"), re.MULTILINE
    ).group(1)


def test_python_import_reports_the_full_version() -> None:
    namespace: dict[str, object] = {}
    exec(compile(ENGINE_VERSION_FILE.read_text(encoding="utf-8"), "O4_Version.py", "exec"), namespace)
    assert namespace["version"] == expected_version()


@app_side
def test_freeze_script_extraction_reports_the_full_version() -> None:
    """The exact pipeline make_engine.sh writes into dist/…/VERSION.txt.

    Frozen engines have no src/O4_Version.py, so this string IS the version
    the app shows for a release build.
    """
    line = "grep -m1 '^version' src/O4_Version.py | cut -d= -f2 | tr -d \" '\\\"\""
    assert line in MAKE_ENGINE.read_text(encoding="utf-8"), "freeze extraction changed"
    result = _zsh(line, cwd=ENGINE_DIR)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected_version()


def test_qt_spec_parser_reports_the_full_version() -> None:
    parser = "f.read().split(\"=\", 1)[1].strip().strip(\"'\\\"\")"
    assert parser in QT_SPEC.read_text(encoding="utf-8"), "Ortho4XP_Qt.spec parser changed"
    raw = ENGINE_VERSION_FILE.read_text(encoding="utf-8")
    assert raw.split("=", 1)[1].strip().strip("'\"") == expected_version()


@app_side
def test_schema_dump_parser_reports_the_full_version() -> None:
    assert 'if "version" in line and "=" in line:' in SCHEMA_DUMP.read_text(encoding="utf-8")
    for line in ENGINE_VERSION_FILE.read_text(encoding="utf-8").splitlines():
        if "version" in line and "=" in line:
            assert line.split("=", 1)[1].strip().strip("'\"") == expected_version()
            break
    else:
        pytest.fail("schema dumper would find no version line")


@app_side
def test_swift_reader_reports_the_full_version() -> None:
    """OrthoEngine.readVersion: first line whose left side is exactly 'version'."""
    assert "readVersion" in SWIFT_ENGINE.read_text(encoding="utf-8")
    for line in ENGINE_VERSION_FILE.read_text(encoding="utf-8").splitlines():
        head, sep, tail = line.partition("=")
        if not sep or head.strip() != "version":
            continue
        assert tail.strip().strip("'\"") == expected_version()
        break
    else:
        pytest.fail("the app's Swift reader would find no version line")


# ---------------------------------------------------------------------------
# The bump helper
# ---------------------------------------------------------------------------
@app_side
@pytest.mark.parametrize(
    "body,before,after,rewritten",
    [
        ("version='1.50.7'\n", "1.50.7", "1.50.8", "version='1.50.8'\n"),
        ("1.0.7\n", "1.0.7", "1.0.8", "1.0.8\n"),
        ("version='1.50.0'\n", "1.50.0", "1.50.1", "version='1.50.1'\n"),
        ("version='1.50.99'\n", "1.50.99", "1.50.100", "version='1.50.100'\n"),
        ("1.0.9\n", "1.0.9", "1.0.10", "1.0.10\n"),
    ],
)
def test_bump_increments_the_build_by_exactly_one(
    tmp_path: Path, body: str, before: str, after: str, rewritten: str
) -> None:
    target = tmp_path / "VERSION"
    target.write_text(body, encoding="utf-8")

    read = _helper(f'xptb_version_read "{target}"')
    assert read.returncode == 0, read.stderr
    assert read.stdout.strip() == before

    bumped = _helper(f'xptb_version_bump "{target}"')
    assert bumped.returncode == 0, bumped.stderr
    assert bumped.stdout.strip() == after
    # Shape survives: the surrounding text is untouched.
    assert target.read_text(encoding="utf-8") == rewritten


@app_side
def test_repeated_bumps_are_monotonic(tmp_path: Path) -> None:
    target = tmp_path / "O4_Version.py"
    target.write_text("# a comment\nversion='1.50.3'\n", encoding="utf-8")
    for expected in ("1.50.4", "1.50.5", "1.50.6"):
        result = _helper(f'xptb_version_bump "{target}"')
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == expected
    assert target.read_text(encoding="utf-8") == "# a comment\nversion='1.50.6'\n"


@app_side
def test_bump_ignores_version_numbers_in_comments(tmp_path: Path) -> None:
    """The helper matches the assignment the way make_engine.sh's own grep
    does, so a triple mentioned in prose can never become the build number."""
    target = tmp_path / "O4_Version.py"
    target.write_text("# see the 0.4.9 notes\nversion='1.50.3'\n", encoding="utf-8")

    assert _helper(f'xptb_version_read "{target}"').stdout.strip() == "1.50.3"
    assert _helper(f'xptb_version_bump "{target}"').stdout.strip() == "1.50.4"
    assert target.read_text(encoding="utf-8") == "# see the 0.4.9 notes\nversion='1.50.4'\n"


@app_side
def test_bump_replaces_the_file_atomically(tmp_path: Path) -> None:
    """Rewrite via a sibling temp file + rename: the destination is never
    a truncated half-write, and nothing is left behind."""
    target = tmp_path / "VERSION"
    target.write_text("1.0.4\n", encoding="utf-8")
    target.chmod(0o644)
    before_inode = target.stat().st_ino

    assert _helper(f'xptb_version_bump "{target}"').returncode == 0

    assert target.read_text(encoding="utf-8") == "1.0.5\n"
    assert target.stat().st_ino != before_inode, "in-place truncation, not a rename"
    assert target.stat().st_mode & 0o777 == 0o644, "permissions must survive the swap"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["VERSION"], "temp file left behind"


@app_side
def test_bump_refuses_a_file_without_a_version(tmp_path: Path) -> None:
    target = tmp_path / "VERSION"
    target.write_text("not a version\n", encoding="utf-8")
    result = _helper(f'xptb_version_bump "{target}"')
    assert result.returncode != 0
    assert target.read_text(encoding="utf-8") == "not a version\n", "left the file intact"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["VERSION"]


@app_side
def test_read_refuses_a_missing_file(tmp_path: Path) -> None:
    result = _helper(f'xptb_version_read "{tmp_path / "nope"}"')
    assert result.returncode != 0
    assert "not found" in result.stderr


@app_side
def test_bumped_engine_file_still_feeds_the_freeze_extraction(tmp_path: Path) -> None:
    """End-to-end of what make_engine.sh does: bump, then extract."""
    src = tmp_path / "src"
    src.mkdir()
    target = src / "O4_Version.py"
    target.write_bytes(ENGINE_VERSION_FILE.read_bytes())
    current = expected_version()
    expected_next = f"1.50.{int(current.rsplit('.', 1)[1]) + 1}"

    bumped = _helper(f'xptb_version_bump "{target}"')
    assert bumped.stdout.strip() == expected_next, bumped.stderr

    extracted = _zsh(
        "grep -m1 '^version' src/O4_Version.py | cut -d= -f2 | tr -d \" '\\\"\"", cwd=tmp_path
    )
    assert extracted.stdout.strip() == expected_next
    # …and the comment block still parses through the strictest reader.
    assert target.read_text(encoding="utf-8").split("=", 1)[1].strip().strip("'\"") == expected_next


# ---------------------------------------------------------------------------
# Wiring: the build scripts really do the bump, and the plist carries it
# ---------------------------------------------------------------------------
@app_side
def test_build_scripts_bump_their_own_version_file() -> None:
    engine = MAKE_ENGINE.read_text(encoding="utf-8")
    assert 'source "$ROOT/scripts/version.sh"' in engine
    assert 'xptb_version_bump "$ENGINE/src/O4_Version.py"' in engine
    # …before PyInstaller bakes src/ into the frozen tree.
    assert engine.index("xptb_version_bump") < engine.index("-m PyInstaller")

    app = MAKE_APP.read_text(encoding="utf-8")
    assert 'xptb_version_bump "$ROOT/Sources/XPTerrainBuilder/Resources/VERSION"' in app
    # …before swift build copies the VERSION resource into the bundle.
    assert app.index("xptb_version_bump") < app.index("\nswift build ")
    # …and after the refuse-if-running guard, so a refusal burns no number.
    assert app.index("is running from") < app.index("xptb_version_bump")


@app_side
def test_info_plist_template_carries_the_app_version() -> None:
    """Render make_app.sh's Info.plist heredoc without building the app."""
    lines = MAKE_APP.read_text(encoding="utf-8").splitlines()
    starts = [i for i, line in enumerate(lines) if line.endswith("<<PLIST")]
    assert starts, "Info.plist heredoc must be unquoted so the version expands"
    start = starts[0]
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "PLIST")
    body = "\n".join(lines[start + 1 : end])

    rendered = _zsh(
        'APP_VERSION="1.0.42"\nAPP_BUILD="42"\n'
        'ENGINE_VERSION="1.50.1793"\nCOMMIT_SHA="5883949fdeadbeef"\n'
        f"cat <<PLIST\n{body}\nPLIST\n"
    )
    assert rendered.returncode == 0, rendered.stderr
    plist = plistlib.loads(rendered.stdout.encode("utf-8"))
    assert plist["CFBundleShortVersionString"] == "1.0.42"
    assert plist["CFBundleVersion"] == "42"
    assert plist["CFBundleIdentifier"] == "com.novemberlima.XPTerrainBuilder"
    # The About box's other two thirds (beta plan §1 B3(3)) — without these
    # the packaged app can only report its own version number.
    assert plist["XPTBEngineVersion"] == "1.50.1793"
    assert plist["XPTBCommitSHA"] == "5883949fdeadbeef"


@app_side
def test_app_version_ships_as_a_swiftpm_resource() -> None:
    """Without this the app can only read its version from Info.plist, which
    `swift run` and the test runner do not have."""
    assert os.path.relpath(APP_VERSION_FILE, REPO_ROOT / "Sources" / "XPTerrainBuilder") == (
        "Resources/VERSION"
    )
    assert '.copy("Resources/VERSION")' in (REPO_ROOT / "Package.swift").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The tag scheme gate (docs/BETA-PLAN-20260916.md §1 B3)
#
# `v1.0.<app-build>[-beta.N]`: the tag's numeric part IS the tracked app
# version at the tagged commit, or the release refuses in the first step of
# every job rather than after an hour of freezing and notarizing.
# ---------------------------------------------------------------------------
CHECK_TAG = REPO_ROOT / "scripts" / "check_tag_version.sh"

tag_gate = pytest.mark.skipif(
    not CHECK_TAG.is_file(), reason="engine checked out standalone — no app tree"
)


def _tag_gate(ref: str, version: str, tmp_path: Path) -> subprocess.CompletedProcess:
    version_file = tmp_path / "VERSION"
    version_file.write_text(version + "\n", encoding="utf-8")
    return subprocess.run(
        ["/bin/bash", str(CHECK_TAG), ref, str(version_file)],
        capture_output=True,
        text=True,
    )


@tag_gate
def test_tag_gate_accepts_a_matching_tag(tmp_path: Path) -> None:
    for ref in ("refs/tags/v1.0.347", "refs/tags/v1.0.347-beta.2", "v1.0.347-beta.11"):
        result = _tag_gate(ref, "1.0.347", tmp_path)
        assert result.returncode == 0, f"{ref}: {result.stdout}{result.stderr}"
        assert "1.0.347" in result.stdout


@tag_gate
def test_tag_gate_refuses_a_mismatching_tag_and_prints_both(tmp_path: Path) -> None:
    result = _tag_gate("refs/tags/v1.0.346-beta.1", "1.0.347", tmp_path)
    assert result.returncode == 1, result.stdout
    both = result.stdout + result.stderr
    assert "1.0.346" in both and "1.0.347" in both, both


@tag_gate
def test_tag_gate_refuses_an_off_scheme_tag(tmp_path: Path) -> None:
    for ref in ("refs/tags/v1.0.347-rc1", "refs/tags/v1.0-beta.1", "refs/tags/v1.0.347beta"):
        result = _tag_gate(ref, "1.0.347", tmp_path)
        assert result.returncode == 1, f"{ref} was accepted: {result.stdout}"


@tag_gate
def test_tag_gate_passes_a_non_tag_ref(tmp_path: Path) -> None:
    """workflow_dispatch must stay buildable off any branch."""
    result = _tag_gate("refs/heads/main", "1.0.347", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@tag_gate
def test_tag_gate_runs_first_in_every_release_job() -> None:
    """Every job checks out, then checks the tag — before anything expensive.

    Textual, not YAML: no yaml module is installed in the engine venv, and
    this assertion is about ORDER inside the file anyway.
    """
    text = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    chunks = text.split("- uses: actions/checkout@v4")
    assert len(chunks) - 1 == 4, "expected four jobs, each starting with a checkout"
    for chunk in chunks[1:]:
        head = chunk[:600]
        assert "check_tag_version.sh" in head, head
