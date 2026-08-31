"""Hermetic tests for tools/run_with_ledger.py (persistent run ledger).

All tests run in a throwaway git repo under tmp_path with the ledger
redirected via O4_RUN_LEDGER_PATH — no network, no airport builds, no
dependence on the real repo's state.
"""
import json
import os
import subprocess
import sys

import pytest

TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "tools", "run_with_ledger.py")


@pytest.fixture()
def ledger_repo(tmp_path, monkeypatch):
    """A minimal git repo shaped like the real one (src/ + tools/) with the
    ledger tool importable against it via O4_RUN_LEDGER_PATH redirect."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tools").mkdir()
    (repo / "src" / "module.py").write_text("VALUE = 1\n")
    env = dict(os.environ,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    for cmd in (["git", "init", "-q"],
                ["git", "add", "-A"],
                ["git", "commit", "-q", "-m", "seed"]):
        subprocess.run(cmd, cwd=repo, env=env, check=True,
                       capture_output=True)
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setenv("O4_RUN_LEDGER_PATH", str(ledger))
    return repo, ledger


def _run_tool(repo, extra, command, env_extra=None):
    """Invoke the tool with REPO_ROOT patched to the throwaway repo."""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    code = (
        "import runpy, sys, importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('rwl', {TOOL!r})\n"
        "rwl = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(rwl)\n"
        f"rwl.REPO_ROOT = {str(repo)!r}\n"
        f"sys.exit(rwl.main({extra!r} + ['--'] + {command!r}))\n"
    )
    return subprocess.run([sys.executable, "-c", code], env=env,
                          capture_output=True, text=True)


def test_miss_runs_and_records(ledger_repo):
    repo, ledger = ledger_repo
    result = _run_tool(repo, [], [sys.executable, "-c", "print('ran')"])
    assert result.returncode == 0
    assert "MISS" in result.stdout and "ran" in result.stdout
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(records) == 1 and records[0]["exit_code"] == 0


def test_identical_rerun_is_skipped(ledger_repo):
    repo, ledger = ledger_repo
    command = [sys.executable, "-c", "print('expensive')"]
    _run_tool(repo, [], command)
    second = _run_tool(repo, [], command)
    assert second.returncode == 0
    assert "HIT" in second.stdout
    assert len(ledger.read_text().splitlines()) == 1   # nothing re-recorded


def test_force_reruns(ledger_repo):
    repo, ledger = ledger_repo
    command = [sys.executable, "-c", "print('again')"]
    _run_tool(repo, [], command)
    forced = _run_tool(repo, ["--force"], command)
    assert "MISS" in forced.stdout or "running" in forced.stdout
    assert len(ledger.read_text().splitlines()) == 2


def test_code_change_invalidates(ledger_repo):
    repo, ledger = ledger_repo
    command = [sys.executable, "-c", "print('x')"]
    _run_tool(repo, [], command)
    (repo / "src" / "module.py").write_text("VALUE = 2\n")   # uncommitted
    second = _run_tool(repo, [], command)
    assert "MISS" in second.stdout
    assert len(ledger.read_text().splitlines()) == 2


def test_o4_env_keys_the_run(ledger_repo):
    repo, ledger = ledger_repo
    command = [sys.executable, "-c", "print('x')"]
    _run_tool(repo, [], command, env_extra={"O4_SOME_GATE": "1"})
    second = _run_tool(repo, [], command, env_extra={"O4_SOME_GATE": "0"})
    assert "MISS" in second.stdout


def test_failure_never_cached(ledger_repo):
    repo, ledger = ledger_repo
    command = [sys.executable, "-c", "import sys; sys.exit(3)"]
    first = _run_tool(repo, [], command)
    assert first.returncode == 3
    second = _run_tool(repo, [], command)
    assert second.returncode == 3
    assert "MISS" in second.stdout          # failed run is not reused


# ── the per-round tag (P2 instrument, item 3) ──────────────────────────
#
# The tag is an O4_* variable, and the run key is (tree, argv, O4_* env).
# If it reached the key, starting a round would invalidate EVERY recorded
# run — the instrument meant to price rounds would become the biggest cost
# in one.  These three tests are the guard on that.

def test_round_tag_is_recorded(ledger_repo):
    repo, ledger = ledger_repo
    _run_tool(repo, [], [sys.executable, "-c", "print('x')"],
              env_extra={"O4_ROUND_TAG": "p2-r1"})
    record = json.loads(ledger.read_text().splitlines()[-1])
    assert record["round_tag"] == "p2-r1"
    assert "O4_ROUND_TAG" not in record["env"], (
        "the tag must be a RECORDED FIELD, never part of the keyed env")


def test_round_tag_does_NOT_invalidate_the_ledger(ledger_repo):
    """Two runs, identical in every way but the round tag ⇒ still a HIT."""
    repo, ledger = ledger_repo
    command = [sys.executable, "-c", "print('expensive')"]
    first = _run_tool(repo, [], command, env_extra={"O4_ROUND_TAG": "r1"})
    assert "MISS" in first.stdout
    second = _run_tool(repo, [], command, env_extra={"O4_ROUND_TAG": "r2"})
    assert "HIT" in second.stdout, (
        "a new round tag re-ran an identical passing command — the tag is "
        "keying the run and the whole ledger invalidates every round")
    assert len(ledger.read_text().splitlines()) == 1


def test_history_attributes_wall_to_a_round(ledger_repo):
    repo, ledger = ledger_repo
    for n in (1, 2):
        _run_tool(repo, [], [sys.executable, "-c", f"print({n})"],
                  env_extra={"O4_ROUND_TAG": "r1"})
    _run_tool(repo, [], [sys.executable, "-c", "print(3)"],
              env_extra={"O4_ROUND_TAG": "r2"})
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    r1_wall = sum(r["duration_s"] for r in records
                  if r["round_tag"] == "r1")

    out = _run_tool(repo, ["--round", "r1"], []).stdout
    assert "round r1: 2 run(s)" in out
    assert f"{r1_wall:.1f}s wall" in out
    assert "round r2" not in out                     # filtered out
    assert "print(3)" not in out                     # and not listed

    everything = _run_tool(repo, ["--history", "10"], []).stdout
    assert "round r1: 2 run(s)" in everything
    assert "round r2: 1 run(s)" in everything


# ── THE TREE HASH COVERS EXACTLY CODE_PATHS ────────────────────────────
#
# It is a CODE hash: docs, STATUS and scratch churn must not move it.  It
# did, until 2026-08-30: the temporary index was seeded with
# ``git read-tree HEAD`` (the WHOLE tree) and then ``git add -A`` only over
# CODE_PATHS, so ``git write-tree`` hashed the HEAD ``docs/`` blobs too.
# The two-line ``docs/RULINGS.md`` commit 5b552ae1 moved the key
# 2f56b778… → b1ec5ef8… with ``git diff -- src tests tools`` empty, and the
# artifact ledger refused to store a valid HECA control (CONTAMINATED-KEY),
# costing the next lane a needless rebuild.  Both halves are asserted: a
# docs change must NOT move the hash, a code change MUST.

def _tool_module():
    """The ledger tool imported in-process, for hash-level assertions."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("rwl_tree_hash", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _commit(repo, message):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "-m", message],
                   cwd=repo, check=True, capture_output=True)


def test_docs_churn_does_NOT_move_the_code_tree_hash(ledger_repo):
    repo, _ledger = ledger_repo
    rwl = _tool_module()
    (repo / "docs").mkdir()
    (repo / "docs" / "RULINGS.md").write_text("ruling one\n")
    (repo / "STATUS.md").write_text("status\n")
    _commit(repo, "seed docs")
    before = rwl.code_tree_hash(str(repo))

    (repo / "docs" / "RULINGS.md").write_text("ruling one\nruling two\n")
    assert rwl.code_tree_hash(str(repo)) == before, (
        "an UNCOMMITTED docs edit moved the code tree hash")
    _commit(repo, "docs: one more ruling")
    assert rwl.code_tree_hash(str(repo)) == before, (
        "a DOCS-ONLY COMMIT moved the code tree hash — the 5b552ae1 "
        "precedent: every ledger key invalidates and valid arms are "
        "refused with CONTAMINATED-KEY while no code changed")

    (repo / "STATUS.md").write_text("status\nmore status\n")
    _commit(repo, "status churn")
    assert rwl.code_tree_hash(str(repo)) == before


def test_a_code_change_DOES_move_the_code_tree_hash(ledger_repo):
    """The other half: a hash that ignored docs by ignoring everything
    would be just as wrong, silently serving stale results."""
    repo, _ledger = ledger_repo
    rwl = _tool_module()
    before = rwl.code_tree_hash(str(repo))

    (repo / "src" / "module.py").write_text("VALUE = 2\n")
    uncommitted = rwl.code_tree_hash(str(repo))
    assert uncommitted != before, "an uncommitted src edit did not move it"
    _commit(repo, "src change")
    assert rwl.code_tree_hash(str(repo)) == uncommitted, (
        "committing an already-hashed edit moved the hash — the hash reads "
        "the working tree, and commit is not a code change")

    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.py").write_text("def test_x(): pass\n")
    assert rwl.code_tree_hash(str(repo)) != uncommitted, (
        "a new test file did not move it")

    (repo / "tools" / "t.py").write_text("print(1)\n")
    _commit(repo, "tools change")
    assert rwl.code_tree_hash(str(repo)) not in (before, uncommitted)


def test_a_docs_commit_does_NOT_invalidate_the_ledger(ledger_repo):
    """End to end, the way the bug was met: a docs commit lands mid-round
    and the already-passing run must still HIT."""
    repo, ledger = ledger_repo
    command = [sys.executable, "-c", "print('expensive')"]
    assert "MISS" in _run_tool(repo, [], command).stdout
    (repo / "docs").mkdir()
    (repo / "docs" / "RULINGS.md").write_text("a two-line ruling\nlanded\n")
    _commit(repo, "RULINGS: a ruling")
    second = _run_tool(repo, [], command)
    assert "HIT" in second.stdout, (
        "a docs-only commit re-ran an identical passing command")
    assert len(ledger.read_text().splitlines()) == 1


def test_artifact_body_hash_ignores_provenance(ledger_repo, tmp_path):
    repo, ledger = ledger_repo
    osm_a = tmp_path / "a.osm"
    osm_b = tmp_path / "b.osm"
    osm_a.write_text("<?xml?>\n<osm o4_provenance_built='T1'>\n<node/>\n")
    osm_b.write_text("<?xml?>\n<osm o4_provenance_built='T2'>\n<node/>\n")
    _run_tool(repo, ["--artifact", str(osm_a)],
              [sys.executable, "-c", "print('build a')"])
    record = json.loads(ledger.read_text().splitlines()[-1])
    art = record["artifacts"][0]
    assert art["sha256"] != art["body_sha256"]
    # Same body, different provenance line ⇒ same body hash.
    import hashlib
    body_b = b"\n".join(line for line in osm_b.read_bytes().split(b"\n")
                        if b"o4_provenance" not in line)
    assert art["body_sha256"] == hashlib.sha256(body_b).hexdigest()
