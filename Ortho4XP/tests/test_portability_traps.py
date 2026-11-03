"""Platform traps are caught here, on the author's Mac, before CI (owner 2026-11-03).

The engine ships on macOS, Windows and Linux, but lanes run on a Mac.  A
call that exists only on POSIX, or a shell flag that means something else
on GNU, is green where the author runs it and red only on a CI runner (or a
user's machine).  Precedent: harness-only PR #1801 landed without its Linux
run and broke main because ``stat -f`` is filesystem status on Linux.

This twin scans ``src``, ``tools`` and ``tests`` (Python, by AST) and every
tracked ``.sh`` under the engine and the repo's ``scripts/`` (by line) for
the known traps in :data:`PY_TRAPS` / :data:`SH_TRAPS`.  A hit passes when
it is GUARDED:

* Python: an enclosing ``if``/ternary/``while`` test, an earlier
  early-exit ``if`` in an enclosing block, an enclosing ``def``/``class``
  decorator, or a module ``pytestmark`` names a platform witness
  (:data:`_WITNESS`: ``sys.platform``, ``os.name``, ``hasattr(...)``,
  ``os.supports_follow_symlinks`` ...); or an enclosing ``try`` catches
  ``AttributeError`` / ``ImportError`` / ``NotImplementedError``, or the
  hit sits in an ``except ImportError`` branch; a guarded POSIX module's
  name (``if _pwd is not None``) is a witness too.
  ``getattr(signal, "SIGKILL", default)`` is not a trap at all.
* Shell: the line carries the other platform's spelling first
  (``stat -c ... || stat -f ...``, ``date -d`` beside ``date -j``) or a
  ``||`` fallback where the rule allows one.

Anything else that is lawful goes in :data:`ALLOWED` with a reason; a stale
entry fails the same way a missing one does.  Pure hermetic: reads the
repo's own files.
"""
from __future__ import annotations

import ast
import functools
import re
import subprocess
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1]
REPO = ENGINE.parent
PY_ROOTS = ("src", "tools", "tests")

#: trap id -> what it costs, for the failure message.
PY_TRAPS = {
    "st_blocks": "os.stat().st_blocks does not exist on Windows",
    "utime_nofollow": "os.utime(follow_symlinks=False) raises NotImplementedError on Windows",
    "posix_os_call": "os.fork/forkpty/killpg/setsid/getpgid/getuid do not exist on Windows",
    "posix_signal": "signal.SIGKILL/SIGHUP/... do not exist on Windows",
    "posix_module": "fcntl/resource/termios/pwd/grp do not import on Windows",
    "windows_module": "msvcrt/winreg/_winapi do not import on macOS or Linux",
    "tar_drive": "GNU tar reads `C:\\...` as host:path; pass --force-local or guard",
    "file_url_concat": "'file://' + a Windows path is not a URL; use Path.as_uri()",
}
SH_TRAPS = {
    "stat_f": "`stat -f` is filesystem status on GNU; try `stat -c` first",
    "date_j": "`date -j` is BSD-only; pair it with `date -d`",
    "sed_i_empty": "`sed -i ''` fails on GNU sed; use `sed -i.bak` and remove the .bak",
    "readlink_f": "`readlink -f` is absent on older BSD; give a `||` fallback",
}

_POSIX_OS = {"fork", "forkpty", "killpg", "setsid", "getpgid", "getuid", "getgid"}
_POSIX_SIGNALS = {"SIGKILL", "SIGHUP", "SIGALRM", "SIGUSR1", "SIGUSR2", "SIGQUIT",
                  "SIGCHLD", "SIGPIPE", "SIGSTOP", "SIGCONT", "SIGTSTP"}
_POSIX_MODULES = {"fcntl", "resource", "termios", "pwd", "grp"}
_WINDOWS_MODULES = {"msvcrt", "winreg", "_winapi"}
_GUARD_EXC = {"AttributeError", "ImportError", "ModuleNotFoundError",
              "NotImplementedError"}
_WITNESS = re.compile(
    r"sys\.platform|os\.name|platform\.system|supports_follow_symlinks|hasattr\(|"
    r"\bIS_WIN|_WINDOWS\b|_POSIX\b|\bIS_MAC|\bwin32\b|\bdarwin\b|\bposix\b|\bnt\b|"
    r"\b_?(fcntl|resource|termios|pwd|grp|msvcrt|winreg)\b")    # a guarded import's name

#: ``relpath`` -> {trap id: reason}.  Reviewed, file-scoped exemptions.
ALLOWED = {
    "tools/harness/bounded_run.py": {
        "posix_os_call": "POSIX-only lane wrapper (process groups); never run on Windows",
        "posix_signal": "POSIX-only lane wrapper (process groups); never run on Windows",
    },
    "tests/test_approach_rings.py": {
        "file_url_concat": "the %s is a dataset code (URL host), not a filesystem path",
    },
    "tools/harness/lane_worktree.sh": {
        "readlink_f": "lane ritual runs on macOS 26 / Linux, both have readlink -f; "
                      "failure is tolerated (2>/dev/null, empty result)",
    },
    "../scripts/make_appimage.sh": {
        "readlink_f": "AppImage launcher: Linux only",
    },
}


# -- Python ----------------------------------------------------------------

def _is_false(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _str_const(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _import_trap(node) -> str | None:
    if isinstance(node, ast.Import):
        names = [a.name for a in node.names]
    else:
        names = [node.module or ""] if not node.level else []
    tops = {n.split(".")[0] for n in names}
    if tops & _POSIX_MODULES:
        return "posix_module"
    if tops & _WINDOWS_MODULES:
        return "windows_module"
    return None


def _call_trap(node: ast.Call) -> str | None:
    f = node.func
    if (isinstance(f, ast.Attribute) and f.attr == "utime"
            and any(k.arg == "follow_symlinks" and _is_false(k.value)
                    for k in node.keywords)):
        return "utime_nofollow"
    if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
        argv = [_str_const(e) for e in node.args[0].elts]
        if (argv and argv[0] and re.search(r"(^|[/\\])tar(\.exe)?$", argv[0])
                and "-C" in argv and "--force-local" not in argv):
            return "tar_drive"
    if (isinstance(f, ast.Attribute) and f.attr == "format"
            and (_str_const(f.value) or "").startswith("file://")):
        return "file_url_concat"
    return None


def _trap(node) -> str | None:
    """The trap id ``node`` is, or ``None``."""
    if isinstance(node, ast.Attribute):
        base = node.value.id if isinstance(node.value, ast.Name) else None
        if node.attr == "st_blocks":
            return "st_blocks"
        if base == "os" and node.attr in _POSIX_OS:
            return "posix_os_call"
        if base == "signal" and node.attr in _POSIX_SIGNALS:
            return "posix_signal"
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        return _import_trap(node)
    elif isinstance(node, ast.Call):
        return _call_trap(node)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        left = _str_const(node.left) or ""
        if left.startswith("file://") and (isinstance(node.op, ast.Add) or "%" in left):
            return "file_url_concat"
    elif isinstance(node, ast.JoinedStr):
        vals = node.values
        if (len(vals) > 1 and (_str_const(vals[0]) or "").startswith("file://")
                and any(isinstance(v, ast.FormattedValue) for v in vals)):
            return "file_url_concat"
    return None


def _exits(stmt) -> bool:
    """An ``if`` body that leaves the block: return/raise/continue/skip."""
    last = stmt.body[-1] if stmt.body else None
    if isinstance(last, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
        return True
    return (isinstance(last, ast.Expr) and isinstance(last.value, ast.Call)
            and "skip" in ast.unparse(last.value.func))


def _earlier_guard(cur, child, witnessed) -> bool:
    """An earlier statement in ``cur``'s block holding ``child`` guards it."""
    for field in ("body", "orelse", "finalbody"):
        block = getattr(cur, field, None)
        if not (isinstance(block, list) and child in block):
            continue
        for stmt in block[:block.index(child)]:
            if isinstance(stmt, ast.If) and witnessed(stmt.test) and _exits(stmt):
                return True
            if (isinstance(stmt, ast.Assign) and isinstance(cur, ast.Module)
                    and any(getattr(t, "id", "") == "pytestmark" for t in stmt.targets)
                    and witnessed(stmt.value)):
                return True
    return False


def _guarded(node, parents, src) -> bool:
    def witnessed(n) -> bool:
        return bool(_WITNESS.search(ast.get_source_segment(src, n) or ast.unparse(n)))

    child, cur = node, parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.If, ast.IfExp, ast.While)) and witnessed(cur.test):
            return True
        if isinstance(cur, ast.ExceptHandler) and cur.type is not None and (
                {n.id for n in ast.walk(cur.type) if isinstance(n, ast.Name)}
                & {"ImportError", "ModuleNotFoundError"}):
            return True                     # the other platform's import branch
        if isinstance(cur, ast.Try) and child in cur.body:
            for h in cur.handlers:
                names = {n.id for n in ast.walk(h.type)
                         if isinstance(n, ast.Name)} if h.type else _GUARD_EXC
                if names & _GUARD_EXC:
                    return True
        if (isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and any(witnessed(d) for d in cur.decorator_list)):
            return True
        if _earlier_guard(cur, child, witnessed):
            return True
        child, cur = cur, parents.get(cur)
    return False


def py_hits(src: str, name: str = "<snippet>") -> list[tuple[int, str]]:
    """``[(line, trap id)]`` of the unguarded Python traps in ``src``."""
    tree = ast.parse(src, name)
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    out = set()
    for node in ast.walk(tree):
        trap = _trap(node)
        if trap and not _guarded(node, parents, src):
            out.add((node.lineno, trap))
    return sorted(out)


# -- shell -----------------------------------------------------------------

def _sh_line_hits(line: str) -> list[str]:
    if line.lstrip().startswith("#"):
        return []
    code = line.split(" #", 1)[0]
    hits = []
    m = re.search(r"\bstat\s+-f\b", code)
    if m and not re.search(r"\bstat\s+-c\b", code[:m.start()]):
        hits.append("stat_f")
    if re.search(r"\bdate\s+-j\b", code) and not re.search(r"\bdate\s+-d\b", code):
        hits.append("date_j")
    if re.search(r"\bsed\s+(-\w+\s+)*-i\s*(''|\"\")", code):
        hits.append("sed_i_empty")
    m = re.search(r"\breadlink\s+-f\b", code)
    if m and "||" not in code[m.end():]:
        hits.append("readlink_f")
    return hits


def sh_hits(text: str) -> list[tuple[int, str]]:
    """``[(line, trap id)]`` of the shell traps in ``text``."""
    return [(i, t) for i, line in enumerate(text.splitlines(), 1)
            for t in _sh_line_hits(line)]


# -- the tree --------------------------------------------------------------

def _tracked(*pathspecs: str) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z", "--", *pathspecs], cwd=REPO,
                         capture_output=True, check=True).stdout.decode("utf-8")
    return [REPO / p for p in out.split("\0") if p and (REPO / p).is_file()]


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ENGINE).as_posix()
    except ValueError:
        return "../" + path.relative_to(REPO).as_posix()


@functools.lru_cache(maxsize=1)
def _tree_hits() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in _tracked(*(f"Ortho4XP/{r}/*.py" for r in PY_ROOTS)):
        if "/Unused/" in path.as_posix():
            continue
        for line, trap in py_hits(path.read_text(encoding="utf-8"), str(path)):
            found.setdefault(_rel(path), []).append(f"{line}:{trap}")
    for path in _tracked("Ortho4XP/*.sh", "scripts/*.sh"):
        for line, trap in sh_hits(path.read_text(encoding="utf-8")):
            found.setdefault(_rel(path), []).append(f"{line}:{trap}")
    return found


needs_git = pytest.mark.skipif(not (REPO / ".git").exists(),
                               reason="no git checkout to list tracked files")


@needs_git
def test_no_unguarded_platform_trap_in_the_tree():
    bad = []
    for rel, hits in sorted(_tree_hits().items()):
        allowed = ALLOWED.get(rel, {})
        for hit in hits:
            trap = hit.split(":", 1)[1]
            if trap not in allowed:
                why = PY_TRAPS.get(trap) or SH_TRAPS[trap]
                bad.append(f"{rel}:{hit} — {why}")
    assert not bad, ("platform traps with no guard (add a sys.platform/hasattr "
                     "guard, or an ALLOWED entry with a reason):\n  " + "\n  ".join(bad))


@needs_git
def test_every_allowed_entry_still_matches_a_hit():
    found = _tree_hits()
    stale = [f"{rel}:{trap}" for rel, traps in ALLOWED.items() for trap in traps
             if not any(h.endswith(":" + trap) for h in found.get(rel, []))]
    assert not stale, f"ALLOWED entries no longer needed — drop them: {stale}"
    assert all(reason.strip() for traps in ALLOWED.values()
               for reason in traps.values())


# -- the fixtures ----------------------------------------------------------

@pytest.mark.parametrize("snippet, trap", [
    ("import os\nos.stat('x').st_blocks\n", "st_blocks"),
    ("import os\nos.utime('l', (1, 1), follow_symlinks=False)\n", "utime_nofollow"),
    ("import os\npid = os.fork()\n", "posix_os_call"),
    ("import os\nos.killpg(1, 9)\n", "posix_os_call"),
    ("import signal\nsig = signal.SIGKILL\n", "posix_signal"),
    ("import fcntl\n", "posix_module"),
    ("from resource import getrusage\n", "posix_module"),
    ("import msvcrt\n", "windows_module"),
    ("import subprocess\nsubprocess.run(['tar', '-xf', a, '-C', d])\n", "tar_drive"),
    ("u = 'file://' + path\n", "file_url_concat"),
    ("u = f'file://{path}'\n", "file_url_concat"),
    ("u = 'file://%s' % path\n", "file_url_concat"),
    ("u = 'file://{}'.format(path)\n", "file_url_concat"),
])
def test_an_unguarded_trap_is_found(snippet, trap):
    assert [t for _l, t in py_hits(snippet)] == [trap]


def test_two_signals_on_one_line_are_one_hit():
    assert py_hits("import signal\nsignal.signal(signal.SIGHUP, signal.SIGKILL)\n") \
        == [(2, "posix_signal")]


@pytest.mark.parametrize("snippet", [
    "import os\nb = getattr(os.stat('x'), 'st_blocks', None)\n",
    "import os, sys\nif sys.platform != 'win32':\n    os.stat('x').st_blocks\n",
    "import os\nif os.utime in os.supports_follow_symlinks:\n"
    "    os.utime('l', (1, 1), follow_symlinks=False)\n",
    "import os\nb = os.stat('x').st_blocks if os.name == 'posix' else 0\n",
    "import os\ndef f():\n    if os.name == 'nt':\n        return 0\n    return os.fork()\n",
    "import os\ntry:\n    pid = os.fork()\nexcept AttributeError:\n    pid = None\n",
    "try:\n    import fcntl\nexcept ImportError:\n    fcntl = None\n",
    "try:\n    import fcntl\nexcept ImportError:\n    import msvcrt\n",
    "import os\ntry:\n    import pwd as _pwd\nexcept ImportError:\n    _pwd = None\n"
    "if _pwd is not None:\n    uid = os.getuid()\n",
    "import signal\nsig = getattr(signal, 'SIGKILL', signal.SIGTERM)\n",
    "import signal\nif hasattr(signal, 'SIGHUP'):\n    signal.signal(signal.SIGHUP, print)\n",
    "import os, pytest\n@pytest.mark.skipif(os.name != 'posix', reason='x')\n"
    "def test_x():\n    os.kill(1, __import__('signal').SIGKILL)\n",
    "import sys, pytest\nif sys.platform == 'win32':\n"
    "    pytest.skip('posix', allow_module_level=True)\nimport fcntl\n",
    "import sys, pytest\npytestmark = pytest.mark.skipif(sys.platform == 'win32',"
    " reason='x')\nimport resource\n",
    "subprocess.run(['tar', '--force-local', '-xf', a, '-C', d])\n",
    "u = Path(p).as_uri()\nq = 'file:///o4.qml'\n",
])
def test_a_guarded_or_lawful_call_passes(snippet):
    assert py_hits(snippet) == []


@pytest.mark.parametrize("line, trap", [
    ('m=$(stat -f %m "$f")', "stat_f"),
    ('m=$(stat -f %m "$f" || stat -c %Y "$f")', "stat_f"),     # BSD first: wrong
    ('d=$(date -j -f %s "$t" +%F)', "date_j"),
    ("sed -i '' 's/a/b/' f", "sed_i_empty"),
    ('sed -E -i "" "s/a/b/" f', "sed_i_empty"),
    ('r=$(readlink -f "$0")', "readlink_f"),
])
def test_a_shell_trap_is_found(line, trap):
    assert [t for _l, t in sh_hits(line)] == [trap]


@pytest.mark.parametrize("line", [
    'm=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo 0)',
    'd=$(date -d "@$t" +%F 2>/dev/null || date -j -f %s "$t" +%F)',
    "sed -i.bak 's/a/b/' f && rm f.bak",
    'r=$(readlink -f "$0" 2>/dev/null || realpath "$0")',
    "# on Linux `stat -f` is filesystem status",
])
def test_a_portable_shell_line_passes(line):
    assert sh_hits(line) == []
