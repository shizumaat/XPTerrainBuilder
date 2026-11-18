"""No ``MallocStackLogging*`` variable reaches an engine child (owner
2026-11-17: one stderr line per worker).  The Swift half is
``Tests/SceneryKitTests/ProcessEnvironmentTests.swift``."""
import os
import subprocess
import sys

import O4_Process_Environment as PE

ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_strip_removes_every_malloc_stack_logging_variable_and_nothing_else():
    env = {"MallocStackLogging": "0", "MallocStackLoggingNoCompact": "1",
           "MallocStackLoggingDirectory": "/tmp",
           "__XPC_MallocStackLogging": "1",
           "MallocNanoZone": "0", "PATH": "/usr/bin"}
    removed = PE.strip_malloc_stack_logging(env)
    assert removed == ["MallocStackLogging", "MallocStackLoggingDirectory",
                       "MallocStackLoggingNoCompact",
                       "__XPC_MallocStackLogging"]
    assert env == {"MallocNanoZone": "0", "PATH": "/usr/bin"}


def test_strip_of_a_clean_environment_removes_nothing():
    env = {"PATH": "/usr/bin"}
    assert PE.strip_malloc_stack_logging(env) == []
    assert env == {"PATH": "/usr/bin"}


def test_default_is_os_environ(monkeypatch):
    monkeypatch.setenv("MallocStackLogging", "0")
    removed = PE.strip_malloc_stack_logging()
    assert [n.upper() for n in removed] == ["MALLOCSTACKLOGGING"]  # Windows upper-cases keys
    assert "MallocStackLogging" not in os.environ


def _module_level_lines(name, needle):
    with open(os.path.join(ENGINE_ROOT, name), encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    return [i for i, ln in enumerate(lines) if ln.startswith(needle)]


def test_both_entries_strip_before_the_spawn_bootstrap():
    """Both frozen entries (engine and Qt window) strip at module level,
    before ``multiprocessing.freeze_support()`` and every later spawn."""
    for name in ("Ortho4XP.py", "Ortho4XP_Qt.py"):
        strip = _module_level_lines(
            name, "O4_Process_Environment.strip_malloc_stack_logging()")
        assert len(strip) == 1, name
        with open(os.path.join(ENGINE_ROOT, name), encoding="utf-8") as h:
            text = h.read().splitlines()
        support = [i for i, ln in enumerate(text)
                   if "multiprocessing.freeze_support()" in ln
                   and not ln.lstrip().startswith("#")]
        assert support and strip[0] < min(support), name


def test_a_child_of_the_stripped_process_sees_no_variable():
    """End to end: the variable set in the parent never reaches a child
    started after the strip."""
    code = ("import os, subprocess, sys; sys.path.insert(0, 'src');"
            "import O4_Process_Environment as P; P.strip_malloc_stack_logging();"
            "print(subprocess.run([sys.executable, '-c',"
            "'import os; print(sorted(k for k in os.environ if \"MallocStack\" in k))'],"
            "capture_output=True, text=True).stdout.strip())")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(PE.MALLOC_DEBUG_PREFIXES)}
    env["MallocStackLoggingDirectory"] = "/nonexistent"
    out = subprocess.run([sys.executable, "-c", code], cwd=ENGINE_ROOT, env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.stdout.strip().splitlines()[-1] == "[]", out
