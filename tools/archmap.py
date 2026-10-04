#!/usr/bin/env python3
"""THE GENERATED ARCHITECTURE MAP (owner RULINGS 2026-10-04a (4)): what
exists, in about a hundred tokens, so a session extends it instead of
writing a second one.  Reached through ``tools/blast.py``:

    tools/blast.py --map                      # one line per package
    tools/blast.py --map auto_patch_v2/airport  # one line per module
    tools/blast.py --find ring area           # functions / classes, file:line

Everything printed is read from the code: a module's line is the first
line of its docstring plus its public names; nothing here is a
hand-written list.  PUBLIC NAME RULE (the declared one): a name of
``__all__`` (or, with no ``__all__``, a public top-level def) is shown
only when ANOTHER non-test module uses it — ``from m import n``, ``m.n``
through an imported module, or through a package ``__init__`` re-export.
A name nobody else uses is implementation detail however it is exported;
the header counts those as ``hidden``.

Paths print relative to ``Ortho4XP/`` (the lane cwd): ``src/…``,
``tools/…``, ``../tools/…``, ``../Sources/…``.

The scan is one AST pass per file, cached in the blast index directory as
``symbols.json`` and rebuilt when any scanned file's size or mtime moves.
``scan`` is a pure function of a tree, which is what the twins and the
layering ratchet (``tools/ratchets.py layers``) call.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re

__all__ = ["ROOTS", "make_resolver", "scan", "load", "package_of",
           "render_map", "render_packages", "find", "render_find",
           "hidden_names", "cmd_map", "cmd_find"]

VERSION = "1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOTS = ("Ortho4XP/src", "Ortho4XP/tools", "tools", "Sources")
SRC = "Ortho4XP/src/"
SKIP_DIRS = {"venv", "build", "dist", "dist.nosync", "__pycache__", "Unused",
             "attic", "Resources", ".build"}
# what a ROOT directory holds when it is not a package with a docstring —
# the four scan roots only; every package below them speaks for itself
ROOT_LABELS = {
    "Ortho4XP/src": "engine core: the O4_* modules (tile build, DEM, OSM, "
                    "mesh, masks, DSF, Qt GUI)",
    "Ortho4XP/tools": "measurement, census, replay and audit tools "
                      "(tools/INDEX.md is the catalogue)",
    "tools": "session tools: blast, archmap, ratchets, docq, brief_pack",
    "Sources": "the macOS Swift app",
}
DOC_W, NAMES, SIG_W, FIND_DOC_W, FIND_TOP = 44, 3, 48, 56, 5
PAREN = re.compile(r"\s*\((?:[^()]|\([^()]*\))*\)")   # citations, asides
ROLE = re.compile(r":\w+:")                               # :func:, :class:
SWIFT_TYPE = re.compile(
    r"^(?:(?:public|final|private|fileprivate|internal|open|indirect"
    r"|@\w+(?:\([^)]*\))?)\s+)*"
    r"(class|struct|enum|protocol|actor|extension)\s+([A-Za-z_][\w.]*)")
SWIFT_FUNC = re.compile(r"^\s*(?:[\w@]+\s+)*func\s+(\w+)\s*(\([^{]*)")


# ── the scan ──────────────────────────────────────────────────────────
def _walk(repo, roots):
    """Repo-relative source paths ('/'-spelled), deterministically ordered."""
    out = []
    for root in roots:
        for base, dirs, files in os.walk(os.path.join(repo, root)):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                if name.endswith((".py", ".swift")):
                    out.append(os.path.relpath(os.path.join(base, name),
                                               repo).replace(os.sep, "/"))
    return sorted(set(out))


def make_resolver(paths):
    """``resolve(dotted) -> rel or None``.  Exact under ``Ortho4XP/src``
    first; otherwise the ONE scanned file whose path ends with the dotted
    name (``harness.frames`` -> ``…/harness/frames.py``).  Stricter than
    blast's unique-stem rule on purpose: ``shapely.geometry`` must not
    resolve to a local ``geometry.py`` and mint a layering edge."""
    tails = {}
    for rel in paths:
        if not rel.endswith(".py"):
            continue
        parts = rel[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        for i in range(len(parts)):
            tails.setdefault("/".join(parts[i:]), []).append(rel)

    def resolve(cand):
        key = cand.replace(".", "/")
        hits = tails.get(key, ())
        if len(hits) == 1:
            return hits[0]
        for rel in hits:
            if rel in (SRC + key + ".py", SRC + key + "/__init__.py"):
                return rel
        return None
    return resolve


def _first_line(doc, width=None):
    line = " ".join((doc or "").strip().split("\n\n")[0].split())
    line = PAREN.sub("", ROLE.sub("", line.replace("`", ""))).split(". ")[0]
    line = " ".join(line.split()).replace(" ,", ",").rstrip(".:;, ")
    if width and len(line) > width:
        line = line[:width - 1].rstrip() + "…"
    return line


def _signature(fn):
    a = fn.args
    names = [x.arg for x in a.posonlyargs + a.args]
    names += ["*" + a.vararg.arg] if a.vararg else (["*"] if a.kwonlyargs else [])
    names += [x.arg for x in a.kwonlyargs]
    names += ["**" + a.kwarg.arg] if a.kwarg else []
    sig = ", ".join(n for n in names if n not in ("self", "cls"))
    return sig if len(sig) <= SIG_W else sig[:SIG_W - 1] + "…"


def _str_list(node):
    if isinstance(node, (ast.List, ast.Tuple)):
        return [e.value for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return None


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        return ".".join([node.id] + parts[::-1])
    return None


def _scan_py(rel, text, resolve):
    """One module: doc, __all__, defs, and what it imports / uses of others."""
    tree = ast.parse(text)
    e = {"doc": _first_line(ast.get_docstring(tree)), "all": None,
         "defs": [], "imports": [], "uses": [], "reexports": {}}
    pkg = rel[len(SRC):].split("/")[:-1] if rel.startswith(SRC) else None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(getattr(t, "id", None) == "__all__" for t in tgts):
                e["all"] = (e["all"] or []) + (_str_list(node.value) or [])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            e["defs"].append([node.name, "f", _signature(node), node.lineno,
                              _first_line(ast.get_docstring(node), FIND_DOC_W)])
        elif isinstance(node, ast.ClassDef):
            e["defs"].append([node.name, "c", "", node.lineno,
                              _first_line(ast.get_docstring(node), FIND_DOC_W)])
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and not m.name.startswith("__"):
                    e["defs"].append(
                        [node.name + "." + m.name, "m", _signature(m),
                         m.lineno,
                         _first_line(ast.get_docstring(m), FIND_DOC_W)])
    top = {id(n) for n in tree.body}
    alias, uses = {}, set()
    for parent in ast.walk(tree):
        for node in ast.iter_child_nodes(parent):
            lazy = 0 if (id(node) in top) else 1
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    if pkg is None or node.level - 1 > len(pkg):
                        continue
                    base = pkg[:len(pkg) - (node.level - 1)]
                    full = ".".join(base + ([node.module] if node.module else []))
                else:
                    full = node.module or ""
                target = resolve(full) if full else None
                for a in node.names:
                    sub = resolve(full + "." + a.name) if full else None
                    if sub and sub != target:
                        alias[a.asname or a.name] = sub      # a submodule
                        e["imports"].append([sub, node.lineno, lazy])
                    elif target:
                        uses.add((target, a.name))
                        if not lazy:
                            e["reexports"][a.asname or a.name] = [target, a.name]
                if target:
                    e["imports"].append([target, node.lineno, lazy])
            elif isinstance(node, ast.Import):
                for a in node.names:
                    target = resolve(a.name)
                    if target:
                        alias[a.asname or a.name] = target
                        e["imports"].append([target, node.lineno, lazy])
    if alias:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                d = _dotted(node)
                if d:
                    head, _, name = d.rpartition(".")
                    if head in alias:
                        uses.add((alias[head], name))
    e["uses"] = sorted(uses)
    return e


def _scan_swift(text):
    """Top-level types (column 0) and every func, with its ``///`` line."""
    defs, doc, lines = [], "", text.splitlines()
    for line in lines:                                # file header comment
        s = line.strip()
        if s.startswith("//"):
            s = s.lstrip("/ ").strip()
            if s and not s.endswith(".swift") and not doc:
                doc = _first_line(s)
        elif s:
            break
    prev = ""
    for i, line in enumerate(lines, 1):
        m = SWIFT_TYPE.match(line)
        if m:
            defs.append([m.group(2), "c" if m.group(1) != "extension" else "x",
                         "", i, _first_line(prev, FIND_DOC_W)])
        else:
            f = SWIFT_FUNC.match(line)
            if f:
                sig = " ".join(f.group(2).split()).rstrip(" {")
                defs.append([f.group(1), "f", sig[1:SIG_W].rsplit(")", 1)[0]
                             if ")" in sig[:SIG_W] else sig[1:SIG_W] + "…",
                             i, _first_line(prev, FIND_DOC_W)])
        s = line.strip()
        prev = s[3:].strip() if s.startswith("///") else ""
    return {"doc": doc, "all": None, "defs": defs, "imports": [], "uses": [],
            "reexports": {}}


def scan(repo=REPO, roots=ROOTS):
    """``{rel: entry}`` for every source file under ``roots``.  An entry
    carries ``doc`` (first docstring line), ``all`` (``__all__`` or None),
    ``defs`` ([name, kind, signature, line, doc]), ``imports`` ([target
    rel, line, lazy]) and ``used`` ({its name: how many other modules use
    it})."""
    paths = _walk(repo, roots)
    resolve = make_resolver(paths)
    files = {}
    for rel in paths:
        with open(os.path.join(repo, rel), encoding="utf-8",
                  errors="replace") as f:
            text = f.read()
        try:
            files[rel] = (_scan_swift(text) if rel.endswith(".swift")
                          else _scan_py(rel, text, resolve))
        except SyntaxError:
            files[rel] = {"doc": "(does not parse)", "all": None, "defs": [],
                          "imports": [], "uses": [], "reexports": {}}
    used = {rel: {} for rel in files}
    for rel, e in files.items():
        is_init = rel.endswith("/__init__.py")
        for target, name in e.pop("uses"):
            # a package __init__ naming a submodule's symbol is a re-export,
            # not a use: its own users are followed to the origin below
            if is_init and name in e["reexports"]:
                continue
            trel, seen = target, set()
            while trel != rel and (trel, name) not in seen:
                seen.add((trel, name))
                used[trel].setdefault(name, set()).add(rel)
                nxt = files[trel]["reexports"].get(name)
                if not nxt:
                    break
                trel, name = nxt
        e["imports"] = sorted({(t, ln, lz) for t, ln, lz in e["imports"]
                               if t != rel})
    for rel, e in files.items():
        e.pop("reexports")
        e["used"] = {n: len(u) for n, u in sorted(used[rel].items())}
    return files


# ── the cache ─────────────────────────────────────────────────────────
def _fingerprint(repo, roots):
    h = hashlib.sha256(VERSION.encode())
    for rel in _walk(repo, roots):
        st = os.stat(os.path.join(repo, rel))
        h.update(("%s %d %d\n" % (rel, st.st_mtime_ns, st.st_size)).encode())
    return h.hexdigest()


def load(idx=None, repo=REPO, roots=ROOTS):
    """The scan, from ``<idx>/symbols.json`` when it is current."""
    if idx is None:
        return scan(repo, roots)
    path, fp = os.path.join(idx, "symbols.json"), _fingerprint(repo, roots)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        if doc.get("fingerprint") == fp:
            return doc["files"]
    except (OSError, ValueError):
        pass
    files = scan(repo, roots)
    os.makedirs(idx, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"fingerprint": fp, "files": files}, fh)
    return files


# ── the map ───────────────────────────────────────────────────────────
def _short(rel):
    """Path as typed from ``Ortho4XP/`` (the lane cwd)."""
    return rel[len("Ortho4XP/"):] if rel.startswith("Ortho4XP/") else "../" + rel


def package_of(arg, files):
    """The scanned directory ``arg`` names, or None.  Read the way the map
    prints: under ``Ortho4XP/src/`` first (``auto_patch_v2/airport``),
    then under ``Ortho4XP/`` (``src``, ``tools``), then from the repo root
    (``Sources/SceneryKit``, ``Ortho4XP/tools``); ``../tools`` is the
    repo-root ``tools``."""
    arg = arg.replace(os.sep, "/").rstrip("/")
    dirs = {os.path.dirname(r) for r in files}
    if arg.startswith("../"):
        cands = (arg[3:],)
    else:
        arg = arg.strip("./")
        cands = ("Ortho4XP/src/" + arg, "Ortho4XP/" + arg, arg)
    for cand in cands:
        if cand in dirs or any(d.startswith(cand + "/") for d in dirs):
            return cand
    return None


def _public(e):
    """(shown, hidden): exported names another module uses / does not."""
    exported = e["all"] if e["all"] is not None else [
        d[0] for d in e["defs"] if d[1] in "fc" and not d[0].startswith("_")]
    used = e["used"]
    shown = [n for n in exported if n in used]
    return (sorted(shown, key=lambda n: -used[n]),          # most used first
            [n for n in exported if n not in used])


def hidden_names(files, prefix):
    """``__all__`` names under ``prefix`` that no other module uses."""
    return sorted((rel, n) for rel, e in files.items()
                  if rel.startswith(prefix) and e["all"] is not None
                  for n in _public(e)[1])


def _members(pkg, files):
    return sorted(r for r in files if os.path.dirname(r) == pkg)


def _subpackages(pkg, files):
    subs = {}
    for r in files:
        if r.startswith(pkg + "/") and os.path.dirname(r) != pkg:
            name = r[len(pkg) + 1:].split("/")[0]
            subs[name] = subs.get(name, 0) + 1
    return subs


def _owns(pkg, files):
    init = files.get(pkg + "/__init__.py")
    doc = (init and init["doc"]) or ROOT_LABELS.get(pkg)
    if doc:
        return _trim(doc, pkg, 0)
    stems = [os.path.basename(r).rsplit(".", 1)[0] for r in _members(pkg, files)]
    stems = [s for s in stems if not s.startswith("__")]
    return ", ".join(stems[:5]) + (", …" if len(stems) > 5 else "")


def _trim(doc, stem, width):
    """Drop a leading 'module.name — ' echo of the name, then cut."""
    head, sep, rest = doc.partition(" — ")
    if sep and head.replace("auto_patch_v2.", "").split(".")[-1].lower() \
            in (stem.lower(), os.path.basename(stem).lower()):
        doc = rest
    return doc if not width or len(doc) <= width \
        else doc[:width - 1].rstrip() + "…"


def render_map(pkg, files, wide=False):
    """One line per module of ``pkg``: name, first docstring line, the
    public names another module uses, most used first (Swift: the
    top-level types).  ``wide`` lifts the width and name caps."""
    rows, hidden = [], 0
    for rel in _members(pkg, files):
        e, stem = files[rel], os.path.basename(rel).rsplit(".", 1)[0]
        if stem in ("__init__", "__main__"):
            continue
        if rel.endswith(".swift"):
            names = [d[0] for d in e["defs"] if d[1] == "c"]
        else:
            names, hid = _public(e)
            hidden += len(hid)
        doc = _trim(e["doc"], stem, 0 if wide else DOC_W)
        if not wide and len(names) > NAMES:
            names = names[:NAMES] + ["+%d" % (len(names) - NAMES)]
        if not doc and not rel.endswith(".swift"):
            doc = "(no docstring)"
        if names == [stem]:                 # a Swift file named for its type
            names = []
        rows.append(stem + ("  " + doc if doc else "")
                    + (" | " + " ".join(names) if names else ""))
    subs = _subpackages(pkg, files)
    if not rows:                            # a directory of packages
        return render_packages(files, pkg)
    swift = all(r.endswith(".swift") for r in _members(pkg, files))
    out = ["%s — %s" % (_short(pkg), _owns(pkg, files)),
           "%d files | top-level types" % len(rows) if swift else
           "%d modules | exports another module uses, most used first "
           "(%d unused exports not shown)" % (len(rows), hidden)] + rows
    if subs:
        out.append("subpackages: " + ", ".join(
            "%s (%d)" % kv for kv in sorted(subs.items())))
    return "\n".join(out)


def render_packages(files, under=""):
    """The package-level map: one line per directory that holds source
    (``under``: only the directories below that one)."""
    out = ["packages (path from Ortho4XP/, modules, what it owns) — "
           "`blast.py --map <path>` lists one"]
    for pkg in sorted({os.path.dirname(r) for r in files}, key=_short):
        if under and not pkg.startswith(under + "/"):
            continue
        n = sum(1 for r in _members(pkg, files)
                if not os.path.basename(r).startswith("__"))
        if n:
            own = _owns(pkg, files)
            out.append("%s  %d  %s" % (
                _short(pkg), n, own if len(own) <= 80 else own[:79] + "…"))
    return "\n".join(out)


# ── find ──────────────────────────────────────────────────────────────
def _words(name):
    return {w.lower() for w in re.findall(r"[A-Za-z][a-z0-9]*|[0-9]+",
                                          name.replace("_", " "))}


def _starts_word(term, text):
    return re.search(r"(?<![a-z0-9])" + re.escape(term), text) is not None


def find(terms, files):
    """Defs matching EVERY term (case-insensitive) in their own name or
    first docstring line, or in their MODULE's name or first docstring
    line (``union find`` reaches ``union_find.find_root``).  RANKED FOR
    REUSE: names another non-test module uses first, then public names,
    then private ones; inside a group the closest name match, then the
    most used.  Rows are (rel, line, name, kind, signature, doc, users)."""
    terms = [t.lower() for t in terms if t]
    hits = []
    for rel, e in files.items():
        used = e["used"]
        stem = os.path.basename(rel).rsplit(".", 1)[0].lower()
        mdoc = e["doc"].lower().replace("-", " ")
        in_mod = [t in stem or _starts_word(t, mdoc) for t in terms]
        for name, kind, sig, line, doc in e["defs"]:
            leaf = name.rsplit(".", 1)[-1]
            low, dlow, words = leaf.lower(), doc.lower(), _words(leaf)
            if not all(t in low or _starts_word(t, dlow) or m
                       for t, m in zip(terms, in_mod)):
                continue
            if "_".join(terms) == low or "".join(terms) == low:
                rank = 0
            elif all(t in words for t in terms):
                rank = 1
            elif all(t in low for t in terms):
                rank = 2
            elif all(t in low or _starts_word(t, dlow) for t in terms):
                rank = 3
            else:
                rank = 4                    # reached through its module
            users = used.get(name.split(".")[0], 0)   # a method: its class
            group = 0 if users else (2 if leaf.startswith("_") else 1)
            hits.append((group, kind == "m", rank, -users, len(name), rel,
                         line, name, kind, sig, doc, users))
    return [h[5:] for h in sorted(hits)]


def render_find(terms, files, top=FIND_TOP):
    """``path:line name(args) [shared N] — doc``; ``[shared N]`` marks a
    name N other modules already use — the one to extend."""
    hits = find(terms, files)
    if not hits:
        return "no function or class matches %r — it does not exist yet" \
            % " ".join(terms)
    out = []
    for rel, line, name, kind, sig, doc, users in hits[:top or None]:
        shape = {"c": name, "x": "extension " + name}.get(
            kind, "%s(%s)" % (name, sig))
        out.append("%s:%d %s%s%s" % (
            _short(rel), line, shape,
            " [shared %d]" % users if users and kind != "m" else "",
            " — " + doc if doc else ""))
    if top and len(hits) > top:
        out.append("+%d more matched (--top N; 0 = all)" % (len(hits) - top))
    return "\n".join(out)


# ── the two commands blast.py dispatches ──────────────────────────────
def cmd_map(arg, idx=None, wide=False, repo=REPO):
    files = load(idx, repo)
    if not arg or arg == "packages":
        print(render_packages(files))
        return 0
    pkg = package_of(arg, files)
    if pkg is None:
        print("no package %r — `blast.py --map` lists them" % arg)
        return 2
    print(render_map(pkg, files, wide))
    return 0


def cmd_find(terms, idx=None, top=FIND_TOP, repo=REPO):
    print(render_find(terms, load(idx, repo), top))
    return 0
