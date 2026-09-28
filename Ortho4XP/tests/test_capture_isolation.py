"""#64 twins: a capture never writes the shared corpus, and a deadline
kills the whole command (the ``perl alarm`` before ``/usr/bin/time``
killed only ``time``; its python kept running).

1. ``v2_solve_replay.capture`` REFUSES when the mod cache / DSF dump cache
   still resolve into the shared data repo — before any engine import;
2. the CLI wrapper ``_capture_guarded`` arms the redirect, so the same
   check passes inside it (run in a subprocess: the redirect rewrites the
   process environment);
3. ``harness/bounded_run.py`` kills a python CHILD of ``/usr/bin/time`` at
   the deadline — the exact arrangement the alarm got wrong — and exits
   124 with ``TIMED_OUT``.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "v2_solve_replay.py"
sys.path.insert(0, str(ROOT / "tools" / "harness"))
from shared_repo_guard import DATA_REPO as _DATA_REPO  # noqa: E402
BOUNDED = ROOT / "tools" / "harness" / "bounded_run.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_capture_without_the_overlays_refuses_before_the_engine(monkeypatch, tmp_path):
    replay = _load("_v2_solve_replay_iso", TOOL)
    sys.path.insert(0, str(ROOT / "tools" / "harness"))
    import O4_File_Names as FNAMES
    from shared_repo_guard import DATA_REPO
    monkeypatch.delenv("O4_AIRPORT_MOD_CACHE_DIR", raising=False)
    monkeypatch.delenv("O4_DSF_CACHE_DIR", raising=False)
    # BOTH scopes are posed here, not just the DSF cache.  Only on a
    # machine whose corpus IS the shared repo does airport_mod_cache_root
    # resolve inside it by default; on a corpus-free runner it already
    # resolved out, so the refusal named one scope and the twin read as a
    # guard defect (issue #76).  Posing both makes this hermetic — the
    # same question on the owner's Mac and on CI.
    monkeypatch.setattr(FNAMES, "Default_dsf_cache_dir",
                        str(Path(DATA_REPO) / "Default_DSF_cache"), raising=False)
    monkeypatch.setattr(FNAMES, "airport_mod_cache_root",
                        lambda: str(Path(DATA_REPO) / "Airport_mod_cache"),
                        raising=False)
    called = []
    # the refusal must come BEFORE the capture reaches the loader
    _load_mod = importlib.import_module("auto_patch_v2.airport.load")
    monkeypatch.setattr(_load_mod, "load_with_report",
                        lambda *a, **k: called.append(a) or pytest.fail("reached the loader"))
    with pytest.raises(SystemExit) as exc:
        replay.capture("ZZZZ", tmp_path / "ZZZZ.pkl")
    msg = str(exc.value)
    assert "REFUSING capture" in msg
    assert "airport_mod_cache" in msg and "dsf_cache" in msg
    assert not called
    assert not (tmp_path / "ZZZZ.pkl").exists()


@pytest.mark.skipif(
    not Path(_DATA_REPO).is_dir(),
    reason="the shared data repo is not this machine's corpus, so the "
           "engine's DEFAULT cache roots already resolve outside it and "
           "there is no un-redirected state for the bare call to refuse")
def test_the_cli_wrapper_arms_the_overlays_the_capture_requires(tmp_path):
    """BARE refuses, WRAPPED does not — the MACHINE's own default roots.

    Unlike the twin above this one cannot pose its question hermetically:
    its subject is precisely what the engine resolves with nothing
    patched, in a subprocess, and an ORTHO4XP_DATA_ROOT forced at the
    shared repo would outrank the very O4_*_DIR redirect the wrapper arms
    (O4_File_Names.airport_mod_cache_root: "an explicitly chosen data
    root is the more specific instruction") — so the WRAPPED half would
    refuse too and the twin would assert nothing.  It therefore runs only
    where the shared repo IS the corpus (issue #76).
    """
    env = {k: v for k, v in os.environ.items()
           if k not in ("O4_AIRPORT_MOD_CACHE_DIR", "O4_DSF_CACHE_DIR")}
    code = f"""
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("r", {str(TOOL)!r})
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
try:
    r.require_capture_isolation()
    print("BARE: not refused")
except SystemExit:
    print("BARE: refused")
def stub(*a, **k):
    r.require_capture_isolation()
    print("WRAPPED: isolated")
r.capture = stub
r._capture_guarded("ZZZZ", Path({str(tmp_path)!r}) / "ZZZZ.pkl")
"""
    out = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    assert "BARE: refused" in out.stdout, out.stdout
    assert "WRAPPED: isolated" in out.stdout, out.stdout
    assert "[guard] shared repo UNCHANGED" in out.stdout, out.stdout


@pytest.mark.skipif(not os.path.exists("/usr/bin/time"), reason="no /usr/bin/time")
def test_the_deadline_kills_the_python_child_of_time(tmp_path):
    pidfile = tmp_path / "child.pid"
    child = ("import os, time; open(%r, 'w').write(str(os.getpid())); "
             "time.sleep(60)" % str(pidfile))
    t0 = time.monotonic()
    out = subprocess.run([sys.executable, str(BOUNDED), "--deadline", "2",
                          "--grace", "2", "--label", "twin", "--",
                          "/usr/bin/time", sys.executable, "-c", child],
                         capture_output=True, text=True, timeout=45)
    wall = time.monotonic() - t0
    assert out.returncode == 124, (out.returncode, out.stderr)
    assert "TIMED_OUT after 2 s" in out.stderr
    assert wall < 30, wall
    pid = int(pidfile.read_text())
    for _ in range(40):                       # reaped by init: poll briefly
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        os.kill(pid, 9)
        pytest.fail(f"python child {pid} of /usr/bin/time survived the deadline")


def test_a_command_inside_its_deadline_keeps_its_own_status():
    out = subprocess.run([sys.executable, str(BOUNDED), "--deadline", "30", "--",
                          sys.executable, "-c", "import sys; sys.exit(3)"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 3
    assert "TIMED_OUT" not in out.stderr
