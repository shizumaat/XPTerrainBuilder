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
import shutil
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


#: The build scripts are zsh scripts and these tests run them for real.
#: ``/bin/zsh`` ships with macOS but not with the Linux or Windows CI
#: runners, where the whole subprocess raises ``FileNotFoundError`` and 19
#: tests go red for the shell's absence rather than for anything about the
#: version scheme.  The skip lives in the helper, not on 19 decorators, so a
#: test added later inherits it.
ZSH = Path("/bin/zsh")

#: The release gates are bash scripts; on Windows that is Git bash on PATH
#: (the CI job runs under it), never a literal /bin/bash (#92).
BASH = "/bin/bash" if os.path.exists("/bin/bash") else shutil.which("bash")


def _sh_path(p) -> str:
    """A script/file argument bash can open on every OS (#92)."""
    return Path(p).as_posix()


def _zsh(script: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a zsh snippet under the build scripts' own shell options."""
    if not ZSH.exists():
        pytest.skip(f"{ZSH} absent — the build scripts' shell ships with macOS only")
    return subprocess.run(
        [str(ZSH), "-c", script],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def _helper(script: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a snippet with scripts/version.sh sourced, as the scripts do.

    THE RUNNER'S OWN MARKER IS UNSET FIRST (#76).  ``xptb_version_bump`` has
    a NO-BUMP MODE — "print the CURRENT version and write nothing" — taken
    when ``GITHUB_ACTIONS=true`` or ``XPTB_NO_BUMP=1``, because a CI build
    must package the tagged tree's version as it is (owner ruling, Release
    run 35239347609: the mac job bumped on the runner and shipped 1.0.348
    for a tree and a tag at 1.0.347).  Every GitHub runner sets
    ``GITHUB_ACTIONS=true``, so on CI the nine twins below that exercise the
    LOCAL bump path were silently handed the CI path instead and asserted
    '1.50.3' == '1.50.4' — the helper working exactly as ruled, and the
    twins measuring the wrong branch of it.  They are green on a developer's
    machine, which is why nothing caught it until CI collected the whole
    suite.

    Unsetting here rather than on nine call sites: a twin added later
    inherits it, and it cannot weaken the no-bump law, which is asserted by
    its OWN twins (``test_ci_bump_writes_nothing_and_reports_the_current_version``
    for both spellings, and ``test_ci_bump_works_for_the_engine_assignment_shape_too``).
    Those set their prefix INLINE on the command, which still overrides a
    plain unset, so they are unaffected.
    """
    preamble = (f"set -euo pipefail\nunset GITHUB_ACTIONS XPTB_NO_BUMP\n"
                f"source {VERSION_SH!s}\n")
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
    target.write_text(body, encoding="utf-8", newline="")

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
    target.write_text("# a comment\nversion='1.50.3'\n", encoding="utf-8", newline="")
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
    target.write_text("# see the 0.4.9 notes\nversion='1.50.3'\n", encoding="utf-8", newline="")

    assert _helper(f'xptb_version_read "{target}"').stdout.strip() == "1.50.3"
    assert _helper(f'xptb_version_bump "{target}"').stdout.strip() == "1.50.4"
    assert target.read_text(encoding="utf-8") == "# see the 0.4.9 notes\nversion='1.50.4'\n"


@app_side
def test_bump_replaces_the_file_atomically(tmp_path: Path) -> None:
    """Rewrite via a sibling temp file + rename: the destination is never
    a truncated half-write, and nothing is left behind."""
    target = tmp_path / "VERSION"
    target.write_text("1.0.4\n", encoding="utf-8", newline="")
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
    target.write_text("not a version\n", encoding="utf-8", newline="")
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
    assert APP_VERSION_FILE.relative_to(REPO_ROOT / "Sources" / "XPTerrainBuilder").as_posix() == (
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
CHECK_BLOCKERS = REPO_ROOT / "scripts" / "check_beta_blockers.sh"

tag_gate = pytest.mark.skipif(
    not CHECK_TAG.is_file(), reason="engine checked out standalone — no app tree"
)


def _blocker_gate(tag: str) -> subprocess.CompletedProcess:
    """The beta-2 blocker gate on its own, over the repo's real list."""
    return subprocess.run(
        [BASH, _sh_path(CHECK_BLOCKERS), tag],
        capture_output=True,
        text=True,
    )


def _tag_gate(ref: str, version: str, tmp_path: Path) -> subprocess.CompletedProcess:
    version_file = tmp_path / "VERSION"
    version_file.write_text(version + "\n", encoding="utf-8", newline="")
    return subprocess.run(
        [BASH, _sh_path(CHECK_TAG), ref, _sh_path(version_file)],
        capture_output=True,
        text=True,
    )


@tag_gate
def test_tag_gate_accepts_a_matching_tag(tmp_path: Path) -> None:
    """The SCHEME half accepts a matching tag, in every spelling.

    This asserted ``rc == 0`` until the BETA-2 BLOCKER GATE was chained
    onto the end of ``check_tag_version.sh`` (owner standing 2026-09-18,
    repo CLAUDE.md "Beta 2 gate": no tag past beta.1 while a row of
    docs/BETA2-BLOCKERS.md is not CLOSED/WAIVED).  A `-beta.N>=2` or plain
    release tag now exits 1 on an open list — the gate working, not the
    scheme refusing — so the scheme verdict is asserted by its own
    sentence here, and the exit code is the subject of
    ``test_the_blocker_gate_decides_a_scheme_good_tags_exit_code`` below.
    """
    for ref in ("refs/tags/v1.0.347", "refs/tags/v1.0.347-beta.2", "v1.0.347-beta.11"):
        result = _tag_gate(ref, "1.0.347", tmp_path)
        assert "matches the tree app version 1.0.347" in result.stdout, (
            f"{ref}: {result.stdout}{result.stderr}")


@tag_gate
def test_tag_gate_accepts_a_matching_beta_1_tag_outright(tmp_path: Path) -> None:
    """END TO END rc 0 — the path the blocker gate does not touch.

    ``check_beta_blockers.sh`` passes a `-beta.1` tag with a note (beta 1
    predates the list), so this tag exercises BOTH halves of the gate and
    still exits 0, whatever state the blocker list is in.
    """
    result = _tag_gate("refs/tags/v1.0.347-beta.1", "1.0.347", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "matches the tree app version 1.0.347" in result.stdout
    assert "blocker list not enforced" in result.stdout


@tag_gate
def test_the_blocker_gate_decides_a_scheme_good_tags_exit_code(tmp_path: Path) -> None:
    """The beta-2 blocker gate is CHAINED after the scheme check, and for a
    scheme-good tag the gate's exit code IS the blocker gate's.

    Stated as an identity against a direct run rather than as a fixed
    verdict, so this twin holds both while the list has open rows (it
    refuses) and after the owner closes them (it passes) — the law is the
    chaining, not today's count.
    """
    assert "check_beta_blockers.sh" in CHECK_TAG.read_text(encoding="utf-8"), (
        "the tag gate must call the beta-2 blocker gate (owner standing "
        "2026-09-18); an unchained tag gate lets beta 2 be cut over open rows")
    ref, tag = "refs/tags/v1.0.347-beta.2", "v1.0.347-beta.2"
    chained = _tag_gate(ref, "1.0.347", tmp_path)
    direct = _blocker_gate(tag)
    assert chained.returncode == direct.returncode, (
        f"chained rc {chained.returncode} != blocker gate rc "
        f"{direct.returncode}\nchained: {chained.stdout}{chained.stderr}"
        f"\ndirect: {direct.stdout}{direct.stderr}")
    assert "matches the tree app version 1.0.347" in chained.stdout


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


def _release_jobs() -> dict[str, str]:
    """``{job name: its block}`` for .github/workflows/release.yml.

    Textual, not YAML: no yaml module is installed in the engine venv, and
    the assertions below are about ORDER inside the file anyway.  A job is
    a top-level key of ``jobs:``, i.e. a line indented exactly two spaces.
    """
    text = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    body = text.split("\njobs:\n", 1)[1]
    jobs: dict[str, str] = {}
    name = None
    for line in body.splitlines(keepends=True):
        head = re.fullmatch(r"  ([A-Za-z_][\w-]*):\s*\n", line)
        if head:
            name = head.group(1)
            jobs[name] = ""
            continue
        if name:
            jobs[name] += line
    return jobs


@tag_gate
def test_tag_gate_runs_first_in_every_release_job() -> None:
    """Every job that can do expensive work checks out, then checks the tag.

    This counted FOUR checkouts until ``xplat_gate`` was added (§46 (7),
    "one programme on every platform").  That job is the one lawful
    exception and is asserted as such rather than dropped from the count:
    it ``needs: [mac, windows, linux]``, so a mismatching tag has already
    refused in all three before it can start, and it only downloads their
    artifacts.  Derived from the file's own job blocks so the next job
    added is CHECKED, not counted.
    """
    jobs = _release_jobs()
    assert set(jobs) >= {"mac", "windows", "linux", "release"}, sorted(jobs)

    gated = {n for n, b in jobs.items()
             if "actions/checkout@v4" in b
             and "check_tag_version.sh" in b.split("- uses: actions/checkout@v4", 1)[1][:600]}
    assert {"mac", "windows", "linux", "release"} <= gated, (
        f"jobs that check out without checking the tag first: "
        f"{sorted(set(jobs) - gated)}")

    for name, block in jobs.items():
        if name in gated or "actions/checkout@v4" not in block:
            continue
        needs = re.search(r"^    needs:\s*\[([^\]]*)\]", block, re.MULTILINE)
        assert needs, (
            f"{name} checks out without the tag gate and without needs: — "
            f"nothing has checked the tag before it runs")
        upstream = {n.strip() for n in needs.group(1).split(",") if n.strip()}
        assert upstream and upstream <= gated, (
            f"{name} skips the tag gate but needs {sorted(upstream)}, which "
            f"is not a subset of the gated jobs {sorted(gated)}")


# ---------------------------------------------------------------------------
# NO-BUMP MODE: a CI build packages the tagged tree's version AS IS
#
# Measured on Release run 35239347609 (owner ruling, round 2): the mac job
# ran make_engine.sh and make_app.sh, which bumped ON THE RUNNER, so the mac
# artifact carried app 1.0.348 / engine 1.50.1794 for a tree and a tag at
# 1.0.347 / 1.50.1793 — while the Windows and Linux artifacts, which never
# run those scripts, carried the tree's numbers.  One release, three
# artifacts, three different versions.  Only a LOCAL build mints a number.
# ---------------------------------------------------------------------------
@app_side
@pytest.mark.parametrize("prefix", ["GITHUB_ACTIONS=true", "XPTB_NO_BUMP=1"])
def test_ci_bump_writes_nothing_and_reports_the_current_version(
    tmp_path: Path, prefix: str
) -> None:
    target = tmp_path / "VERSION"
    target.write_text("1.0.347\n", encoding="utf-8", newline="")
    before = target.read_bytes()

    result = _helper(f'{prefix} xptb_version_bump "{target}"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.0.347"
    assert target.read_bytes() == before, "the version file must be untouched"
    # And it says so, so a job log never silently looks like a local build.
    assert "NOT bumped" in result.stderr, result.stderr


@app_side
def test_ci_bump_works_for_the_engine_assignment_shape_too(tmp_path: Path) -> None:
    target = tmp_path / "O4_Version.py"
    target.write_text("# a comment\nversion='1.50.1793'\n", encoding="utf-8", newline="")
    before = target.read_bytes()

    result = _helper(f'GITHUB_ACTIONS=true xptb_version_bump "{target}"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.50.1793"
    assert target.read_bytes() == before


@app_side
def test_bump_still_writes_by_default(tmp_path: Path) -> None:
    """The local path is the one that mints numbers; guard it beside the
    CI path so a future env-var change cannot silently disable both."""
    target = tmp_path / "VERSION"
    target.write_text("1.0.347\n", encoding="utf-8", newline="")
    result = _helper(f'GITHUB_ACTIONS= XPTB_NO_BUMP= xptb_version_bump "{target}"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.0.348"
    assert target.read_text(encoding="utf-8") == "1.0.348\n"


# ---------------------------------------------------------------------------
# The "-dirty" marker excludes a build's OWN version bump
# ---------------------------------------------------------------------------
TREE_DIRTY = REPO_ROOT / "scripts" / "tree_dirty.sh"

dirty_gate = pytest.mark.skipif(
    not TREE_DIRTY.is_file(), reason="engine checked out standalone — no app tree"
)


def _fake_repo(tmp_path: Path) -> Path:
    """A committed tree carrying both version files at their real paths."""
    root = tmp_path / "repo"
    (root / "Sources" / "XPTerrainBuilder" / "Resources").mkdir(parents=True)
    (root / "Ortho4XP" / "src").mkdir(parents=True)
    (root / "Sources" / "XPTerrainBuilder" / "Resources" / "VERSION").write_text(
        "1.0.347\n", encoding="utf-8", newline=""
    )
    (root / "Ortho4XP" / "src" / "O4_Version.py").write_text(
        "version='1.50.1793'\n", encoding="utf-8", newline=""
    )
    (root / "README.md").write_text("hello\n", encoding="utf-8", newline="")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "HOME": str(tmp_path)}
    for argv in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "base"],
    ):
        subprocess.run(argv, cwd=root, check=True, env=env, capture_output=True)
    return root


def _is_dirty(root: Path) -> bool:
    """scripts/tree_dirty.sh exits 0 for dirty, 1 for clean."""
    result = subprocess.run(
        [BASH, _sh_path(TREE_DIRTY), _sh_path(root)], capture_output=True, text=True
    )
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


@dirty_gate
def test_a_clean_tree_is_not_dirty(tmp_path: Path) -> None:
    assert _is_dirty(_fake_repo(tmp_path)) is False


@dirty_gate
def test_a_builds_own_version_bump_is_not_dirt(tmp_path: Path) -> None:
    """Otherwise EVERY local build stamps "-dirty" and the marker says
    nothing: make_app.sh/make_engine.sh bump before anything stamps a sha."""
    root = _fake_repo(tmp_path)
    (root / "Sources" / "XPTerrainBuilder" / "Resources" / "VERSION").write_text(
        "1.0.348\n", encoding="utf-8", newline=""
    )
    (root / "Ortho4XP" / "src" / "O4_Version.py").write_text(
        "version='1.50.1794'\n", encoding="utf-8", newline=""
    )
    assert _is_dirty(root) is False


@dirty_gate
def test_any_other_change_is_dirt(tmp_path: Path) -> None:
    root = _fake_repo(tmp_path)
    (root / "README.md").write_text("edited\n", encoding="utf-8", newline="")
    assert _is_dirty(root) is True


@dirty_gate
def test_another_change_alongside_the_bump_is_still_dirt(tmp_path: Path) -> None:
    root = _fake_repo(tmp_path)
    (root / "Sources" / "XPTerrainBuilder" / "Resources" / "VERSION").write_text(
        "1.0.348\n", encoding="utf-8", newline=""
    )
    (root / "README.md").write_text("edited\n", encoding="utf-8", newline="")
    assert _is_dirty(root) is True


@dirty_gate
def test_the_stampers_use_the_one_dirty_predicate() -> None:
    """Two callers, one rule — a second hand-written `git diff --quiet HEAD`
    is how the marker drifted apart in the first place."""
    for script in ("make_app.sh", "write_version_txt.sh"):
        text = (REPO_ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert "tree_dirty.sh" in text, script
        assert "git diff --quiet HEAD" not in text, script
