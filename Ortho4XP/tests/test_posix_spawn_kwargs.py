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


#: ``path:function`` -> why argv[0] always has a directory, so the launch need
#: not hand its command to the helper (#2259: CPython forks for a bare name).
_PATH_ARGV = {
    "O4_DSFTool.py:head": "the bundled DSFTool path",
    "O4_DSFTool.py:run": "the bundled DSFTool path",
    "O4_MSFS_XPlane_Pack.py:write_overlay_dsf": "dsftool_path",
    "O4_Mesh_Utils.py:_run_triangulation_process":
        "the bundled Triangle4XP path",
    "O4_Triangle_Run.py:triangulate": "the bundled Triangle4XP path",
    "O4_World_Pack.py:_dsftool": "dsftool_path",
    "auto_patch/provenance.py:git_provenance": "shutil.which's absolute git",
    "auto_patch_v2/airport/dsf_mesh.py:stream_text": "the bundled DSFTool path",
    "elevation_access/capabilities.py:lerc_decode_available": "sys.executable",
    "elevation_access/strategies/arcgis_export_image.py:_decode_lerc_chunks":
        "sys.executable",
    "elevation_access/strategies/arcgis_lerc_tiles.py:fetch": "sys.executable",
    "elevation_access/strategies/static_stac.py:_decode_lerc_sources":
        "sys.executable",
    "o4_engine/parallel.py:spawn": "tile_worker_command: sys.executable",
}

#: Bare-name launches that still fork, each in a file another lane holds.
#: Fixing one makes its line stale, and the guard then asks to delete it.
_BARE_NAME_OPEN = {
    "auto_patch_v2/airport/pool_memory.py:_resident_kib":
        "bare ps; pass the argv to the helper (#2259)",
}

#: Launchers outside ``subprocess`` that fork or shell out.
_OTHER_LAUNCHERS = ("system", "popen", "fork", "forkpty", "spawnv", "spawnvp")
_EXEMPT_OTHER = {
    "O4_Geotag.py:<os.system>": "standalone script, imported by nothing",
}


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


def bare_name_launches(relative: str, tree: ast.AST):
    """``path:function`` for each launch whose argv[0] may be a bare name:
    it neither hands its command to the helper nor names an absolute path."""
    owner = {}
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(function):
                if node is not function:
                    owner[id(node)] = function
    for node in ast.walk(tree):
        if not _is_launch(node):
            continue
        spread = [k.value for k in node.keywords if k.arg is None]
        if any(_is_helper_call(value) and value.args for value in spread):
            continue
        first = node.args[0] if node.args else None
        head = first.elts[0] if isinstance(first, ast.List) and first.elts \
            else None
        if isinstance(head, ast.Constant) and isinstance(head.value, str) \
                and head.value.startswith("/"):
            continue
        function = owner.get(id(node))
        yield "%s:%s" % (relative, function.name if function else "<module>")


def other_launchers(relative: str, tree: ast.AST):
    """``os.system`` and kin, a ``subprocess`` launcher passed as a default
    argument, and a multiprocessing ``fork`` context."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name):
            module, name = node.func.value.id, node.func.attr
            if module == "os" and name in _OTHER_LAUNCHERS:
                yield "%s:<os.%s>" % (relative, name)
            if name in ("get_context", "set_start_method") and any(
                    isinstance(a, ast.Constant) and a.value == "fork"
                    for a in node.args):
                yield "%s:<fork context>" % relative
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if isinstance(default, ast.Attribute) \
                        and default.attr in _LAUNCHES \
                        and getattr(default.value, "id", "") == "subprocess":
                    yield "%s:%s" % (relative, node.name)


def _trees():
    for directory, _subdirectories, names in os.walk(SRC):
        for name in names:
            if name.endswith(".py"):
                path = os.path.join(directory, name)
                with open(path, encoding="utf-8") as handle:
                    yield (os.path.relpath(path, SRC).replace(os.sep, "/"),
                           ast.parse(handle.read()))


def test_no_launch_can_fork_on_a_bare_program_name():
    found = set()
    for relative, tree in _trees():
        if not relative.startswith("Unused/"):
            found.update(bare_name_launches(relative, tree))
    recorded = set(_PATH_ARGV) | set(_BARE_NAME_OPEN) | (
        set(_EXEMPT_LAUNCHES) - {k for k in _EXEMPT_LAUNCHES
                                 if k.startswith("Unused/")})
    assert found == recorded, (
        "pass the argv: **UI.%s(command), or record why argv[0] is a path; "
        "new or stale: %s" % (HELPER, sorted(found ^ recorded)))


def test_no_launch_outside_subprocess_forks():
    found = set()
    for relative, tree in _trees():
        if not relative.startswith("Unused/"):
            found.update(other_launchers(relative, tree))
    assert found == set(_EXEMPT_OTHER), sorted(found ^ set(_EXEMPT_OTHER))


def test_the_bare_name_guard_reads_the_command():
    def found(body):
        return list(bare_name_launches("m.py", ast.parse(body)))

    head = "def f(cmd):\n"
    assert found(head + "    subprocess.run(['ps'],"
                 " **UI.external_tool_keyword_arguments())\n") == ["m.py:f"]
    assert not found(head + "    subprocess.run(cmd,"
                     " **UI.external_tool_keyword_arguments(cmd))\n")
    assert not found(head + "    subprocess.run(['/bin/ps'], close_fds=False)\n")


def test_helper_resolves_a_bare_name_into_a_spawnable_launch(monkeypatch):
    monkeypatch.setattr(UI.sys, "platform", "darwin")
    monkeypatch.setattr(UI.shutil, "which",
                        lambda name, path=None: "/usr/bin/" + name)
    kwargs = UI.external_tool_keyword_arguments(["ps", "-A"])
    assert kwargs["executable"] == "/usr/bin/ps"
    assert _takes_posix_spawn([kwargs["executable"]], kwargs)
    assert "executable" not in UI.external_tool_keyword_arguments(["/bin/ps"])
    monkeypatch.setattr(UI.shutil, "which", lambda name, path=None: None)
    assert "executable" not in UI.external_tool_keyword_arguments(["nope"])
    monkeypatch.setattr(UI.sys, "platform", "win32")
    assert "executable" not in UI.external_tool_keyword_arguments(["ps"])


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
