"""TWINS FOR ``tools/archmap.py`` — the generated architecture map (owner
RULINGS 2026-10-04a (4)): ``tools/blast.py --map`` / ``--find``.

The rules are pinned on synthetic trees; the live assertions read the
checked-out tree (no build, no corpus, no network) and never pin a module
list — packages move (04c (4)), the map is generated.
"""
import ast
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
sys.dont_write_bytecode = True

import archmap  # noqa: E402

V2 = "Ortho4XP/src/auto_patch_v2"
# modules that predate the rule and carry no ``__all__``: the list may
# SHRINK (a name here whose file gained one, or left the package, is
# simply unused); a module not listed here must declare ``__all__``.
NO_ALL_YET = {"__init__.py", "emit/__init__.py", "model/__init__.py",
              "airport/wall_corridor_probe.py", "airport/wall_geometry.py",
              "law/tunnel_object_schema.py", "model/pulse.py",
              "pipeline/xplat.py"}


def _write(root, rel, text):
    path = os.path.join(str(root), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _tree(root):
    pkg = "Ortho4XP/src/auto_patch_v2/geom/"
    _write(root, pkg + "__init__.py",
           '"""auto_patch_v2.geom — THE LEAF GEOMETRY (RULINGS x)."""\n'
           "from .ring import ring_area\n__all__ = ['ring_area']\n")
    _write(root, pkg + "ring.py",
           '"""Ring measures (plan §1).  Second sentence."""\n'
           "__all__ = ['ring_area', 'ring_length', 'perimeter']\n"
           "def ring_area(ring, signed=False):\n"
           '    """Shoelace area of a closed ring."""\n'
           "def ring_length(ring):\n    return perimeter(ring)\n"
           "def perimeter(ring):\n"
           '    """Length of the ring boundary."""\n'
           "def _helper(a):\n    pass\n")
    _write(root, "Ortho4XP/src/auto_patch_v2/solve/__init__.py", '"""ONE solve."""\n')
    _write(root, "Ortho4XP/src/auto_patch_v2/solve/design.py",
           '"""The design surface."""\n'
           "from ..geom import ring_area\nfrom ..geom import ring\n"
           "__all__ = ['solve']\n"
           "def solve(p):\n    return ring_area(p) + ring.perimeter(p)\n")
    _write(root, "Ortho4XP/tools/census.py",
           '"""A census tool."""\nimport shapely.geometry\n'
           "def run():\n    pass\n")
    _write(root, "Ortho4XP/src/auto_patch_v2/geom/geometry.py",
           '"""Not shapely."""\n__all__ = []\n')
    _write(root, "Sources/Kit/Client.swift",
           "// Client.swift\n// The engine client.\n\n"
           "/// Talks JSONL to the engine.\npublic final class Client {\n"
           "    func send(_ line: String) -> Bool {\n    }\n}\n"
           "extension Client {\n}\n")
    return str(root)


def test_map_shows_only_names_another_module_uses(tmp_path):
    files = archmap.scan(_tree(tmp_path))
    ring = files[V2 + "/geom/ring.py"]
    # ring_area through the package re-export, perimeter through the
    # imported module; ring_length is exported and used by nobody else
    assert set(ring["used"]) == {"ring_area", "perimeter"}
    assert files[V2 + "/geom/__init__.py"]["used"] == {"ring_area": 1}
    text = archmap.render_map(V2 + "/geom", files)
    line = [l for l in text.splitlines() if l.startswith("ring ")][0]
    assert line == "ring  Ring measures | ring_area perimeter"
    assert "ring_length" not in text and "__init__" not in text
    assert text.splitlines()[0] == "src/auto_patch_v2/geom — THE LEAF GEOMETRY"
    assert archmap.hidden_names(files, V2 + "/") == [
        (V2 + "/geom/ring.py", "ring_length"),
        (V2 + "/solve/design.py", "solve")]


def test_a_third_party_import_never_resolves_to_a_local_stem(tmp_path):
    files = archmap.scan(_tree(tmp_path))
    assert files["Ortho4XP/tools/census.py"]["imports"] == []


def test_map_is_deterministic_and_the_cache_follows_the_tree(tmp_path):
    repo, idx = _tree(tmp_path / "repo"), str(tmp_path / "idx")
    a = archmap.load(idx, repo)
    assert archmap.render_packages(a) == archmap.render_packages(archmap.scan(repo))
    assert archmap.render_map(V2 + "/geom", archmap.load(idx, repo)) \
        == archmap.render_map(V2 + "/geom", archmap.scan(repo))
    _write(repo, V2 + "/geom/extra.py", '"""New."""\n__all__ = []\n')
    assert V2 + "/geom/extra.py" in archmap.load(idx, repo)


def test_package_arguments_read_the_way_the_map_prints(tmp_path):
    files = archmap.scan(_tree(tmp_path))
    assert archmap.package_of("auto_patch_v2/geom", files) == V2 + "/geom"
    assert archmap.package_of("tools", files) == "Ortho4XP/tools"
    assert archmap.package_of("Ortho4XP/tools", files) == "Ortho4XP/tools"
    assert archmap.package_of("../Sources/Kit", files) == "Sources/Kit"
    assert archmap.package_of("nowhere", files) is None
    # a directory of packages lists them, one line each
    top = archmap.render_map(V2, files).splitlines()
    assert "src/auto_patch_v2/geom  2  THE LEAF GEOMETRY" in top
    assert "src/auto_patch_v2/solve  1  ONE solve" in top
    swift = archmap.render_map("Sources/Kit", files).splitlines()
    assert swift[1:] == ["1 files | top-level types", "Client  The engine client"]


def test_find_matches_name_or_docstring_with_signature_and_line(tmp_path):
    files = archmap.scan(_tree(tmp_path))
    out = archmap.render_find(["ring", "area"], files).splitlines()
    assert out[0].startswith("src/auto_patch_v2/geom/ring.py:")
    assert out[0].endswith(" ring_area(ring, signed) [shared 1]"
                           " — Shoelace area of a closed ring")
    assert archmap.render_find(["send"], files) == \
        "../Sources/Kit/Client.swift:6 send(_ line: String)"
    assert "does not exist yet" in archmap.render_find(["nothing_like_it"], files)
    last = archmap.render_find(["ring"], files, top=1).splitlines()[-1]
    assert last.startswith("+3 more matched")


def test_find_ranks_shared_then_public_then_private(tmp_path):
    """RANKED FOR REUSE: what another module already uses comes first and
    is marked; a private one-file helper never outranks a shared export."""
    repo = _tree(tmp_path)
    _write(repo, V2 + "/solve/local.py",
           '"""Local."""\n__all__ = []\n'
           "def _ring_area(r):\n    pass\n"
           "def ring_area_public(r):\n    pass\n")
    files = archmap.scan(repo)
    names = [h[2] for h in archmap.find(["ring", "area"], files)]
    # _ring_area is the closer NAME match and still comes last
    assert names[:3] == ["ring_area", "ring_area_public", "_ring_area"]
    assert [h[2] for h in archmap.find(["ring"], files)][:2] \
        == ["ring_area", "perimeter"]                 # the two shared names
    out = archmap.render_find(["ring", "area"], files).splitlines()
    assert "[shared" in out[0] and not any("[shared" in l for l in out[1:3])


def test_find_matches_the_module_name_and_docstring(tmp_path):
    """`union find` must reach `union_find.find_root`: the keywords are in
    the MODULE's name and docstring, not the function's."""
    repo = _tree(tmp_path)
    _write(repo, V2 + "/geom/union_find.py",
           '"""UNION-FIND: the root of an element\'s set."""\n'
           "__all__ = ['find_root']\n"
           "def find_root(parent, i):\n    pass\n")
    _write(repo, V2 + "/solve/comp.py",
           '"""Components."""\nfrom ..geom.union_find import find_root\n'
           "__all__ = []\n"
           "class _UnionFind:\n    pass\n")
    files = archmap.scan(repo)
    assert [h[2] for h in archmap.find(["union", "find"], files)] \
        == ["find_root", "_UnionFind"]
    assert [h[2] for h in archmap.find(["root", "set"], files)] == ["find_root"]


# ------------------------------------------------------------------ live
def test_live_find_finds_a_known_symbol():
    files = archmap.scan(REPO, ("tools",))
    hit = archmap.find(["make", "resolver"], files)[0]
    assert hit[0] == "tools/archmap.py" and hit[2] == "make_resolver"


def test_live_find_puts_the_shared_helper_first():
    files = archmap.scan(REPO, ("Ortho4XP/src", "Ortho4XP/tools"))
    for terms, want in ((["union", "find"], "find_root"),
                        (["sha256", "file"], "sha256_file")):
        hits = archmap.find(terms, files)
        assert hits[0][2] == want and hits[0][6] > 0, (terms, hits[:3])
        groups = [0 if h[6] else (2 if h[2].rsplit(".", 1)[-1].startswith("_")
                                  else 1) for h in hits if h[3] != "m"]
        assert groups == sorted(groups), terms
    text = archmap.render_find(["union", "find"], files)
    assert len(text) <= 900 and "more matched" in text


def test_live_map_stays_scannable():
    """The point is a hundred tokens, not completeness: one line per
    module, and the largest package's map stays near 1.5k tokens."""
    files = archmap.scan(REPO, ("Ortho4XP/src",))
    for pkg in sorted({os.path.dirname(r) for r in files if r.startswith(V2 + "/")
                       and os.path.dirname(r) != V2}):
        text = archmap.render_map(pkg, files)
        members = [r for r in files if os.path.dirname(r) == pkg
                   and not os.path.basename(r).startswith("__")]
        assert len(text.splitlines()) == len(members) + 2, pkg
        assert len(text) <= 100 * len(members) + 200, (pkg, len(text))
        assert max(len(l) for l in text.splitlines()[2:]) <= 180, pkg


def test_every_v2_module_has_a_docstring_and_declares_all():
    """HONEST INPUTS (04a (4)): the map is the docstring's first line and
    ``__all__``; a module without them is invisible in it."""
    no_doc, no_all = [], []
    for base, dirs, names in os.walk(os.path.join(REPO, V2)):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, os.path.join(REPO, V2)).replace(os.sep, "/")
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            if not ast.get_docstring(tree):
                no_doc.append(rel)
            declared = any(isinstance(n, ast.Assign) and any(
                getattr(t, "id", None) == "__all__" for t in n.targets)
                for n in tree.body)
            if not declared and name != "__main__.py" and rel not in NO_ALL_YET:
                no_all.append(rel)
    assert not no_doc, "v2 modules with no docstring: %s" % no_doc
    assert not no_all, ("v2 modules with no __all__ (declare what the "
                        "module offers): %s" % no_all)


def test_blast_cli_serves_the_map_and_find(tmp_path):
    env = dict(os.environ, BLAST_INDEX_DIR=str(tmp_path / "idx"))
    blast = os.path.join(TOOLS, "blast.py")

    def run(*args):
        return subprocess.run([sys.executable, blast, *args], env=env,
                              capture_output=True, text=True, encoding="utf-8")
    r = run("--map")
    assert r.returncode == 0, r.stderr
    assert "src/auto_patch_v2/airport  " in r.stdout
    r = run("--map", "../tools")
    assert r.returncode == 0 and "\narchmap  " in r.stdout
    assert run("--map", "no/such/package").returncode == 2
    r = run("--find", "make_resolver")
    assert r.returncode == 0 and "../tools/archmap.py:" in r.stdout
    assert os.path.exists(os.path.join(env["BLAST_INDEX_DIR"], "symbols.json"))


def test_archmap_is_indexed():
    index = open(os.path.join(TOOLS, "INDEX.md"), encoding="utf-8").read()
    assert "| `tools/archmap.py` |" in index
    assert "--map" in index and "--find" in index
