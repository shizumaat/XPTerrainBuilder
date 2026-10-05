"""Both frozen engines carry the same interpreter belt.

``Ortho4XP_Qt.spec`` has pinned the embedded interpreter's string-hash
seed since the Qt bundle was first frozen; ``Ortho4XP.spec`` — the
engine the mac app embeds — did not, so the two frozen engines started
their interpreters differently.  A spec is Python: it must also still
parse, which is the only check available here (freezing is not run in
the suite).
"""

import ast
import os

ENGINE_ROOT = os.path.join(os.path.dirname(__file__), "..")
SPECS = ("Ortho4XP.spec", "Ortho4XP_Qt.spec")


def _source(name):
    with open(os.path.join(ENGINE_ROOT, name), encoding="utf-8") as handle:
        return handle.read()


def test_every_spec_parses():
    for name in SPECS:
        ast.parse(_source(name), filename=name)


def test_every_spec_pins_the_hash_seed():
    for name in SPECS:
        assert "('hash_seed=0', None, 'OPTION')" in _source(name), name


def test_every_spec_names_the_scenery_pack_module():
    """Whether scenery_packs.ini is honoured (owner RULINGS 2026-09-17b)
    rides on ``O4_Scenery_Packs`` reaching the frozen bundle.  Its
    consumers import it at TOP LEVEL, so PyInstaller finds it statically;
    naming it in hiddenimports is the belt — the lazy-import class shipped
    a broken frozen engine on 2026-09-10."""
    for name in SPECS:
        assert "'O4_Scenery_Packs'" in _source(name), name


def test_every_spec_collects_laspy():
    """#130: ``laspy`` is imported INSIDE the las_tile_index strategy, so
    PyInstaller's static scan never sees it (the highspy precedent); both
    frozen engines must collect it explicitly."""
    for name in SPECS:
        assert "collect_submodules('laspy')" in _source(name), name


def test_every_spec_collects_lazrs():
    """#153: the USGS Lidar Point Cloud rung reads LAZ through laspy's
    Rust backend, which laspy looks up at run time -- invisible to the
    static scan; both frozen engines must collect it explicitly, and the
    release workflow's frozen self-check imports it."""
    for name in SPECS:
        assert "collect_submodules('lazrs')" in _source(name), name
    workflow = os.path.join(ENGINE_ROOT, "..", ".github", "workflows",
                            "release.yml")
    with open(workflow, encoding="utf-8") as handle:
        text = handle.read()
    assert text.count("--import-selfcheck laspy,lazrs") == 3


# ---------------------------------------------------------------------------
# The console's text layer is part of the same interpreter belt (#171, #125)
# ---------------------------------------------------------------------------
ENTRIES = ("Ortho4XP.py", "Ortho4XP_Qt.py")


def _entry_tree(name):
    import ast as _ast
    return _ast.parse(_source(name), filename=name)


def _module_level_call_line(tree, attr):
    """Line of the first MODULE-LEVEL ``<x>.<attr>()`` call, or None.

    Module level matters: a call nested in an ``if`` runs only on some
    argv, and the whole point is that it runs on every one.
    """
    import ast as _ast
    for node in tree.body:
        if isinstance(node, _ast.Expr) and isinstance(node.value, _ast.Call) \
                and isinstance(node.value.func, _ast.Attribute) \
                and node.value.func.attr == attr:
            return node.lineno
    return None


def test_every_entry_pins_the_console_before_anything_can_print():
    """#125: the FROZEN Windows engine wrote stderr in the ANSI code page,
    so ``Adolfo Suárez`` reached ``logs/engine-stderr.log`` as undecodable
    cp1252.  #171: a printed non-cp1252 character is an exception, not
    mojibake.  Both frozen engines must pin their streams at the top of
    the entry, ahead of the PROJ self-check — which PRINTS its failure to
    stderr — and ahead of every heavy import.  Freezing is not run in the
    suite, so the entry source is what is checked; the spec files add no
    stream setup of their own (``runtime_hooks=[]`` in both)."""
    import ast as _ast
    for name in ENTRIES:
        source = _source(name)
        assert "import O4_Console_Encoding" in source, name
        tree = _entry_tree(name)
        pinned = _module_level_call_line(tree, "configure_console_streams")
        assert pinned is not None, (
            f"{name} does not call "
            "O4_Console_Encoding.configure_console_streams() at module level")

        prints = [n.lineno for n in _ast.walk(tree)
                  if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)
                  and n.func.id == "print"]
        assert prints, name
        assert pinned < min(prints), (
            f"{name} prints at line {min(prints)} before pinning the console "
            f"at line {pinned}")

        proj = [n.lineno for n in _ast.walk(tree)
                if isinstance(n, _ast.Name) and n.id == "O4_Proj_Runtime"]
        assert proj and pinned < min(proj), (
            f"{name} loads the PROJ runtime at line {min(proj)} — whose "
            f"self-check prints to stderr — before pinning the console at "
            f"line {pinned}")


def test_the_jsonl_transport_pins_its_streams_before_it_repoints_stdout():
    """``serve`` is the transport's own door (the tests' harness and any
    other host enter there, not through the entry), and it is the stream
    setup #125 names: ``sys.stdout`` is repointed at ``sys.stderr``, which
    makes stderr the engine's whole console."""
    path = os.path.join(ENGINE_ROOT, "src", "o4_engine", "jsonl.py")
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    pinned = source.index("O4_Console_Encoding.configure_console_streams()")
    repointed = source.index("sys.stdout = sys.stderr")
    assert pinned < repointed, (
        "jsonl.serve repoints sys.stdout at sys.stderr before pinning the "
        "streams")


def test_every_entry_claims_the_spawn_bootstrap_first():
    """Issue #362 (RULINGS 2026-10-05d): a spawned worker of a FROZEN
    engine is the executable re-exec'd as ``<exe> --multiprocessing-fork``;
    PyInstaller's runtime hook only DEFINES ``freeze_support`` as the
    diverter.  ``Ortho4XP_Qt.py`` — the Windows/Linux engine — never called
    it, so every pool worker there would have started the Qt application.
    Both entries call it under the ``__main__`` guard ahead of every other
    statement but the stdlib imports, and both dispatch the pool's
    self-check."""
    import ast as _ast
    for name in ENTRIES:
        tree = _entry_tree(name)
        seen = None
        for node in tree.body:
            if isinstance(node, (_ast.Import, _ast.ImportFrom)) or (
                    isinstance(node, _ast.Expr)
                    and isinstance(node.value, _ast.Constant)):
                continue                       # docstring, ``import os, sys``
            seen = node
            break
        assert isinstance(seen, _ast.If), name
        assert "__main__" in _ast.unparse(seen.test), name
        assert "multiprocessing.freeze_support()" in _ast.unparse(seen), name
        source = _source(name)
        assert "--pool-selfcheck" in source, name
        assert "O4_Pool_Selfcheck.main(sys.argv)" in source, name

