"""THE FROZEN POOL PASS'S GATE, AND THE ENTRY IT READS (issue #362; owner
RULINGS 2026-10-05d (2)).

The suite never freezes, so what is twinned here is (1) the verdict
``scripts/check_frozen_pool.py`` passes on a pair of ``--pool-selfcheck``
records — a fallback, a serial pool, an unequal digest, a nested child
without its share, an orphan: each is a refusal that names itself — and
(2) the engine entry itself, run from source in a child process exactly as
the pass runs the bundle.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys

import pytest

import O4_Pool_Selfcheck as SC

ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(ENGINE_ROOT)


def _script(name):
    path = os.path.join(REPO_ROOT, "scripts", name)
    spec = importlib.util.spec_from_file_location("_" + name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CP = _script("check_frozen_pool.py")


def _pools(workers=4):
    return {name: {"workers": workers, "parallel": workers > 1, "fell_back": False,
                   "reason": "" if workers > 1 else "budget 1", "wall_s": 0.5,
                   "tasks": 8 if workers > 1 else 0} for name in CP.SECTIONS}


def _pair():
    pooled = {"ok": True, "failures": [], "workers": 4, "frozen": True, "cpu": 4,
              "digest": "d1", "sections": {}, "pools": _pools(), "pid": 10,
              "pids": [11, 12, 13], "blocks": ["psm_a"], "orphans": [],
              "leaked_blocks": [],
              "kill": {"pid": 60, "pids": [61, 62], "blocks": ["psm_k1", "psm_k2"],
                       "orphans": [], "leaked_blocks": [], "gone_s": 0.3},
              "nested": [{"pid": 20 + k, "budget": 2, "cpu": 4, "daemon": False,
                          "digest": "d1", "pids": [30 + k, 40 + k],
                          "pools": _pools(2)} for k in range(2)]}
    serial = {"ok": True, "failures": [], "workers": 1, "frozen": True,
              "digest": "d1", "sections": {}, "pools": _pools(1), "pid": 50,
              "pids": [51, 52], "blocks": [], "nested": []}
    return pooled, serial


def test_a_clean_pair_is_a_pass():
    assert CP.verdict(*_pair()) == []


def _broken(edit):
    pooled, serial = _pair()
    edit(pooled, serial)
    return " | ".join(CP.verdict(pooled, serial))


@pytest.mark.parametrize("edit, said", [
    (lambda p, s: p["pools"]["pack"].update(fell_back=True, reason="a worker died"),
     "pack pool FELL BACK (a worker died)"),
    (lambda p, s: p["pools"]["spawn"].update(workers=1, parallel=False, reason="budget 1"),
     "spawn pool ran SERIAL"),
    (lambda p, s: p["pools"]["dem"].update(tasks=0), "dem pool's workers answered 0 tasks"),
    (lambda p, s: p["pools"].pop("object"), "no account of the object pool"),
    (lambda p, s: p.update(pids=[11]), "fewer than two worker processes"),
    (lambda p, s: p.update(frozen=False), "did not run frozen"),
    (lambda p, s: s.update(digest="d2"), "EQUALITY: pooled digest d1 != one-core digest d2"),
    (lambda p, s: s.update(workers=4), "one-core arm ran with 4 workers"),
    (lambda p, s: p["nested"].pop(), "nested: 1 of 2 airport-pool children"),
    (lambda p, s: p["nested"][0].update(budget=4), "budget 4, want 2 (set_share)"),
    (lambda p, s: p["nested"][1].update(digest="dx"), "nested child 21: digest dx != d1"),
    (lambda p, s: p["nested"][0]["pools"]["pack"].update(fell_back=True, reason="x"),
     "nested child 20: the pack pool FELL BACK"),
    (lambda p, s: p["nested"][0].update(pids=[]), "fewer than two workers of its own"),
    (lambda p, s: p.update(orphans=[13]), "orphans [13]"),
    (lambda p, s: p.pop("kill"), "did not hard-kill a pool over shared blocks"),
    (lambda p, s: p["kill"].update(pids=[61]), "did not hard-kill a pool"),
    (lambda p, s: p["kill"].update(orphans=[62]),
     "after the bundle hard-killed a pool's parent: orphans [62]"),
    (lambda p, s: p["kill"].update(leaked_blocks=["psm_k2"]),
     "blocks still openable ['psm_k2']"),
    (lambda p, s: p.update(failures=["teardown: x"]), "pooled arm: teardown: x"),
])
def test_every_refusal_names_itself(edit, said):
    assert said in _broken(edit)


def test_a_missing_record_and_a_printed_fallback_are_refusals():
    pooled, serial = _pair()
    assert "wrote no record" in " ".join(CP.verdict(None, serial))
    assert "one-core arm wrote no record" in " ".join(CP.verdict(pooled, None))
    said = CP.verdict(pooled, serial, text="[pool] FELL BACK: could not start")
    assert said == ["the bundle printed 'FELL BACK'"]
    # a SOURCE arm is not asked to be frozen
    unfrozen = copy.deepcopy(pooled)
    unfrozen["frozen"] = False
    assert CP.verdict(unfrozen, serial, frozen=False) == []


def test_the_argv_puts_an_interpreter_in_front_of_a_source_entry_only():
    assert CP.selfcheck_argv("/b/Ortho4XP") == ["/b/Ortho4XP", "--pool-selfcheck"]
    assert CP.selfcheck_argv("/s/Ortho4XP.py", "/py") == [
        "/py", "/s/Ortho4XP.py", "--pool-selfcheck"]


def test_the_probes_read_a_process_and_a_block():
    from multiprocessing import shared_memory
    assert SC.alive(os.getpid())
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert not SC.alive(child.pid)
    block = shared_memory.SharedMemory(create=True, size=16)
    try:
        assert SC.block_exists(block.name)
    finally:
        block.close()
        block.unlink()
    assert not SC.block_exists(block.name)


def test_the_outside_kill_arm_names_what_outlived_the_engine():
    good = {"pool": {"fell_back": False}, "pids": [5, 6], "blocks": ["a", "b"],
            "manager": 4}
    assert CP.kill_verdict(good, [], [], [], 20.0) == []
    assert "wrote no record" in CP.kill_verdict(None, [], [], [], 20.0)[0]
    assert "KILL ARM ORPHAN: process(es) still alive 20 s" in CP.kill_verdict(
        good, [6], [], [], 20.0)[0]
    assert "of the bundle's image" in CP.kill_verdict(good, [], [(9, "x")], [], 20.0)[0]
    assert "KILL ARM LEAK" in CP.kill_verdict(good, [], [], ["b"], 20.0)[0]
    for edit in ({"pids": [5]}, {"blocks": ["a"]}, {"manager": None},
                 {"pool": {"fell_back": True}}):
        assert "was not an engine over an airport child" in CP.kill_verdict(
            dict(good, **edit), [], [], [], 20.0)[0]


def test_a_hard_killed_parent_leaves_no_worker_and_no_block(tmp_path):
    """THE KILL ARM, in this process: a child that owns a pool over the
    shared DEM and a shared array is SIGKILLed mid-map while its parent
    (here) lives on — so the resource tracker they share unlinks nothing.
    Every worker is gone and every block unopenable inside the wait."""
    said: list = []
    record, failures = SC._kill_arm(2, str(tmp_path), said.append)
    assert failures == [], failures
    assert record["busy"] == 2 and len(record["blocks"]) == 2
    assert record["orphans"] == [] and record["leaked_blocks"] == []
    assert record["gone_s"] < SC.KILL_S
    assert not any(SC.alive(pid) for pid in record["pids"])
    assert not any(SC.block_exists(name) for name in record["blocks"])
    assert said and said[0].startswith("kill: parent")


def test_a_run_that_leaves_one_of_its_own_blocks_open_fails_its_teardown(tmp_path,
                                                                         monkeypatch):
    """The Windows one-core failure, posed on any platform: this process
    still holding a block after its owner closed it is a refusal."""
    from auto_patch_v2.airport import pool as P
    SC.write_pack(str(tmp_path / "pack"))
    monkeypatch.setattr(P, "attached", lambda: ["wnsm_5f9c13bf"])
    got = SC._core(1, str(tmp_path), lambda _s: None)
    assert any("still has shared block(s) open" in f and "wnsm_5f9c13bf" in f
               for f in got["failures"]), got["failures"]
    monkeypatch.undo()
    assert SC._core(1, str(tmp_path), lambda _s: None)["failures"] == []
    assert P.attached() == []


def record_of(logs, tag):
    return json.loads((logs / ("pool-selfcheck-%s.json" % tag)).read_text(encoding="utf-8"))


def test_the_entry_runs_the_pool_from_source_and_the_gate_passes_it(tmp_path):
    """The whole pass on the SOURCE entry: two workers, the nested airport
    pool, the one-core arm, the outside teardown read."""
    logs = tmp_path / "logs"
    done = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "check_frozen_tile.py"),
         os.path.join(ENGINE_ROOT, "Ortho4XP.py"), "--pass", "pool",
         "--logs", str(logs), "--deadline", "240"],
        capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "POOL PASS OK" in done.stdout
    assert "after" in done.stdout and "0 alive, 0 of the image, 0 block(s) openable" \
        in done.stdout, done.stdout
    assert record_of(logs, "pooled")["kill"]["orphans"] == []
    victim = record_of(logs, "victim")
    assert victim["manager"] and victim["top"] and len(victim["blocks"]) == 2
    for pid in [victim["pid"], victim["top"], victim["manager"], *victim["pids"]]:
        assert not SC.alive(pid), pid
    record = json.loads((logs / "pool-selfcheck-pooled.json").read_text(encoding="utf-8"))
    assert record["ok"] and len(record["nested"]) == 2
    assert all(row["tasks"] > 0 and not row["fell_back"]
               for row in record["pools"].values())
    serial = json.loads((logs / "pool-selfcheck-onecore.json").read_text(encoding="utf-8"))
    assert serial["digest"] == record["digest"] and serial["workers"] == 1


WORKFLOWS = os.path.join(REPO_ROOT, ".github", "workflows")


@pytest.mark.skipif(not os.path.isdir(WORKFLOWS),
                    reason="engine checked out standalone — no workflows tree")
def test_every_frozen_job_runs_the_pool_pass_and_the_probe_is_dispatch_only():
    """The pass sits in each frozen job of the release (mac, Windows,
    Linux, the AppImage), and the probe that proves a branch BEFORE a tag
    freezes on all three platforms and fires on dispatch alone."""
    with open(os.path.join(WORKFLOWS, "release.yml"), encoding="utf-8") as handle:
        release = handle.read()
    assert release.count("--pass pool") == 4
    for binary in ("Ortho4XP/dist/Ortho4XP/Ortho4XP --pass pool",
                   "Ortho4XP/dist/Ortho4XP_Qt/Ortho4XP_Qt.exe --pass pool",
                   "Ortho4XP/dist/Ortho4XP_Qt/Ortho4XP_Qt --pass pool",
                   '"$APPRUN" --pass pool'):
        assert binary in release, binary
    with open(os.path.join(WORKFLOWS, "frozen-pool-probe.yml"),
              encoding="utf-8") as handle:
        probe = handle.read()
    body = "\n".join(line for line in probe.splitlines()
                     if not line.lstrip().startswith("#"))
    assert "workflow_dispatch:" in body
    for trigger in ("push:", "pull_request:", "schedule:"):
        assert trigger not in body, trigger
    for runner in ("macos-15", "windows-latest", "ubuntu-22.04"):
        assert "runs-on: %s" % runner in body, runner
    assert body.count("--pass pool") == 3
    assert body.count("if: always()") == 3          # the logs upload, every arm


def test_a_windows_pool_never_asks_for_more_than_the_executor_allows(monkeypatch):
    """``ProcessPoolExecutor`` raises above 61 workers on Windows (its
    ``WaitForMultipleObjects`` ceiling): a 96-core machine there must get a
    pool of 61, not a fallback.  No Windows runner has the cores to show
    it, so the cap is read here."""
    from auto_patch_v2.airport import pool as P
    monkeypatch.setattr(sys, "platform", "win32")
    assert P.WorkPool(workers=200).workers == P.WINDOWS_MAX_WORKERS == 61
    monkeypatch.setattr(sys, "platform", "linux")
    assert P.WorkPool(workers=200).workers == 200
