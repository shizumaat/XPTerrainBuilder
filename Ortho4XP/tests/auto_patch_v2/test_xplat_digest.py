"""TWIN — the cross-platform stage digest (lane ``xplatdeterminism``).

The instrument's whole value rests on three properties, and each of them
is a way it could silently lie instead of failing:

1. the digest is ORDER-FREE (otherwise every platform "differs" because
   a dict happened to enumerate differently, and the real divergence is
   drowned);
2. the ROUNDING LADDER separates an ulp from a topology change (a single
   digest cannot, and that distinction is the attribution);
3. the pipeline actually WRITES it when armed, and not when it is not —
   the silent-degradation class (a replay arm publishing an empty list
   and reading a perfect family, memory ``sidecar-keys-published-…``).

Plus the release job must upload it on SUCCESS: a dump that travels only
when the job is red cannot answer why three GREEN platforms disagree,
which is the exact finding this lane exists for.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys

import pytest

from auto_patch_v2.pipeline import xplat

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))


def _items(n=200, seed=7):
    rng = random.Random(seed)
    return [("tag%d" % (k % 5), k, rng.uniform(-5000, 5000),
             rng.uniform(-5000, 5000)) for k in range(n)]


def test_digest_is_order_free():
    items = _items()
    shuffled = list(items)
    random.Random(13).shuffle(shuffled)
    assert shuffled != items
    assert xplat.digest(items) == xplat.digest(shuffled)


def test_the_rounding_ladder_separates_an_ulp_from_a_move():
    items = _items()
    # ONE vertex nudged by a last-ulp-sized amount: the finest rounding
    # must see it and the coarse ones must not.  That is what makes
    # "same up to ulp" distinguishable from "different topology".
    ulp = list(items)
    tag, k, x, y = ulp[3]
    ulp[3] = (tag, k, x + 1e-9, y)
    a, b = xplat.digest(items), xplat.digest(ulp)
    assert a["dp9"] != b["dp9"], "a 1e-9 m nudge must move the 9 dp digest"
    for dp in ("dp6", "dp4", "dp2", "dp1"):
        assert a[dp] == b[dp], f"a 1e-9 m nudge must NOT move {dp}"
    # A real move shows at every rounding.
    moved = list(items)
    moved[3] = (tag, k, x + 12.5, y)
    c = xplat.digest(moved)
    for dp in ("dp9", "dp6", "dp4", "dp2", "dp1"):
        assert a[dp] != c[dp], f"a 12.5 m move must show at {dp}"


def test_minus_zero_cannot_move_a_digest():
    assert (xplat.digest([("v", 0.0, 1.0)])
            == xplat.digest([("v", -1e-15, 1.0)]))


def test_compare_names_the_first_divergent_stage():
    base = {
        "icao": "CYXY",
        "env": {"machine": "arm64"},
        "stages": {
            "load": {"counts": {"pavements": 75},
                     "geometry": {"n": 10, "dp9": "aa"}},
            "planar": {"counts": {"vertices": 4289},
                       "vertices": {"n": 4289, "dp9": "bb"}},
        },
    }
    other = json.loads(json.dumps(base))
    other["env"]["machine"] = "x86_64"
    other["stages"]["planar"]["counts"]["vertices"] = 4300
    lines = xplat.compare({"mac": base, "linux": other})
    assert any(line.startswith("env machine") and "DIFFER" in line
               for line in lines)
    load = [ln for ln in lines if ln.startswith("load ")]
    assert load and all("AGREE" in ln for ln in load), (
        "load agrees here and must not be reported as divergent")
    planar = [ln for ln in lines
              if ln.startswith("planar ") and "DIFFER" in ln]
    assert planar and "counts.vertices" in planar[0]
    assert "4289" in planar[0] and "4300" in planar[0], (
        "the table must carry the NUMBERS, not just a verdict")


def test_the_arming_is_a_schema_flag_not_an_env_gate():
    """``test_model.py`` forbids an environment read anywhere in the v2
    package, so the dump is armed by ``Config.xplat_dump`` and the
    release check's request is translated in the v1 wrapper."""
    from auto_patch_v2.pipeline.build import Config
    assert Config().xplat_dump is False, "off by default"
    assert Config(xplat_dump=True).xplat_dump is True
    wrapper = open(os.path.join(_ROOT, "Ortho4XP", "src", "auto_patch",
                                "engine_v2.py"), encoding="utf-8").read()
    assert "O4_V2_XPLAT_DIGEST" in wrapper and "xplat_dump=" in wrapper, (
        "the wrapper is the ONE place the release check's request is read")


def test_build_writes_the_dump_only_when_armed():
    """The wiring, read off ``pipeline/build.py`` itself: the writer is
    reached through ``cfg.xplat_dump`` and nowhere else, and the dump
    goes in its OWN file so the report's schema is untouched."""
    source = open(os.path.join(_ROOT, "Ortho4XP", "src", "auto_patch_v2",
                               "pipeline", "build.py"),
                  encoding="utf-8").read()
    assert "from . import xplat as _xplat" in source, (
        "a TOP-LEVEL import — a function-level one is invisible to "
        "PyInstaller and the frozen bundle would have no dump at all "
        "(the highspy precedent)")
    assert "cfg.xplat_dump" in source
    assert "_xplat.write(" in source
    assert 'f"{icao}.xplat.json"' in source
    assert 'report["xplat"]' not in source, (
        "the dump must not change the v2 report's schema")


def test_the_environment_names_every_suspect_library():
    env = xplat.environment()
    for key in ("python", "machine", "platform", "geos_version",
                "geos_capi_version", "proj_version_str", "numpy",
                "numpy_blas", "scipy", "shapely", "pyproj"):
        assert key in env, f"the dump must record {key}"


def test_check_frozen_tile_compares_dumps_without_third_party(tmp_path):
    """``--compare`` must run under an interpreter with NO third-party
    package — the mac runner's bare python3 has no numpy, which is what
    killed a redundant LERC step.  It is asserted by RUNNING it in a
    subprocess with the site packages blocked."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    base = {"icao": "CYXY", "env": {"machine": "arm64"},
            "stages": {"load": {"counts": {"pavements": 75}},
                       "planar": {"counts": {"vertices": 4289}}}}
    a.write_text(json.dumps(base))
    other = json.loads(json.dumps(base))
    other["stages"]["planar"]["counts"]["vertices"] = 4300
    b.write_text(json.dumps(other))
    script = os.path.join(_ROOT, "scripts", "check_frozen_tile.py")
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    done = subprocess.run(
        [sys.executable, "-S", script, "--compare",
         "mac=%s" % a, "linux=%s" % b],
        capture_output=True, text=True, env=env)
    assert done.returncode == 2, done.stderr
    assert "FIRST DIVERGENT STAGE: planar" in done.stdout, done.stdout
    assert "load" in done.stdout and "4300" in done.stdout


def test_a_dump_of_one_platform_agrees_with_itself(tmp_path):
    a = tmp_path / "a.json"
    base = {"icao": "CYXY", "env": {"machine": "arm64"},
            "stages": {"load": {"counts": {"pavements": 75}}}}
    a.write_text(json.dumps(base))
    script = os.path.join(_ROOT, "scripts", "check_frozen_tile.py")
    done = subprocess.run(
        [sys.executable, "-S", script, "--compare",
         "mac=%s" % a, "mac2=%s" % a],
        capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.fixture(scope="module")
def workflow():
    path = os.path.join(_ROOT, ".github", "workflows", "release.yml")
    return open(path, encoding="utf-8").read()


def test_every_platform_uploads_its_dump_on_success(workflow):
    """The finding was three GREEN jobs that disagreed.  A dump gated on
    ``if: failure()`` would never have been written."""
    assert workflow.count("--xplat-dump") == 3, (
        "mac, Windows and Linux must each arm the dump")
    for platform in ("mac", "windows", "linux"):
        marker = "name: frozen-tile-logs-%s" % platform
        assert marker in workflow, platform
        block = workflow[:workflow.index(marker)]
        step = block[block.rindex("- name: Frozen tile build logs"):]
        assert "if: always()" in step, (
            "frozen-tile-logs-%s uploads only on failure — three green "
            "platforms could never be compared" % platform)
