"""TWINS FOR THE WINDOWS FULL-TILE SMOKE TEST (issue #250).

The thing under test here cannot be run in the suite: it builds a whole
tile over the real network on a Windows runner, which is why it is a
`workflow_dispatch` workflow and not a pytest case.  So what these twins
pin is everything about it that CAN rot silently between runs — and every
one of them is a way a smoke test goes quietly toothless:

1. **The marker lists are the ENGINE's own wording.**  The pass fails on a
   download give-up line and on a Windows poison line.  Both are literal
   strings, and a reworded engine message turns a FAIL into a PASS with no
   diff anywhere near the check.  So every give-up marker must still appear
   in ``Ortho4XP/src`` (the "could not be downloaded" entry was dropped
   before this landed for exactly that reason: it matched nothing).

2. **The config pins what would otherwise demand an X-Plane install.**
   ``texture_mode`` at ``default_xplane``/``airport_ortho`` and
   ``dsf_bathymetry=False`` each hard-error without a Global Scenery
   donor, and ``osm_regional_extracts`` ships ``True`` — on CYXY that is
   Canada's whole Geofabrik extract.  A default that moves must not
   silently change what the smoke test is testing.

3. **The step list is the front ends' own**, and is a subset of the
   engine's ``STEP_WEIGHTS`` — a renamed step key would otherwise make the
   build run NOTHING and still reach ``RunDone``.

4. **The source arm really is the same protocol entry** — ``_engine_argv``
   puts the interpreter in front of a ``.py`` and nothing in front of an
   exe, which is what lets ONE driver cover both arms instead of two
   recipes that drift.

5. **The workflow is dispatch-shaped, not a gate**, runs on Windows, and
   restores no cache: a cache restore would mean the run proved a download
   it never made.

6. **The Gateway helper never fails loudly and always records**, because a
   substituted build input that is not written down is the thing the brief
   forbids.

No test here reaches the network: the Gateway arms stub ``urlopen``
(``tests/conftest.py`` would refuse a real connect anyway, which is the
backstop rather than the mechanism).
"""
from __future__ import annotations

import ast
import base64
import importlib.util
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

_ENGINE = Path(__file__).resolve().parents[1]          # Ortho4XP/
_REPO = _ENGINE.parent
SCRIPTS = _REPO / "scripts"
WORKFLOW = _REPO / ".github" / "workflows" / "win-tile-smoke.yml"
INDEX = _REPO / "tools" / "INDEX.md"
DRIVER = SCRIPTS / "check_frozen_tile.py"
GATEWAY = SCRIPTS / "fetch_gateway_apt.py"


def _load(path: Path, name: str):
    """Import a repo-root script by path (it is not on sys.path)."""
    if not path.exists():                              # a lane worktree mirror
        pytest.skip(f"{path} is not in this checkout")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load(DRIVER, "_wintile_driver")


@pytest.fixture(scope="module")
def gateway():
    return _load(GATEWAY, "_wintile_gateway")


# ---------------------------------------------------------------------------
# 1. The marker lists are the engine's own wording
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def engine_text() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted((_ENGINE / "src").rglob("*.py")))


def test_every_giveup_marker_is_still_a_string_the_engine_prints(
        driver, engine_text):
    """A reworded engine message turns this pass's FAIL into a PASS with no
    diff anywhere near the check.  The marker list is therefore pinned to
    the source, not to memory."""
    missing = [m for m in driver.FULL_TILE_GIVEUP_MARKERS
               if m not in engine_text]
    assert missing == [], (
        "these give-up markers match nothing in Ortho4XP/src any more, so "
        "the full-tile pass would no longer notice a download that gave "
        "up: " + ", ".join(repr(m) for m in missing))


def test_every_retry_marker_is_still_a_string_the_engine_prints(
        driver, engine_text):
    missing = [m for m in driver.FULL_TILE_RETRY_MARKERS
               if m not in engine_text]
    assert missing == [], ", ".join(repr(m) for m in missing)


def test_the_poison_list_names_the_windows_classes(driver):
    """#171 (UnicodeEncodeError on a cp1252 console), #125 (a mangled
    non-ASCII airport name) and the Windows path/handle/locked-file class
    are what a Windows-only red looks like; none may drop out of the
    list."""
    markers = {m for m, _why in driver.FULL_TILE_POISON}
    for required in ("Traceback (most recent call last)", "WinError",
                     "UnicodeEncodeError", "cp1252", "PermissionError"):
        assert required in markers, required
    assert all(why.strip() for _m, why in driver.FULL_TILE_POISON), (
        "every poison marker carries a reason, so a red names the class "
        "rather than the string")


# ---------------------------------------------------------------------------
# 2. The config pins what would otherwise demand an X-Plane install
# ---------------------------------------------------------------------------
def _cfg(driver) -> dict:
    text = driver.FULL_TILE_CONFIG % {
        "icao": "CYXY", "cifp": "/x/Custom Data/CIFP",
        "scenery": "/x/Custom Scenery"}
    out = {}
    for line in text.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


@pytest.mark.parametrize("key,value", [
    # Each of these, at any other value, either needs a Global Scenery
    # donor or downloads a country-sized extract.
    ("texture_mode", "full_ortho"),
    ("dsf_bathymetry", "auto"),
    ("custom_overlay_src", ""),
    ("osm_regional_extracts", "False"),
    # And these are what make the pass REAL rather than another offline one.
    ("skip_downloads", "False"),
    ("skip_converts", "False"),
    ("auto_patch", "ICAO"),
    ("custom_dem", ""),
    ("base_elevation_source", "auto"),
    ("max_build_slots", "1"),
])
def test_the_full_tile_config_pins_its_load_bearing_keys(driver, key, value):
    assert _cfg(driver)[key] == value


def test_the_config_points_cifp_and_scenery_at_the_fixture_it_was_given(
        driver):
    cfg = _cfg(driver)
    assert cfg["cifp_data_path"] == "/x/Custom Data/CIFP"
    assert cfg["custom_scenery_dir"] == "/x/Custom Scenery"


def test_the_fixture_lays_out_an_xplane_root_cifp_resolution_accepts(
        driver, tmp_path):
    """``auto_patch.cifp_reader.xplane_root_from_cifp_path`` walks TWO
    levels up from the CIFP directory and requires a ``Custom Scenery``
    (or ``Resources``) there.  A fixture that got this wrong would make
    auto-patch refuse the whole tile, which is the ONE hard refusal a
    missing install produces."""
    data_root, xplane_root, subs = driver._write_full_tile_fixture(
        str(tmp_path), str(_REPO), 60, -136, "CYXY", None, None)
    cifp = Path(xplane_root) / "Custom Data" / "CIFP"
    assert (cifp / "CYXY.dat").is_file()
    assert cifp.parent.parent == Path(xplane_root)
    assert (Path(xplane_root) / "Custom Scenery").is_dir()
    # THE DATA ROOT STARTS EMPTY — that is what makes the download table
    # honest.  One file, the config.
    assert sorted(p.name for p in Path(data_root).iterdir()) == \
        ["Ortho4XP.cfg"]
    # And every substitution is recorded with what a real install has.
    assert len(subs) == 2
    for item in subs:
        assert item["input"]
        assert item["provided_from"]
        assert item["a_real_install_provides"]
        assert item["coverage_gap"]


# ---------------------------------------------------------------------------
# 3. The step list is the front ends' own, and the engine still knows it
# ---------------------------------------------------------------------------
def test_the_step_keys_are_the_engines_own(driver):
    """A renamed step key would make the build run NOTHING and still reach
    RunDone — a green smoke test over an empty plan."""
    source = (_ENGINE / "src" / "o4_engine" / "session.py").read_text(
        encoding="utf-8")
    for step in driver.FULL_TILE_STEPS:
        assert re.search(r'"%s"\s*:' % re.escape(step), source), (
            f"{step!r} is not a key of session.py's STEP_WEIGHTS any more")
    assert "overlays" not in driver.FULL_TILE_STEPS, (
        "the overlays step reads an X-Plane install by definition "
        "(custom_overlay_src) and has no business in this pass")
    assert driver.FULL_TILE_STEPS[:2] == ("vector", "mesh"), \
        driver.FULL_TILE_STEPS


# ---------------------------------------------------------------------------
# 4. ONE driver, both arms
# ---------------------------------------------------------------------------
def test_a_source_entry_gets_an_interpreter_and_a_frozen_one_does_not(
        driver):
    assert driver._engine_argv("/x/Ortho4XP.py", "/py") == \
        ["/py", "/x/Ortho4XP.py", "--engine-jsonl"]
    assert driver._engine_argv(r"C:\x\XPTerrainBuilder.exe", "/py") == \
        [r"C:\x\XPTerrainBuilder.exe", "--engine-jsonl"]
    # No interpreter named: this one, so the arm still runs.
    argv = driver._engine_argv("/x/Ortho4XP.py")
    assert argv[1:] == ["/x/Ortho4XP.py", "--engine-jsonl"] and argv[0]


def test_full_tile_is_a_pass_the_cli_accepts(driver, capsys):
    with pytest.raises(SystemExit):
        driver.main(["--help"])
    text = capsys.readouterr().out
    assert "full-tile" in text
    for flag in ("--icao", "--provider", "--zl", "--apt-dat", "--cifp-dat",
                 "--engine-python"):
        assert flag in text, flag


# ---------------------------------------------------------------------------
# 5. The download table separates what was DOWNLOADED from what was DERIVED
# ---------------------------------------------------------------------------
def test_the_table_never_counts_a_derived_file_as_a_download(driver,
                                                             tmp_path):
    root = tmp_path / "data"
    for rel, size in (("Elevation_data/a.hgt", 1000),
                      ("OSM_data/b.osm.bz2", 200),
                      ("Orthophotos/c.jpg", 300),
                      ("Tiles/d/textures/e.dds", 999999),
                      ("Geotiffs/f.tif", 500000)):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    out = tmp_path / "table.md"
    files, total, giveups = driver._download_table(
        str(root), "fetched https://viewfinderpanoramas.org/dem3/P08.zip\n"
                   "  server may be down or busy, new tentative in 5\n",
        str(out))
    # 3 downloaded files, 1500 bytes; the .dds and the .tif are DERIVED.
    assert (files, total) == (3, 1500)
    assert giveups == []
    text = out.read_text(encoding="utf-8")
    assert "viewfinderpanoramas.org" in text
    assert "Derived on the runner (NOT downloads)" in text
    assert "retry" in text


def test_the_table_reports_a_giveup_as_a_giveup(driver, tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    _f, _t, giveups = driver._download_table(
        str(root), "ERROR: every texture download failed (imagery source "
                   "'Arc')\n", str(tmp_path / "t.md"))
    # BOTH match, and that is right: "download failed" is the general
    # verdict and "every texture download failed" the imagery-wide one,
    # so the narrower marker never hides the broader row.
    assert sorted(m for m, _n, _first in giveups) == sorted(
        ["download failed", "every texture download failed"])


# ---------------------------------------------------------------------------
# 6. The Gateway helper: records always, never fails loudly, pins its console
# ---------------------------------------------------------------------------
def test_the_gateway_helper_pins_the_console_before_its_parser():
    """The rule every argparse-bearing tool obeys (``O4_Console_Encoding``,
    one derivation site): the pin is at module level, ahead of the
    parser."""
    tree = ast.parse(GATEWAY.read_text(encoding="utf-8"), filename=str(GATEWAY))
    pins = [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "configure_console_streams"]
    parsers = [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Attribute) and n.attr == "ArgumentParser"]
    assert pins and parsers
    assert min(pins) < min(parsers), (pins, parsers)


def test_the_gateway_helper_records_a_failure_and_does_not_raise(
        gateway, tmp_path, monkeypatch):
    """A Gateway outage is not an engine defect.  The helper must still
    write its record — the caller reads it, substitutes the fixture and
    reports the gap."""
    def _boom(*_a, **_k):
        raise OSError("the Gateway is down")
    monkeypatch.setattr(gateway.urllib.request, "urlopen", _boom)
    record = tmp_path / "gw.json"
    rc = gateway.main(["CYXY", "--out", str(tmp_path / "apt.dat"),
                       "--record", str(record)])
    assert rc == 1
    data = json.loads(record.read_text(encoding="utf-8"))
    assert data["ok"] is False
    assert "the Gateway is down" in data["error"]
    assert data["a_real_install_provides"] and data["coverage_gap"]
    assert not (tmp_path / "apt.dat").exists()


def test_the_gateway_helper_writes_the_apt_dat_it_fetched(
        gateway, tmp_path, monkeypatch):
    apt = ("I\n1100 Version\n1 703 0 0 CYXY Erik Nielsen Whitehorse\n"
           "100 45.00 1 0 0.00 0 2 0 14 60.709 -135.072 0 0 3 0 0 0 "
           "32 60.717 -135.060 0 0 3 0 0 0\n")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("CYXY.dat", apt)
        archive.writestr("objects/deep/other.dat", "not this one")
    payload = {
        "/airport/CYXY": {"airport": {"recommendedSceneryId": 4242}},
        "/scenery/4242": {"scenery": {
            "masterZipBlob": base64.b64encode(buffer.getvalue()).decode()}},
    }

    class _Response:
        def __init__(self, body):
            self._body = body

        def read(self):
            return json.dumps(self._body).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def _urlopen(request, timeout=None):
        url = request.full_url
        for suffix, body in payload.items():
            if url.endswith(suffix):
                return _Response(body)
        raise AssertionError("unexpected URL %s" % url)

    monkeypatch.setattr(gateway.urllib.request, "urlopen", _urlopen)
    out = tmp_path / "apt.dat"
    record = tmp_path / "gw.json"
    rc = gateway.main(["cyxy", "--out", str(out), "--record", str(record)])
    assert rc == 0
    assert out.read_text(encoding="utf-8") == apt
    data = json.loads(record.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["icao"] == "CYXY"
    assert data["recommended_scenery_id"] == 4242
    # the pack root's own .dat, not the nested one
    assert data["zip_member"] == "CYXY.dat"
    assert data["has_airport_header"] is True
    assert data["url_hosts"] == ["gateway.x-plane.com"]


def test_the_fixture_substitution_is_used_when_the_gateway_missed(
        driver, tmp_path):
    """No apt.dat supplied: the repository fixture stands in AND the record
    says the Gateway fetch did not happen."""
    _data, xplane, subs = driver._write_full_tile_fixture(
        str(tmp_path), str(_REPO), 60, -136, "CYXY", None, None)
    apt = list((Path(xplane) / "Custom Scenery").rglob("apt.dat"))
    assert apt, "the fixture carries no apt.dat at all"
    gap = [s for s in subs if "apt.dat" in s["input"]][0]
    assert "FIXTURE" in gap["coverage_gap"] or "fixture" in gap["coverage_gap"]


# ---------------------------------------------------------------------------
# 7. The workflow is dispatch-shaped, Windows, and restores no cache
# ---------------------------------------------------------------------------
def test_the_workflow_invariants_hold_without_a_yaml_parser():
    """The same invariants as the parsed cases below, read as TEXT.

    PyYAML is not in the engine's requirements, so the parsed cases
    ``importorskip`` — and a skipped invariant is not an invariant.
    These four are the ones whose violation would be silent: a
    pull_request trigger (a two-hour network job on every push), a
    non-Windows runner, a cache restore (a run that proves a download it
    never made), and a push trigger that escaped its namespace.
    """
    if not WORKFLOW.exists():
        pytest.skip("no win-tile-smoke.yml in this checkout")
    body = "\n".join(
        line for line in WORKFLOW.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#"))
    assert "workflow_dispatch:" in body
    assert "pull_request:" not in body
    assert "runs-on: windows-latest" in body
    assert "actions/cache" not in body
    pushed = [line.strip() for line in body.splitlines()
              if line.strip().startswith("branches:")]
    assert pushed == ['branches: ["claude/wintile-run/**"]'], pushed


@pytest.fixture(scope="module")
def workflow() -> dict:
    yaml = pytest.importorskip("yaml")
    if not WORKFLOW.exists():
        pytest.skip("no win-tile-smoke.yml in this checkout")
    # PyYAML reads the bare `on:` key as the boolean True.
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_workflow_is_never_a_gate(workflow):
    triggers = workflow[True]
    assert set(triggers) <= {"push", "workflow_dispatch"}, sorted(triggers)
    assert "workflow_dispatch" in triggers
    assert "pull_request" not in triggers
    # The one push trigger is the bootstrap, scoped to a namespace that
    # matches no lane branch and `main` least of all.
    branches = (triggers.get("push") or {}).get("branches") or []
    assert all(b.startswith("claude/wintile-run/") for b in branches), branches
    assert not any(b in ("main", "**", "*") for b in branches)


def test_the_workflow_runs_on_windows_and_restores_no_cache(workflow):
    job = workflow["jobs"]["smoke"]
    assert job["runs-on"] == "windows-latest"
    assert job["timeout-minutes"] >= 60
    uses = [str(step.get("uses") or "") for step in job["steps"]]
    assert not any(u.startswith("actions/cache") for u in uses), (
        "a cache restore would mean this run proved a download it never "
        "made (#250 §3)")
    assert any(u.startswith("actions/upload-artifact") for u in uses)
    assert any(u.startswith("actions/checkout") for u in uses)


def test_the_workflow_drives_the_full_tile_pass(workflow):
    run_text = "\n".join(str(step.get("run") or "")
                         for step in workflow["jobs"]["smoke"]["steps"])
    assert "--pass full-tile" in run_text
    assert "check_frozen_tile.py" in run_text
    assert "fetch_gateway_apt.py" in run_text
    # Both arms, through the same driver.
    assert "Ortho4XP_Qt.exe" in run_text and "--engine-python" in run_text


# ---------------------------------------------------------------------------
# 8. The index (RULINGS 7e90032: a tool absent from it is treated as absent)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", [
    "scripts/fetch_gateway_apt.py",
    ".github/workflows/win-tile-smoke.yml",
])
def test_the_new_entries_each_have_exactly_one_index_row(path):
    if not INDEX.exists():                             # a lane worktree mirror
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    rows = [line for line in INDEX.read_text(encoding="utf-8").splitlines()
            if line.startswith("| `%s`" % path)]
    assert len(rows) == 1, (path, len(rows))


def test_the_driver_row_names_the_new_pass():
    if not INDEX.exists():
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    row = [line for line in INDEX.read_text(encoding="utf-8").splitlines()
           if line.startswith("| `scripts/check_frozen_tile.py`")]
    assert len(row) == 1
    assert "full-tile" in row[0]


# ---------------------------------------------------------------------------
# 9. The hostile PROJ environment is for the FROZEN arm only
# ---------------------------------------------------------------------------
def test_the_full_tile_pass_leaves_the_runners_proj_alone(driver):
    """Run 37033688936: the vector step died in 0.5 s with
    ``PROJ: proj_create_from_database: Cannot find proj.db`` and
    ``sys.frozen: False``.

    ``O4_Proj_Runtime``'s scrub is conditioned on the bundle — a FROZEN
    bundle must ignore a hostile ``PROJ_LIB`` because it ships its own
    proj.db, and a SOURCE tree inherits it, so GDAL refuses and the
    engine disables the build rather than degrade it.  Both behaviours
    are right; arming the hostile environment for the source arm was
    not.  The default stays armed so the frozen passes keep the check
    they have always had.
    """
    tree = ast.parse(DRIVER.read_text(encoding="utf-8"), filename=str(DRIVER))
    drive = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_drive")
    names = [a.arg for a in drive.args.args][-len(drive.args.defaults):]
    assert dict(zip(names, drive.args.defaults))["hostile_proj"].value is True, \
        "a frozen bundle must still face the hostile PROJ environment"

    full = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
                and n.name == "run_full_tile")
    passed = [kw.value.value for call in ast.walk(full)
              if isinstance(call, ast.Call)
              for kw in call.keywords if kw.arg == "hostile_proj"]
    assert passed == [False], (
        "the full-tile pass must leave the runner's PROJ environment "
        "alone — it runs the engine from the checkout, where the "
        "bundle's scrub does not apply")


# ---------------------------------------------------------------------------
# 10. The .dsf lives TWO levels under "Earth nav data"
# ---------------------------------------------------------------------------
def test_the_dsf_is_found_at_the_depth_fnames_actually_writes_it(driver,
                                                                 tmp_path):
    """Run 37034293088 built the tile — its own log read "DSF file encoded,
    total size is : 37996339 bytes (36.2M)" and "*Activating DSF file." —
    and the check reported "no .dsf … the tile produced no scenery at all".

    ``FNAMES.dsf_file`` joins ``build_dir`` + ``"Earth nav data"`` +
    ``long_latlon(lat, lon)``, and ``long_latlon`` is itself a TWO-LEVEL
    path (the 10-degree block, then the tile).  A glob one level short
    finds nothing — and silently made the ``.dsf.tmp`` leftover check
    vacuous too, so the Windows locked-file class it exists to catch
    could never have fired.
    """
    root = tmp_path / "data"
    built = (root / "Tiles" / "zOrtho4XP_+60-136" / "Earth nav data"
             / "+60-140")
    built.mkdir(parents=True)
    (built / "+60-136.dsf").write_bytes(b"XPLNEDSF" + b"\0" * 70000)
    found = driver._tile_dsfs(str(root))
    assert [Path(p).name for p in found] == ["+60-136.dsf"], found

    # A one-level spelling must be found too: `**` matches zero
    # directories, so the helper cannot be wrong either way.
    flat = root / "Tiles" / "zOrtho4XP_+00+000" / "Earth nav data"
    flat.mkdir(parents=True)
    (flat / "+00+000.dsf").write_bytes(b"XPLNEDSF")
    assert len(driver._tile_dsfs(str(root))) == 2

    # And the leftover check sees a temp file at the real depth.
    assert driver._tile_dsfs(str(root), ".dsf.tmp") == []
    (built / "+60-136.dsf.tmp").write_bytes(b"XPLNEDSF")
    assert [Path(p).name for p in driver._tile_dsfs(str(root), ".dsf.tmp")] \
        == ["+60-136.dsf.tmp"]
