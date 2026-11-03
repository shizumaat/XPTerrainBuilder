"""TWINS for the lane-worktree janitor (owner 2026-11-03).

* ``down`` ignores the open handles of a macOS Virtualization VM — its
  shared-folder view of the home directory held read-only handles in 71 of
  73 trees and made every teardown refuse — and still refuses any other
  holder (fake ``lsof`` on PATH, matched by COMMAND, never a pid).
* ``prune-merged`` removes, through ``down``, exactly the trees whose work
  is on main (ancestry, or a merged PR's head), keeps open, dirty and fresh
  lanes and the tree it runs from, and is a dry run without ``--apply``.
* ``up`` creating a new tree first RECYCLES a finished lane tree (moved,
  detached at the new ref, products cleared, mounts kept), else prunes and
  then holds ``LANE_CAP`` (16).
* ``prune-merged`` lists stray non-worktree directories under
  ``.claude/worktrees`` and removes, with ``--apply``, only the empty /
  ``.DS_Store``-only ones.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

if sys.platform == "win32":                                # pragma: no cover
    pytest.skip("tools/harness is a POSIX-only lane instrument",
                allow_module_level=True)

from test_harness import RITUAL, _ritual, _tiny_repo  # noqa: E402

VM = "com.apple.Virtualization.Virtua"     # lsof's 31-char COMMAND


def _fake_bin(tmp_path, env, lsof_out="", gh_out=""):
    """Fake ``lsof`` and ``gh`` first on PATH; both just print a file."""
    fb = tmp_path / "fakebin"
    fb.mkdir(exist_ok=True)
    for name, out in (("lsof", lsof_out), ("gh", gh_out)):
        (tmp_path / f"{name}.out").write_text(out, encoding="utf-8", newline="")
        tool = fb / name
        tool.write_text(f"#!/bin/sh\ncat '{tmp_path / (name + '.out')}'\n",
                        encoding="utf-8", newline="")
        tool.chmod(0o755)
    env["PATH"] = f"{fb}{os.pathsep}{env['PATH']}"
    return env


def _git(env, cwd, *args):
    r = subprocess.run(("git", "-C", str(cwd)) + args, env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _lane(env, main, name, commit=True):
    up = _ritual(env, "up", name, "HEAD")
    assert up.returncode == 0, up.stdout + up.stderr
    wt = main / ".claude" / "worktrees" / name
    _git(env, wt, "switch", "-q", "-c", f"claude/{name}")
    if commit:
        (wt / f"{name}.txt").write_text(name + "\n", encoding="utf-8", newline="")
        _git(env, wt, "add", f"{name}.txt")
        _git(env, wt, "commit", "-qm", name)
    return wt


def test_down_ignores_a_virtualization_vm_but_refuses_other_holders(tmp_path):
    main, _data, env, _old = _tiny_repo(tmp_path)
    vm = f"p1246\nc{VM}\nn{main}/.claude/worktrees/x/tools\n"
    env = _fake_bin(tmp_path, env, lsof_out=vm)
    for name in ("vm1", "py1"):
        assert _ritual(env, "up", name, "HEAD").returncode == 0
    down = _ritual(env, "down", "vm1")
    assert down.returncode == 0, down.stdout + down.stderr
    assert not (main / ".claude" / "worktrees" / "vm1").exists()

    (tmp_path / "lsof.out").write_text(
        vm + "p4242\ncpython3.12\nn/x/Ortho4XP/Patches/a.osm\n",
        encoding="utf-8", newline="")
    held = _ritual(env, "down", "py1")
    assert held.returncode == 2
    assert "open file handles" in held.stderr
    assert "python3.12 pid 4242" in held.stdout and VM not in held.stdout


def test_prune_merged_removes_only_merged_lanes(tmp_path):
    main, _data, env, _old = _tiny_repo(tmp_path)
    env = _fake_bin(tmp_path, env)
    env["O4_PRUNE_BASE"] = _git(env, main, "branch", "--show-current")
    merged = _lane(env, main, "merged")
    squash = _lane(env, main, "squash")
    _lane(env, main, "open")
    dirty = _lane(env, main, "dirty")
    _lane(env, main, "fresh", commit=False)
    _git(env, main, "merge", "-q", "--no-ff", "-m", "m1", "claude/merged")
    _git(env, main, "merge", "-q", "--no-ff", "-m", "m2", "claude/dirty")
    (dirty / "dirty.txt").write_text("edited\n", encoding="utf-8", newline="")
    (tmp_path / "gh.out").write_text(
        f"claude/squash\t{_git(env, squash, 'rev-parse', 'HEAD')}\t77\n",
        encoding="utf-8", newline="")

    def prune(*args, cwd=tmp_path, **extra):
        r = subprocess.run([str(RITUAL), "prune-merged", *args],
                           env=dict(env, **extra), cwd=cwd,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        rows = {}
        for ln in r.stdout.splitlines():
            parts = ln.split()
            if len(parts) > 2 and parts[0] in ("kept", "remove", "removed"):
                rows[parts[1]] = ln
        return rows, r.stdout

    rows, out = prune()
    assert "DRY RUN" in out and merged.exists() and squash.exists()
    assert rows["merged"].split()[0] == "remove"
    assert "PR #77" in rows["squash"]
    assert rows["open"].split()[0] == "kept"
    assert "uncommitted" in rows["dirty"]
    assert "fresh lane" in rows["fresh"]

    rows, _ = prune(cwd=merged)
    assert "the tree this runs from" in rows["merged"]
    rows, _ = prune(O4_PRUNE_MIN_AGE_H="0")
    assert "no commits of its own, idle" in rows["fresh"]

    rows, out = prune("--apply")
    assert not merged.exists() and not squash.exists()
    assert {n for n, ln in rows.items() if ln.split()[0] == "removed"} \
        == {"merged", "squash"}
    assert dirty.exists() and "free space" in out


def test_up_holds_the_lane_cap(tmp_path):
    assert "\nLANE_CAP=16\n" in RITUAL.read_text(encoding="utf-8", newline="")
    main, _data, env, _old = _tiny_repo(tmp_path)
    env = _fake_bin(tmp_path, env)
    env["O4_PRUNE_BASE"] = _git(env, main, "branch", "--show-current")
    env["O4_LANE_CAP"] = "2"
    for name in ("a1", "a2"):
        _lane(env, main, name)
    over = _ritual(env, "up", "a3", "HEAD")
    assert over.returncode == 2
    assert "LANE CAP: 2 lane worktrees" in over.stderr
    assert "claude/a1" in over.stderr and "claude/a2" in over.stderr
    # Completing an EXISTING tree is not a new lane.
    assert _ritual(env, "up", "a1").returncode == 0
    # A merged lane is taken over by `up` itself, which frees the slot.
    _git(env, main, "merge", "-q", "--no-ff", "-m", "m", "claude/a1")
    again = _ritual(env, "up", "a3", "HEAD")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "RECYCLED a1" in again.stdout
    assert not (main / ".claude" / "worktrees" / "a1").exists()


def test_up_recycles_a_finished_lane_and_clears_its_products(tmp_path):
    main, data, env, _old = _tiny_repo(tmp_path)
    (data / "logs").mkdir()                       # a mounted data dir
    with open(main / ".gitignore", "a", encoding="utf-8", newline="") as fh:
        fh.write("Ortho4XP/Tiles/\nOrtho4XP/tmp/\nOrtho4XP/Previews/\n")
    _git(env, main, "commit", "-qam", "ignore products")
    env = _fake_bin(tmp_path, env)
    env["O4_PRUNE_BASE"] = _git(env, main, "branch", "--show-current")
    old = _lane(env, main, "old")
    eng = old / "Ortho4XP"
    for rel in ("Tiles/zOrtho4XP_+30+031/t.dsf", "tmp/x.pkl",
                "Previews/p.jpg", "Patches/+30+031/HECA_auto.patch.osm"):
        (eng / rel).parent.mkdir(parents=True, exist_ok=True)
        (eng / rel).write_text("stale\n", encoding="utf-8", newline="")
    (eng / "XPTerrainBuilder.cfg").write_text("lane=edit\n", encoding="utf-8", newline="")
    _lane(env, main, "busy")                      # open: never recycled
    _git(env, main, "merge", "-q", "--no-ff", "-m", "m", "claude/old")
    tip = _git(env, main, "rev-parse", "HEAD")

    up = _ritual(env, "up", "new", "HEAD")
    assert up.returncode == 0, up.stdout + up.stderr
    assert "RECYCLED old" in up.stdout and "untracked audit clean" in up.stdout
    new = main / ".claude" / "worktrees" / "new"
    assert not old.exists() and new.is_dir()
    assert _git(env, new, "rev-parse", "HEAD") == tip
    assert _git(env, new, "branch", "--show-current") == ""
    ne = new / "Ortho4XP"
    assert not (ne / "Tiles").exists() and not (ne / "tmp").exists()
    assert not (ne / "Previews").exists()
    assert not (ne / "Patches" / "+30+031").exists()
    assert (ne / "Patches" / "+39-078" / "2W2_runways.patch.osm").is_file()
    assert (ne / "XPTerrainBuilder.cfg").read_text(encoding="utf-8") \
        == (main / "Ortho4XP" / "XPTerrainBuilder.cfg").read_text(encoding="utf-8")
    assert (ne / "logs").is_symlink() and (ne / "venv").is_symlink()
    trees = _git(env, main, "worktree", "list", "--porcelain")
    assert str(new) in trees and str(old) not in trees

    # Nothing finished is left: the next NEW lane is a fresh tree.
    fresh = _ritual(env, "up", "new2", "HEAD")
    assert fresh.returncode == 0 and "RECYCLED" not in fresh.stdout
    assert (main / ".claude" / "worktrees" / "busy").is_dir()


def test_prune_merged_lists_strays_and_removes_only_empty_ones(tmp_path):
    main, _data, env, _old = _tiny_repo(tmp_path)
    env = _fake_bin(tmp_path, env)
    env["O4_PRUNE_BASE"] = _git(env, main, "branch", "--show-current")
    _lane(env, main, "real")
    root = main / ".claude" / "worktrees"
    (root / "empty").mkdir()
    (root / "dsonly" / "sub").mkdir(parents=True)
    (root / "dsonly" / ".DS_Store").write_bytes(b"x")
    (root / "dsonly" / "sub" / ".DS_Store").write_bytes(b"x")
    (root / "residue").mkdir()
    (root / "residue" / "README.md").write_text("x\n", encoding="utf-8", newline="")

    def prune(*args):
        r = subprocess.run([str(RITUAL), "prune-merged", *args], env=env,
                           cwd=tmp_path, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        return {ln.split()[1]: ln.split()[0] for ln in r.stdout.splitlines()
                if len(ln.split()) > 2 and ln.split()[0] != "[prune]"}

    rows = prune()
    assert rows["empty"] == rows["dsonly"] == "remove"
    assert rows["residue"] == "stray" and rows["real"] == "kept"
    assert (root / "empty").exists() and (root / "dsonly").exists()
    rows = prune("--apply")
    assert rows["empty"] == rows["dsonly"] == "removed"
    assert not (root / "empty").exists() and not (root / "dsonly").exists()
    assert (root / "residue" / "README.md").exists() and (root / "real").is_dir()
