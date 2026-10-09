"""Guard twin: every child the engine launches takes CPython's posix_spawn().

On macOS, once GDAL has warped anything, its bundled PROJ has registered a
``pthread_atfork`` handler that closes the ``proj.db`` sqlite handles in the
forked child and segfaults before ``exec`` runs (2026-07-16 crash class; the
canonical text is ``O4_UI_Utils.external_tool_keyword_arguments``).  A launch
CPython routes through ``fork()`` + ``exec()`` from such a parent "fails
instantly" with no output.  CPython takes ``posix_spawn`` only when the launch
keywords satisfy the gate mirrored in ``_takes_posix_spawn`` below.

Two halves:

* the AST guard reads every ``subprocess`` launch in ``src`` and requires the
  helper's keywords (or a literal ``close_fds=False``) and no ``cwd=`` — a new
  launch site that forks is a named failure, an exemption is a recorded line;
* the recorder twins read the keywords the ``git`` provenance launches really
  pass, since the two gates the helper cannot carry (``cwd`` and a bare
  command name) were both wrong there.

Neither half tries to reproduce the segfault.
"""
import ast
import os
import subprocess
import sys

import O4_UI_Utils as UI

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
HELPER = "external_tool_keyword_arguments"
_LAUNCHES = ("run", "Popen", "call", "check_call", "check_output")

#: ``path:function`` -> why this launch does not name the helper itself.
#: A stale line fails the guard the same way a missing one does.
_EXEMPT_LAUNCHES = {
    "O4_OSM_Extract_Filter.py:_run_osmium_extract":
        "spawn_kwargs is the caller's; O4_OSM_Extracts (its one src caller) passes the helper",
    "Unused/O4_Forest.py:build_forest":
        "dead code under src/Unused — imported by nothing",
    "Unused/Earth_Orbit_Textures.py:<module>":
        "dead code under src/Unused — imported by nothing",
}


def _takes_posix_spawn(argv, kwargs):
    """CPython ``Popen._execute_child``'s posix_spawn gate, the part the
    keywords decide (pipes from capture_output are never low descriptors)."""
    return bool(
        os.path.dirname(argv[0])
        and kwargs.get("preexec_fn") is None
        and kwargs.get("close_fds", True) is False
        and not kwargs.get("pass_fds")
        and kwargs.get("cwd") is None
        and not kwargs.get("start_new_session")
        and kwargs.get("process_group", -1) == -1
        and kwargs.get("user") is None
        and kwargs.get("group") is None
        and kwargs.get("extra_groups") is None
        and kwargs.get("umask", -1) < 0
    )


def _is_helper_call(node) -> bool:
    return (isinstance(node, ast.Call)
            and getattr(node.func, "attr", getattr(node.func, "id", None))
            == HELPER)


def _is_launch(node) -> bool:
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _LAUNCHES
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess")


def forking_launches(relative: str, tree: ast.AST):
    """``path:function`` for each ``subprocess`` launch in ``tree`` that
    passes ``cwd=`` or carries neither the helper's keywords (``**helper()``,
    or ``**name`` where the function binds ``name`` from the helper) nor a
    literal ``close_fds=False``."""
    functions = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    owner = {}
    for function in functions:              # innermost function wins
        for node in ast.walk(function):
            if node is not function:
                owner[id(node)] = function
    for node in ast.walk(tree):
        if not _is_launch(node):
            continue
        function = owner.get(id(node))
        bound = set()
        for inner in ast.walk(function) if function is not None else ():
            if isinstance(inner, ast.Assign) and _is_helper_call(inner.value):
                bound.update(t.id for t in inner.targets
                             if isinstance(t, ast.Name))
        keywords = {k.arg: k.value for k in node.keywords if k.arg}
        spread = [k.value for k in node.keywords if k.arg is None]
        closed = keywords.get("close_fds")
        safe = (isinstance(closed, ast.Constant) and closed.value is False) \
            or any(_is_helper_call(value)
                   or (isinstance(value, ast.Name) and value.id in bound)
                   for value in spread)
        if "cwd" in keywords or not safe:
            yield "%s:%s" % (relative,
                             function.name if function else "<module>")


def test_every_engine_launch_takes_posix_spawn():
    offenders = set()
    for directory, _subdirectories, names in os.walk(SRC):
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            relative = os.path.relpath(path, SRC).replace(os.sep, "/")
            offenders.update(forking_launches(relative, tree))
    assert offenders == set(_EXEMPT_LAUNCHES), (
        "a subprocess launch that forks (pass **UI.%s() and no cwd=), "
        "or a stale exemption: %s"
        % (HELPER, sorted(offenders ^ set(_EXEMPT_LAUNCHES))))


def test_the_guard_sees_a_forking_launch_and_passes_a_spawning_one():
    def found(body):
        return list(forking_launches("m.py", ast.parse(body)))

    head = "def f(cmd):\n"
    assert found(head + "    subprocess.run(cmd, capture_output=True)\n") \
        == ["m.py:f"]
    assert found(head + "    subprocess.Popen(cmd, cwd='/x',"
                 " **UI.external_tool_keyword_arguments())\n") == ["m.py:f"]
    assert found("subprocess.call(cmd)\n") == ["m.py:<module>"]
    assert not found(head + "    subprocess.run(cmd, close_fds=False)\n")
    assert not found(head + "    subprocess.run(cmd, **PIPE.text(),"
                     " **UI.external_tool_keyword_arguments())\n")
    assert not found(head + "    kw = UI.external_tool_keyword_arguments()\n"
                     "    subprocess.run(cmd, **kw)\n")
    # a spread that is not the helper is not evidence
    assert found(head + "    subprocess.run(cmd, **other)\n") == ["m.py:f"]


def test_helper_kwargs_satisfy_the_gate():
    kwargs = UI.external_tool_keyword_arguments()
    assert kwargs["close_fds"] is False
    assert "cwd" not in kwargs
    assert isinstance(kwargs["env"], dict)
    assert _takes_posix_spawn([sys.executable, "-c", "pass"], kwargs)
    # The gates the helper cannot carry: a bare command name, and cwd=.
    assert not _takes_posix_spawn(["git", "status"], kwargs)
    assert not _takes_posix_spawn([sys.executable], dict(kwargs, cwd="/x"))


def test_git_provenance_takes_posix_spawn(monkeypatch):
    """``git_provenance`` passed ``cwd=`` and a bare ``git`` — both force
    fork.  It asks an ABSOLUTE git with ``-C <dir>`` instead, and the answer
    is read the same way."""
    from auto_patch import provenance

    calls = []

    def fake_run(argv, **kwargs):
        calls.append((list(argv), dict(kwargs)))
        return subprocess.CompletedProcess(argv, 0, stdout="abcdef12\n",
                                           stderr="")

    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(provenance.shutil, "which",
                        lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(subprocess, "run", fake_run)
    got = provenance.git_provenance(cwd="/some/checkout")
    assert got == {"sha": "abcdef12", "dirty": True}
    assert [argv[3:] for argv, _ in calls] == [
        ["rev-parse", "--short=8", "HEAD"], ["status", "--porcelain"]]
    for argv, kwargs in calls:
        assert argv[:3] == ["/usr/bin/git", "-C", "/some/checkout"]
        assert _takes_posix_spawn(argv, kwargs), (argv, kwargs)


def test_git_provenance_without_git_is_absent(monkeypatch):
    from auto_patch import provenance

    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(provenance.shutil, "which", lambda name: None)
    assert provenance.git_provenance() == {"sha": None, "dirty": None}
