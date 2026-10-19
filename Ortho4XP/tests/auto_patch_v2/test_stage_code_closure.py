"""issue #842 (B3-10, spec ``v2-stage-cache-spec.md`` §4, T3) — EACH CACHED
V2 STAGE'S CODE KEY IS THE IMPORT CLOSURE of its entry modules.

``pipeline/stage_code.CODE_MODULES[stage]`` is a declared list; this twin
recomputes each stage's closure from the SOURCES with the shared walker
(``src/O4_Code_Closure.py`` — the partition twin's, generalised) and fails
on a module the stage imports and its list omits (a STALE HIT after an
edit there), and on a listed module the stage no longer imports.  The
freeze digests reproduce from the specs' by-path execution.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

import O4_Code_Closure as CLOSURE
from auto_patch_v2.airport import partition_code as PCODE
from auto_patch_v2.pipeline import stage_code as SCODE

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _drift(src: Path, entries, declared, prefixes) -> tuple[list, list]:
    """``(missing, extra)``: closure modules the list omits, listed
    modules outside the closure."""
    closure = set(CLOSURE.closure(str(src), entries, prefixes))
    return sorted(closure - set(declared)), sorted(set(declared) - closure)


@pytest.mark.parametrize("stage", SCODE.STAGES)
def test_every_module_a_stage_imports_is_in_its_code_key(stage):
    missing, extra = _drift(SRC, SCODE.ENTRY_MODULES[stage],
                            SCODE.CODE_MODULES[stage], SCODE.CLOSURE_PREFIXES)
    assert not missing, (
        f"the {stage} stage imports these and stage_code.CODE_MODULES"
        f"[{stage!r}] does not key on them — a change there would be a "
        f"STALE HIT; add them: {missing}")
    assert not extra, (
        f"stage_code.CODE_MODULES[{stage!r}] names modules the stage does "
        f"not import; drop them: {extra}")
    listed = SCODE.CODE_MODULES[stage]
    assert list(listed) == sorted(set(listed))          # one order, no repeats
    assert all(os.path.isfile(CLOSURE.source_path(str(SRC), m)) for m in listed)


def test_the_stages_are_the_specs_cached_stages():
    from auto_patch_v2.constraints import GENERATORS
    assert SCODE.STAGES == ("classify", "planar", "flat_site", "road_profile",
                            "channels", "shapes",
                            *(SCODE.generator_stage(n) for n, _f in GENERATORS),
                            "constraints.assembly", "jetway_strip", "emit", "verify")
    assert set(SCODE.CODE_MODULES) == set(SCODE.STAGES)


def test_each_generator_is_entered_at_its_own_module():
    """spec §4b.1: ``constraints.<generator>`` keys on the closure of
    ``fn.__module__`` (one module's generators share the digest)."""
    from auto_patch_v2.constraints import GENERATORS
    assert SCODE.GENERATOR_MODULES == {
        n: fn.__module__.rsplit(".", 1)[1] for n, fn in GENERATORS}
    for n, fn in GENERATORS:
        assert SCODE.ENTRY_MODULES[SCODE.generator_stage(n)] == (fn.__module__,)
    digests = SCODE.runtime_digests()
    assert (digests[SCODE.generator_stage("taxi_chain")]
            == digests[SCODE.generator_stage("taxi_box")])
    assert (digests[SCODE.generator_stage("taxi_chain")]
            != digests[SCODE.generator_stage("water_pins")])


def test_the_back_half_entries_are_where_the_prefix_enters_them():
    from auto_patch_v2.airport import riders
    from auto_patch_v2.constraints import assembly, jetway_strip
    from auto_patch_v2.pipeline import constraint_records as CR
    from auto_patch_v2.pipeline import shapes
    assert CR.assemble.__module__ == assembly.__name__
    assert CR.joint_filter.__module__ == shapes.__name__
    assert set(SCODE.ENTRY_MODULES["constraints.assembly"]) == {
        assembly.__name__, shapes.__name__}
    assert set(SCODE.ENTRY_MODULES["jetway_strip"]) == {
        riders.rider_candidates.__module__, jetway_strip.jetway_strips.__module__}


def test_the_entry_modules_are_where_the_build_enters_each_stage():
    """``pipeline/build.build`` calls these names; if one moves to another
    module, the stage's closure must be re-rooted there."""
    from auto_patch_v2 import classify
    from auto_patch_v2.airport import flat_site_read, road_profile, road_ramp
    from auto_patch_v2.constraints import apron_trend, eat, runway_chord, taxi_trend
    from auto_patch_v2.emit import road_join
    from auto_patch_v2.pipeline import shapes
    # ``planar/__init__`` re-exports ``build``, shadowing the submodule
    planar_build = importlib.import_module("auto_patch_v2.planar.build")
    # classify is entered in ``build``, the rest in its prefix (§10 step 8)
    pipe = SRC / "auto_patch_v2" / "pipeline"
    text = (pipe / "build.py").read_text(encoding="utf-8")
    assert "from ..classify import classify, load_rules" in text
    text = (pipe / "prefix.py").read_text(encoding="utf-8")
    for line in ("from ..planar.build import build as build_planar",
                 "from ..airport.flat_site_read import verdict_for_build as _flat_verdict",
                 "from ..airport.road_profile import preferred_road_z",
                 "from .shapes import shape_stage"):
        assert line in text, line
    defined = {
        "classify": {classify.classify.__module__, classify.load_rules.__module__},
        "planar": {planar_build.build.__module__},
        "flat_site": {flat_site_read.verdict_for_build.__module__},
        "road_profile": {road_profile.preferred_road_z.__module__},
        # the target channels the shape record is keyed on (#843)
        "channels": {runway_chord.with_runway_chord.__module__,
                     taxi_trend.with_taxi_trend.__module__,
                     apron_trend.with_apron_trend.__module__,
                     eat.withdraw_trend_over_reach.__module__,
                     road_ramp.with_road_ramp.__module__,
                     road_join.with_road_coverage_join.__module__},
        "shapes": {shapes.shape_stage.__module__},
    }
    front = {s: set(e) for s, e in SCODE.ENTRY_MODULES.items() if s in defined}
    assert front == defined


def _toy_tree(root: Path) -> Path:
    src = root / "src"
    pkg = src / "auto_patch_v2" / "pipeline"
    pkg.mkdir(parents=True)
    for d in (src / "auto_patch_v2", pkg):
        (d / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    (pkg / "entry.py").write_text("from . import helper\n", encoding="utf-8", newline="\n")
    (pkg / "helper.py").write_text("X = 1\n", encoding="utf-8", newline="\n")
    (pkg / "later.py").write_text("Y = 2\n", encoding="utf-8", newline="\n")
    return src


def test_the_twin_bites(tmp_path):
    """PLANTED: a stage that starts importing a module its list omits
    fails the check — at module level and inside a function."""
    src = _toy_tree(tmp_path)
    entries = ("auto_patch_v2.pipeline.entry",)
    declared = ("auto_patch_v2.pipeline.entry", "auto_patch_v2.pipeline.helper")
    prefixes = ("auto_patch_v2",)
    assert _drift(src, entries, declared, prefixes) == ([], [])
    (src / "auto_patch_v2" / "pipeline" / "entry.py").write_text(
        "from . import helper\n\ndef f():\n    from .later import Y\n    return Y\n",
        encoding="utf-8", newline="\n")
    assert _drift(src, entries, declared, prefixes) == (
        ["auto_patch_v2.pipeline.later"], [])
    # and the reverse: a listed module no longer imported
    assert _drift(src, ("auto_patch_v2.pipeline.helper",), declared, prefixes) == (
        [], ["auto_patch_v2.pipeline.entry"])
    # on the real tree: drop one module from one stage's list
    short = tuple(m for m in SCODE.CODE_MODULES["flat_site"]
                  if m != "auto_patch_v2.law.tables")
    assert _drift(SRC, SCODE.ENTRY_MODULES["flat_site"], short,
                  SCODE.CLOSURE_PREFIXES)[0] == ["auto_patch_v2.law.tables"]


_FREEZE = r"""
import json, os, runpy, sys
src, out = sys.argv[1], sys.argv[2]
assert not any(os.path.isfile(os.path.join(p or ".", "O4_Code_Closure.py"))
               for p in sys.path), "the helper must not be importable here"
stage = runpy.run_path(os.path.join(src, "auto_patch_v2", "pipeline", "stage_code.py"))
part = runpy.run_path(os.path.join(src, "auto_patch_v2", "airport", "partition_code.py"))
print(json.dumps({"stage": stage["write_freeze_digest"](src, out),
                  "partition": part["write_freeze_digest"](src, out)}))
"""


def test_the_freeze_digests_reproduce_by_path(tmp_path):
    """The specs execute ``stage_code.py`` / ``partition_code.py`` BY PATH
    with ``src`` off ``sys.path``: the shared helper is loaded by path, and
    the files written equal the checkout's digests."""
    import json
    script = tmp_path / "freeze.py"
    script.write_text(_FREEZE, encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    run = subprocess.run([sys.executable, "-I", str(script), str(SRC), str(out)],
                         cwd=str(tmp_path), capture_output=True, text=True,
                         encoding="utf-8", timeout=120)
    assert run.returncode == 0, run.stderr
    paths = json.loads(run.stdout.strip().splitlines()[-1])
    assert os.path.basename(paths["stage"]) == SCODE.DIGEST_FILENAME
    table = SCODE.frozen_digests(str(out))
    assert table == SCODE.freeze_digests(str(SRC))
    assert set(table) == set(SCODE.STAGES)
    # one digest per distinct closure (one module's generators share one)
    assert len(set(table.values())) == len({SCODE.CODE_MODULES[s] for s in SCODE.STAGES})
    # the partition file is unchanged in form: one line, its digest
    text = Path(paths["partition"]).read_text(encoding="ascii")
    assert text == PCODE.freeze_digest(str(SRC)) + "\n"
    assert PCODE.frozen_digest(str(out)) == PCODE.freeze_digest(str(SRC))


def test_the_digest_table_reader_refuses_what_is_not_one(tmp_path):
    assert SCODE.frozen_digests(str(tmp_path)) is None              # a checkout
    path = tmp_path / SCODE.DIGEST_FILENAME
    path.write_text("planar not-a-digest\n", encoding="ascii", newline="\n")
    assert SCODE.frozen_digests(str(tmp_path)) is None
    path.write_text("a" * 64 + "\n", encoding="ascii", newline="\n")
    assert SCODE.frozen_digests(str(tmp_path)) is None              # no stage name
    with pytest.raises(SystemExit):                 # a listed module with no source
        SCODE.write_freeze_digest(str(tmp_path), str(tmp_path / "o5"))
    assert not (tmp_path / "o5" / SCODE.DIGEST_FILENAME).exists()


def test_an_edit_to_one_stage_module_moves_only_the_stages_that_import_it(
        tmp_path, monkeypatch):
    before = SCODE.freeze_digests(str(SRC))
    real = CLOSURE.source_path
    edited = tmp_path / "flat_site.py"
    edited.write_bytes((SRC / "auto_patch_v2" / "airport" / "flat_site.py").read_bytes()
                       + b"#\n")
    monkeypatch.setitem(SCODE._CLOSURE, "modules_digest",
                        lambda root, mods: CLOSURE.digest_of(
                            (m, str(edited) if m == "auto_patch_v2.airport.flat_site"
                             else real(root, m)) for m in mods))
    after = SCODE.freeze_digests(str(SRC))
    for stage in SCODE.STAGES:
        keyed = "auto_patch_v2.airport.flat_site" in SCODE.CODE_MODULES[stage]
        assert (after[stage] != before[stage]) == keyed, stage


def test_both_specs_write_and_bundle_the_stage_digests():
    for spec in ("Ortho4XP.spec", "Ortho4XP_Qt.spec"):
        text = (ROOT / spec).read_text(encoding="utf-8")
        assert '"pipeline", "stage_code.py")\n)["write_freeze_digest"]("src"' in text, spec
        assert '(_stage_digest_file, os.path.join("auto_patch_v2", "pipeline"))' in text, spec
