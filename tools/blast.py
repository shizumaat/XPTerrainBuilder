#!/usr/bin/env python3
"""Blast-radius index for XPTerrainBuilder: what else moves when a file moves.

    Ortho4XP/venv/bin/python tools/blast.py <file>   # print the blast card
    tools/blast.py --rebuild                         # force a rebuild
    tools/blast.py --audit                           # recall audit + canaries
    tools/blast.py --audit --mutations 3             # + the mutation-recall twin
    tools/blast.py --tests-for <file> [--since REF]  # the SWEEP SELECTION

Design rule: the index must fail LOUD ("not indexed", "stale", "low
confidence"), never fail PLAUSIBLE.  Absence of data is never rendered as a
safety claim.  Import lines are AST-exact; co-change is a weak historical
signal and is labelled as such.  Importable without side effects.

``--tests-for`` (BS1, spec docs/specs/blast-sweep-and-artifact-ledger-spec.md)
turns the index into a SWEEP SELECTOR: it reads the diff, works out which
top-level symbols actually moved, and prints the test files whose recorded
symbol USE intersects them.  Its law is RECALL OVER PRECISION — every clause
below is a UNION, and anything the index cannot attribute falls back WIDE
(all direct-importer tests) instead of silently narrowing:

    1. the tests attributed to the changed SYMBOLS;
    2. ALL direct-importer tests of a changed file whose total test count is
       small (<= --cheap-ceiling, default 15) — a cheap file just runs
       everything;
    3. ALL direct-importer tests of a changed file carrying a symbol the
       index cannot attribute (dynamic use, a re-export, ``__all__``, a
       module-level edit outside any named symbol);
    4. changed test files themselves.

The file list goes to STDOUT, one per line (``| xargs venv/bin/python -m
pytest``); the stamped header — changed symbols, per-clause sizes, fallbacks
fired — goes to STDERR, so the pipe stays clean.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

#: v2 adds the per-symbol TEST attribution and the attributed-symbol roster
#: (``symbol_tests`` / ``symbols_attributed``) that --tests-for selects on.
#: Bumping it makes every v1 index on disk rebuild instead of answering a
#: --tests-for query out of shards that never recorded symbol edges.
VERSION = "2"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_ROOTS = ("Ortho4XP/src", "Ortho4XP/tools", "Ortho4XP/tests")
SRC_PREFIX = "Ortho4XP/src/"
TESTS_PREFIX = "Ortho4XP/tests/"
#: Clause 2's threshold: a file whose whole direct-importer test sweep is
#: this small is not worth narrowing — running all of it costs less than
#: one wrong selection.
CHEAP_CEILING = 15
SKIP = (".claude/worktrees", "/venv/", "/build/", "/dist/", "__pycache__",
        "dist.nosync")
SHARDS = ("modules", "roles", "flags", "wire", "artifacts", "meta")
EVENTS_PY = "Ortho4XP/src/o4_engine/events.py"
SWIFT_CLIENT = "Sources/SceneryKit/OrthoEngineClient.swift"
CMD_PY = ("Ortho4XP/src/o4_engine/jsonl.py", "Ortho4XP/src/o4_engine/session.py")
CONTRACTS = os.path.join(REPO, "tools", "artifact_contracts.json")
ROLE_CANARIES = {"apron", "primary_parallel", "runway"}
MECHANISM = ("the wire name IS the Python class name (type(self).__name__) and "
             "field names travel as JSON keys; Swift matches string literals. "
             "Renaming either silently breaks the GUI -- the string never "
             "appears in Python source.")


def index_dir(override=None):
    return (override or os.environ.get("BLAST_INDEX_DIR")
            or os.path.join(REPO, ".blast_index"))


def _git(*args):
    return subprocess.run(("git",) + args, cwd=REPO, capture_output=True,
                          text=True).stdout


def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8", errors="replace") as f:
        return f.read()


def _fingerprint():
    return (_git("rev-parse", "HEAD").strip(),
            hashlib.sha256(_git("status", "--porcelain").encode()).hexdigest())


def scan_paths():
    """Repo-relative .py paths in scope, deterministically ordered."""
    out = []
    for root in SCAN_ROOTS:
        for base, dirs, files in os.walk(os.path.join(REPO, root)):
            dirs[:] = sorted(d for d in dirs
                             if not any(k.strip("/") == d for k in SKIP))
            for name in sorted(f for f in files if f.endswith(".py")):
                rel = os.path.relpath(os.path.join(base, name), REPO)
                if not any(k in "/" + rel for k in SKIP):
                    out.append(rel)
    return out


def modkey(rel):
    """src -> full dotted path under Ortho4XP/src; tools/tests -> repo path."""
    if not rel.startswith(SRC_PREFIX):
        return rel
    parts = rel[len(SRC_PREFIX):].split("/")
    parts = parts[:-1] if parts[-1] == "__init__.py" else parts[:-1] + [parts[-1][:-3]]
    return ".".join(parts)


def pkg_parts(rel):
    """Dotted package the file lives in (src only); None for tools/tests."""
    if not rel.startswith(SRC_PREFIX):
        return None
    return rel[len(SRC_PREFIX):].split("/")[:-1]


def _str_assigns(tree):
    return {t.id: n.value.value for n in tree.body
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
            for t in n.targets if isinstance(t, ast.Name)}


def role_values():
    """ROLE_* value vocabulary, resolving one hop of Name/Attribute alias."""
    layout = ast.parse(_read(SRC_PREFIX + "auto_patch/layout.py"))
    lit_l = _str_assigns(layout)
    lit_s = _str_assigns(ast.parse(_read(SRC_PREFIX + "auto_patch/pavement/strips.py")))
    vals, unresolved = set(), []
    for node in layout.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets
                 if isinstance(t, ast.Name) and t.id.startswith("ROLE_")]
        v = node.value
        if not names:
            continue
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            hit = v.value
        elif isinstance(v, ast.Attribute):            # PS.ROLE_APRON
            hit = lit_s.get(v.attr)
        elif isinstance(v, ast.Name):                 # local one-hop alias
            hit = lit_l.get(v.id) or lit_s.get(v.id)
        else:
            hit = None
        vals.add(hit) if hit else unresolved.append(names[0])
    missing = ROLE_CANARIES - vals
    if missing:
        raise SystemExit(
            "BUILD FAILED: role vocabulary lost %s (unresolved: %s). layout.py's"
            " ROLE_* shape changed -- fix blast.py role_values()."
            % (sorted(missing), unresolved))
    return vals, unresolved


def _is_environ_get(node):
    f = node.func
    return (isinstance(f, ast.Attribute) and f.attr == "get"
            and isinstance(f.value, ast.Attribute) and f.value.attr == "environ"
            and node.args and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value.startswith("O4_"))


def parse_all(roles):
    """One AST pass: import edges, symbol edges, env flags, role literals."""
    paths = scan_paths()
    mods = {modkey(r): r for r in paths}
    stems = defaultdict(list)
    for key in mods:
        stems[key.split(".")[-1]].append(key)
    uniq = {s: k[0] for s, k in stems.items() if len(k) == 1}
    importers, sym_users = defaultdict(set), defaultdict(set)
    env_reads, env_defaults = defaultdict(set), defaultdict(set)
    role_lits, uses_ap, fails = defaultdict(set), set(), []

    def hit(cand, rel, names=()):
        target, parts = None, cand.split(".")
        if cand in mods:
            target = cand
        else:                       # trim leading components, then unique stem
            for i in range(1, len(parts) - 1):
                if ".".join(parts[i:]) in mods:
                    target = ".".join(parts[i:])
                    break
            target = target or uniq.get(parts[-1])
        if target is None:
            return
        importers[target].add(rel)
        if target.split(".")[0] == "auto_patch":
            uses_ap.add(rel)
        for n in names:
            sym_users[(target, n)].add(rel)

    for rel in paths:
        try:
            tree = ast.parse(_read(rel))
        except SyntaxError:
            fails.append(rel)
            continue
        pkg, my_roles = pkg_parts(rel), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:                        # RELATIVE: resolve level
                    if pkg is None or node.level - 1 > len(pkg):
                        continue
                    base = pkg[:len(pkg) - (node.level - 1)]
                    full = ".".join(base + ([node.module] if node.module else []))
                else:
                    full = node.module or ""
                if not full:
                    continue
                names = [a.name for a in node.names]
                hit(full, rel, names)
                for n in names:                       # submodule-via-from
                    hit(full + "." + n, rel)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    hit(a.name, rel)
            elif isinstance(node, ast.Call) and _is_environ_get(node):
                flag = node.args[0].value
                env_reads[flag].add(rel)
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    env_defaults[flag].add(repr(node.args[1].value))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and node.value in roles:
                my_roles.add(node.value)
        for value in my_roles:
            role_lits[value].add(rel)
    return dict(paths=paths, importers=importers, sym_users=sym_users,
                env_reads=env_reads, env_defaults=env_defaults,
                role_lits=role_lits, uses_ap=uses_ap, fails=fails)


def _rename_map():
    """old path -> newest path, chained through the repo's two mass renames."""
    toks = [t.strip("\n") for t in
            _git("log", "-M", "--diff-filter=R", "--name-status",
                 "--format=%x01%H", "-z").split("\0")]
    ren, i = {}, 0
    while i < len(toks):
        if re.fullmatch(r"[RC]\d*", toks[i]) and i + 2 < len(toks):
            ren.setdefault(toks[i + 1], toks[i + 2])
            i += 3
        else:
            i += 1
    out = {}
    for old in ren:
        seen, cur = {old}, ren[old]
        while cur in ren and ren[cur] not in seen:
            seen.add(cur)
            cur = ren[cur]
        out[old] = cur
    return out


def cochange():
    """Historical co-edit pairs, rename-aware.  A weak signal by construction."""
    ren, live = _rename_map(), set(_git("ls-files").splitlines())
    commits, cur = [], []
    for t in [x.strip("\n") for x in
              _git("log", "-M", "--name-only", "--format=%x01%H", "-z").split("\0")]:
        if t.startswith("\x01"):
            commits.append(cur)
            cur = []
        elif t.endswith((".py", ".swift")) and ".claude/worktrees" not in t:
            cur.append(ren.get(t, t))       # map renames BEFORE the live filter
    commits.append(cur)
    pair, solo, usable = defaultdict(int), defaultdict(int), 0
    for c in commits:
        files = sorted({f for f in c if f in live})
        if not 2 <= len(files) <= 25:
            continue
        usable += 1
        for i, a in enumerate(files):
            solo[a] += 1
            for b in files[i + 1:]:
                pair[(a, b)] += 1
    out = defaultdict(list)
    for (a, b), n in pair.items():
        if n < 3:
            continue
        rec = {"n": n}
        if min(solo[a], solo[b]) >= 5:      # enough support to quote a percent
            rec["pct"] = round(n / min(solo[a], solo[b]), 2)
        out[a].append(dict(rec, file=b))
        out[b].append(dict(rec, file=a))
    return ({k: sorted(v, key=lambda d: (-d.get("pct", 0), -d["n"]))[:6]
             for k, v in out.items()}, usable)


def _python_commands():
    """Command names the engine dispatches (handler dict / == / handlers[k])."""
    cmds = set()
    for rel in CMD_PY:
        if not os.path.exists(os.path.join(REPO, rel)):
            continue
        for n in ast.walk(ast.parse(_read(rel))):
            if isinstance(n, ast.Dict) and len(n.keys) >= 3 and all(
                    isinstance(k, ast.Constant) and isinstance(k.value, str)
                    for k in n.keys) and all(
                    isinstance(v, ast.Attribute) for v in n.values):
                cmds.update(k.value for k in n.keys)
            elif isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) \
                    and n.left.id in ("cmd", "command"):
                cmds.update(c.value for c in n.comparators
                            if isinstance(c, ast.Constant)
                            and isinstance(c.value, str))
            elif isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) \
                    and "handler" in n.value.id \
                    and isinstance(n.slice, ast.Constant) \
                    and isinstance(n.slice.value, str):
                cmds.add(n.slice.value)
    return cmds


def _swift_commands():
    out = set()
    for base, _, files in os.walk(os.path.join(REPO, "Sources")):
        for name in (f for f in files if f.endswith(".swift")):
            with open(os.path.join(base, name), errors="replace") as fh:
                body = fh.read()
            out.update(re.findall(r'send\(\s*command:\s*"([^"]+)"', body))
            out.update(re.findall(r'"cmd"\s*:\s*"([^"]+)"', body))
    return out


def wire_scan():
    """Both directions of the JSON-lines engine protocol."""
    events, fields = [], {}
    for n in ast.parse(_read(EVENTS_PY)).body:
        if isinstance(n, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id == "EngineEvent" for b in n.bases):
            events.append(n.name)
            fields[n.name] = [s.target.id for s in n.body
                              if isinstance(s, ast.AnnAssign)
                              and isinstance(s.target, ast.Name)
                              and s.target.id not in ("seq", "ts")]
    swift = _read(SWIFT_CLIENT)
    cases = set(re.findall(r'case\s+"([A-Za-z_]\w*)"\s*:', swift))
    lits = set(re.findall(r'"([^"\\\n]*)"', swift))
    py, sw = _python_commands(), _swift_commands()
    return {
        "python_source": EVENTS_PY, "swift_consumer": SWIFT_CLIENT,
        "mechanism": MECHANISM, "events": sorted(events), "fields": fields,
        "python_only": sorted(set(events) - cases),
        "swift_only": sorted(cases - set(events)),
        "fields_unreferenced_in_swift":
            sorted({f for c in events for f in fields[c]} - lits),
        "commands_python": sorted(py), "commands_swift": sorted(sw),
        "commands_swift_only": sorted(sw - py),
        "commands_python_only": sorted(py - sw),
        "commands_scan": "ok" if (py and sw) else "incomplete",
        "commands_python_sources": list(CMD_PY),
    }


def build(idx):
    """Full rebuild of every shard into `idx`.  Returns the loaded shards."""
    roles, unresolved = role_values()
    d = parse_all(roles)
    cc, n_commits = cochange()
    cards = {}
    by_module = defaultdict(dict)
    for (m, s), users in d["sym_users"].items():
        by_module[m][s] = users
    for rel in d["paths"]:
        key, card = modkey(rel), {}
        imps = sorted(d["importers"].get(key, ()))
        if imps:
            card["imported_by"] = imps
            card["tests"] = [f for f in imps if f.startswith(TESTS_PREFIX)]
        syms = by_module.get(key, {})
        hot = sorted(((len(v), s) for s, v in syms.items() if len(v) >= 3),
                     reverse=True)[:12]
        if hot:
            card["hot_symbols"] = {s: n for n, s in hot}
        # THE SWEEP-SELECTION EDGES (v2).  ``symbol_tests`` is the per-symbol
        # test attribution --tests-for's clause 1 selects on; it stores only
        # the TEST users, which is what keeps the shard small.
        # ``symbols_attributed`` is the roster of every symbol the index saw
        # imported AT ALL — it is what makes clause 3 possible: a symbol
        # absent from it is one the index CANNOT attribute (dynamic use, a
        # re-export, ``__all__``), and the selector must then fall back wide
        # rather than report "no tests" for it, which reads as safety.
        sym_tests = {s: sorted(f for f in v if f.startswith(TESTS_PREFIX))
                     for s, v in syms.items()}
        sym_tests = {s: v for s, v in sym_tests.items() if v}
        if sym_tests:
            card["symbol_tests"] = sym_tests
        if syms:
            card["symbols_attributed"] = sorted(syms)
        if cc.get(rel):
            card["cochange"] = cc[rel]
        cards[rel] = card
    for rel, v in cc.items():                       # Swift: co-change only
        if rel.endswith(".swift"):
            cards.setdefault(rel, {})["cochange"] = v
    cards.setdefault(SWIFT_CLIENT, {})
    roles_shard = {}
    for value, files in sorted(d["role_lits"].items()):
        hi = sorted(f for f in files if f.startswith(SRC_PREFIX + "auto_patch/")
                    or f in d["uses_ap"])
        roles_shard[value] = {"high": hi, "low": sorted(set(files) - set(hi))}
    flags_shard = {}
    for flag, files in sorted(d["env_reads"].items()):
        defaults = sorted(d["env_defaults"].get(flag, ()))
        flags_shard[flag] = {
            "defaults": defaults, "default_conflict": len(defaults) > 1,
            "files": sorted(files),
            "read_in_tests": any(f.startswith("Ortho4XP/tests/") for f in files)}
    head, dirty = _fingerprint()
    contracts = {"_doc": "tools/artifact_contracts.json MISSING", "rows": []}
    if os.path.exists(CONTRACTS):
        with open(CONTRACTS, encoding="utf-8") as fh:
            contracts = json.load(fh)
    out = {"modules": cards, "roles": roles_shard, "flags": flags_shard,
           "wire": wire_scan(), "artifacts": contracts,
           "meta": {"version": VERSION, "head_sha": head, "dirty_hash": dirty,
                    "scanned": len(d["paths"]), "parse_failures": d["fails"],
                    "role_values": sorted(roles),
                    "role_aliases_unresolved": unresolved,
                    "cochange_commits": n_commits}}
    os.makedirs(idx, exist_ok=True)
    for name in SHARDS:
        with open(os.path.join(idx, name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(out[name], fh, indent=0, sort_keys=True)
    return out


def load(idx):
    out = {}
    for name in SHARDS:
        with open(os.path.join(idx, name + ".json"), encoding="utf-8") as fh:
            out[name] = json.load(fh)
    return out


def ensure_fresh(idx, force=False):
    """Rebuild when HEAD or the dirty set moved.  Prints one line if it did."""
    stale = force or not all(
        os.path.exists(os.path.join(idx, n + ".json")) for n in SHARDS)
    if not stale:
        try:
            with open(os.path.join(idx, "meta.json"), encoding="utf-8") as fh:
                meta = json.load(fh)
            head, dirty = _fingerprint()
            stale = (meta.get("version"), meta.get("head_sha"),
                     meta.get("dirty_hash")) != (VERSION, head, dirty)
        except (ValueError, OSError):
            stale = True
    if stale:
        build(idx)
        print("index rebuilt (forced)" if force else "index rebuilt (stale)")
    return load(idx)


def normalize(arg):
    """(repo-relative path, exists).  Absolute / repo-relative / Ortho4XP-less."""
    arg = arg.rstrip("/")
    for c in (arg, os.path.join(REPO, arg), os.path.join(REPO, "Ortho4XP", arg),
              os.path.join(os.getcwd(), arg)):
        if os.path.exists(c):
            real = os.path.realpath(c)
            return ((os.path.relpath(real, REPO), True)
                    if real.startswith(REPO + os.sep) else (c, True))
    return os.path.normpath(arg), False


def _names(paths, n=10):
    return ", ".join(os.path.basename(p) for p in paths[:n]) + \
        (" ..." if len(paths) > n else "")


def _cc(card):
    return ", ".join("%s(%s)" % (os.path.basename(d["file"]),
                                 "%d%%" % round(d["pct"] * 100) if "pct" in d
                                 else "%dx" % d["n"]) for d in card["cochange"])


def _wire_lines(w):
    out = ["WIRE PROTOCOL (%s <-> %s): %s"
           % (os.path.basename(w["python_source"]),
              os.path.basename(w["swift_consumer"]), w["mechanism"])]
    if w["python_only"] or w["swift_only"]:
        out.append("WIRE DRIFT -- FIX BEFORE SHIP: python_only=%s swift_only=%s"
                   % (w["python_only"] or "[]", w["swift_only"] or "[]"))
    else:
        out.append("  events: verified in sync (%d events)" % len(w["events"]))
    if w["fields_unreferenced_in_swift"]:
        out.append("  fields never referenced by the Swift client (unused OR "
                   "renamed -- check): "
                   + ", ".join(w["fields_unreferenced_in_swift"][:12]))
    if w["commands_scan"] != "ok":
        out.append("  COMMANDS: scan INCOMPLETE (python=%d swift=%d) -- command "
                   "drift is NOT covered" % (len(w["commands_python"]),
                                             len(w["commands_swift"])))
    elif w["commands_swift_only"]:
        out.append("  WIRE DRIFT -- FIX BEFORE SHIP: swift sends commands with "
                   "no python handler: " + ", ".join(w["commands_swift_only"]))
    else:
        out.append("  commands: %d python handlers cover all %d swift call sites"
                   " (python-only, other front ends: %s)"
                   % (len(w["commands_python"]), len(w["commands_swift"]),
                      ", ".join(w["commands_python_only"]) or "none"))
    return out


def _artifact_lines(rel, rows):
    out = []
    for row in rows:
        w, r = row.get("writers", []), row.get("readers", [])
        if rel in w and rel in r and not (set(w) | set(r)) - {rel}:
            out.append("OWNS ARTIFACT (self-coupled cache): " + row["pattern"])
            continue
        if rel in w:
            out.append("WRITES ARTIFACT: %s -- read by %s"
                       % (row["pattern"], _names([x for x in r if x != rel], 6)
                          or "(no other reader recorded)"))
        if rel in r:
            out.append("READS ARTIFACT: %s -- written by %s"
                       % (row["pattern"], _names([x for x in w if x != rel], 6)
                          or "(no other writer recorded)"))
    return out


def render(rel, s):
    """Card lines for one file.  [] means the file is outside index scope."""
    card, out = s["modules"].get(rel), []
    is_wire = rel in (s["wire"].get("python_source"),
                      s["wire"].get("swift_consumer"))
    if rel.endswith(".swift"):                      # R7: no python-only claims
        out.append("swift: co-change + wire coverage only in v1 "
                   "(no python import/test analysis)")
        if card and card.get("cochange"):
            out.append("CO-CHANGED (historical, weak signal): " + _cc(card))
        return out + (_wire_lines(s["wire"]) if is_wire else [])
    if card is None:
        return []
    if card.get("imported_by"):
        v = card["imported_by"]
        src = [f for f in v if f.startswith(SRC_PREFIX)]
        out.append("IMPORTED BY %d files (%d src, %d tests, %d tools): %s"
                   % (len(v), len(src), len(card.get("tests", [])),
                      len([f for f in v if f.startswith("Ortho4XP/tools/")]),
                      _names(src or v)))
    else:
        out.append("indexed (%s): no direct importers recorded"
                   % s["meta"]["head_sha"][:7])
    if card.get("hot_symbols"):
        out.append("HOT SYMBOLS (users): "
                   + ", ".join("%s(%d)" % kv for kv in card["hot_symbols"].items()))
    shown = [t for t in card.get("tests", ())
             if os.path.basename(t) != "conftest.py"]
    if shown:
        out.append("TESTS (direct importers -- may miss dynamic use) (%d): %s"
                   % (len(shown), " ".join(shown[:8])))
    elif card.get("imported_by"):
        out.append("TESTS (direct importers -- may miss dynamic use): none -- "
                   "NOT a claim that the file is untested")
    hi = sorted(k for k, v in s["roles"].items() if rel in v["high"])
    if hi:
        out.append("ROLE LITERALS HERE (%d): %s -- renaming a ROLE_* VALUE in "
                   "auto_patch/layout.py breaks this file silently"
                   % (len(hi), ", ".join(hi)))
    f = s["flags"]
    fl = sorted(k for k, v in f.items() if rel in v["files"])
    if fl:
        out.append("ENV FLAGS READ HERE: %d (%d default-ON, %d read in no test "
                   "file): %s"
                   % (len(fl), len([k for k in fl if f[k]["defaults"] == ["'1'"]]),
                      len([k for k in fl if not f[k]["read_in_tests"]]),
                      ", ".join(fl[:8])))
        out += ["  WARNING: %s has conflicting defaults across read sites: %s"
                % (k, ", ".join(f[k]["defaults"]))
                for k in fl if f[k]["default_conflict"]]
    out += _artifact_lines(rel, s["artifacts"].get("rows", []))
    if card.get("cochange"):
        out.append("CO-CHANGED (historical, weak signal): " + _cc(card))
    return out + (_wire_lines(s["wire"]) if is_wire else [])


def cmd_query(arg, idx):
    s = ensure_fresh(idx)
    rel, exists = normalize(arg)
    if not exists:
        sys.stdout.flush()
        print("ERROR: no such file in repo: %s" % arg, file=sys.stderr)
        return 2
    lines = render(rel, s)
    print("=== %s  [index %s] ===" % (rel, s["meta"]["head_sha"][:7]))
    if not lines:
        print("  not in index scope (%s; only .py under %s is analysed) -- NOT "
              "a safety claim" % (os.path.splitext(rel)[1] or "no suffix",
                                  ", ".join(SCAN_ROOTS)))
    for line in lines:
        print("  " + line)
    return 0


# ══════════════════════════════════════════════════════════════════════
# BS1 — SYMBOL-LEVEL SWEEP SELECTION (--tests-for)
# ══════════════════════════════════════════════════════════════════════
# The four-clause union law is in the module docstring.  Everything here
# obeys one rule: a thing the index cannot attribute widens the selection
# and SAYS SO on stderr.  Narrowing in silence is the failure mode this
# whole tool exists to refuse (a sweep that skips the one failing test is
# indistinguishable from a green run).

def _git_show(ref, rel):
    """File content at ``ref``, or None when it did not exist there."""
    proc = subprocess.run(("git", "show", f"{ref}:{rel}"), cwd=REPO,
                          capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def top_level_symbols(text):
    """``{name: normalised source}`` for every top-level def/class/constant.

    Normalised through :func:`ast.unparse`, following the index's own
    AST-exact idiom: a reformatting or a comment edit is not a symbol
    change, and a renamed argument or a changed default is.  Raises
    ``SyntaxError`` for the caller to turn into a wide fallback.
    """
    out = {}
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            out[node.name] = ast.unparse(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = ast.unparse(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target,
                                                            ast.Name):
            out[node.target.id] = ast.unparse(node)
    return out


def _module_level_source(text):
    """Everything OUTSIDE the top-level named symbols, normalised.

    An edit here (an import, a module-level ``if``, a registry mutation)
    belongs to no symbol, so clause 1 can never see it.  It is reported as
    an unattributable change and widens the selection.
    """
    body = [n for n in ast.parse(text).body
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Assign, ast.AnnAssign))]
    return "\n".join(ast.unparse(n) for n in body)


def changed_symbols(rel, ref="HEAD"):
    """``(symbols, notes)`` for one file: what moved between ``ref`` and the
    working tree.  ``notes`` carries the widening reasons, never a silence.
    """
    notes = []
    after_path = os.path.join(REPO, rel)
    after = _read(rel) if os.path.exists(after_path) else None
    before = _git_show(ref, rel)
    if after is None:
        return set(), ["file DELETED in the working tree"]
    if before is None:
        notes.append(f"file is NEW since {ref} (no before-image)")
        before = ""
    try:
        old, new = top_level_symbols(before), top_level_symbols(after)
        mod_changed = _module_level_source(before) != _module_level_source(after)
    except SyntaxError as exc:
        return set(), [f"UNPARSEABLE ({exc.__class__.__name__}: {exc}) — "
                       f"every symbol treated as changed"]
    syms = {n for n in set(old) | set(new) if old.get(n) != new.get(n)}
    if mod_changed:
        notes.append("MODULE-LEVEL code outside any top-level symbol changed "
                     "(imports, module body) — belongs to no symbol")
    return syms, notes


def diff_files(ref="HEAD"):
    """Changed .py files in index scope: tracked diff vs ``ref`` + untracked."""
    tracked = _git("diff", "--name-only", ref, "--").split()
    untracked = _git("ls-files", "--others", "--exclude-standard").split()
    out = []
    for rel in sorted(set(tracked) | set(untracked)):
        if not rel.endswith(".py") or any(k in "/" + rel for k in SKIP):
            continue
        if rel.startswith(SCAN_ROOTS) or rel.startswith("tools/"):
            out.append(rel)
    return out


def _card_tests(card):
    """The direct-importer test files of a card, conftest excluded (pytest
    loads conftest itself; naming it in a selection is noise)."""
    return [t for t in card.get("tests", ())
            if os.path.basename(t) != "conftest.py"]


def select_tests(changed, shards, ceiling=CHEAP_CEILING, wide_reasons=None):
    """THE SELECTION LAW.  ``changed`` is ``{rel: set(changed symbols)}``.

    ``wide_reasons`` — ``{rel: [why, ...]}`` for files whose change the
    caller already knows it cannot attribute symbol-wise (an unparseable
    file, a module-level edit, a file that did not move at all).  They enter
    clause 3 with the unattributed symbols, by the same law: fall back to
    the file's whole direct-importer test set, and say why.

    Returns a record with the union, each clause's own contribution, the
    fallbacks that fired and the size of the FULL direct-importer sweep the
    selection replaces — every number the header quotes, computed once.
    """
    clauses = {"symbol": set(), "cheap_file": set(), "fallback": set(),
               "changed_test": set()}
    fallbacks, unindexed, full = [], [], set()
    wide_reasons = dict(wide_reasons or {})
    for rel in wide_reasons:
        changed.setdefault(rel, set())
    for rel, syms in sorted(changed.items()):
        if rel.startswith(TESTS_PREFIX) and os.path.basename(rel) \
                != "conftest.py":
            clauses["changed_test"].add(rel)            # clause 4
        card = shards["modules"].get(rel)
        if card is None:
            unindexed.append(rel)
            fallbacks.append(f"{rel}: NOT IN THE INDEX (outside "
                             f"{', '.join(SCAN_ROOTS)}) — no test can be "
                             f"attributed to it; this is not a claim that "
                             f"nothing covers it")
            continue
        tests = set(_card_tests(card))
        full |= tests
        sym_tests = card.get("symbol_tests", {})
        attributed = set(card.get("symbols_attributed", ()))
        for why in wide_reasons.get(rel, ()):            # clause 3, file-wide
            clauses["fallback"] |= tests
            fallbacks.append(f"{rel}: {why} — falling back to all "
                             f"{len(tests)} direct-importer test(s)")
        for sym in sorted(syms):
            if sym in attributed:
                clauses["symbol"] |= {t for t in sym_tests.get(sym, ())
                                      if os.path.basename(t) != "conftest.py"}
            else:                                        # clause 3
                clauses["fallback"] |= tests
                fallbacks.append(
                    f"{rel}: symbol {sym!r} is UNATTRIBUTED by the index "
                    f"(dynamic use, a re-export or __all__) — falling back "
                    f"to all {len(tests)} direct-importer test(s)")
        if len(tests) <= ceiling:                        # clause 2
            clauses["cheap_file"] |= tests
    selected = set().union(*clauses.values())
    return {"selected": sorted(selected),
            "clauses": {k: sorted(v) for k, v in clauses.items()},
            "fallbacks": fallbacks, "unindexed": unindexed,
            "full_sweep": sorted(full), "ceiling": ceiling}


def cmd_tests_for(files, idx, ref="HEAD", ceiling=CHEAP_CEILING):
    """``--tests-for``: the selection, stdout = file list, stderr = header.

    The rebuild notice is redirected to stderr with everything else: this
    command's stdout is a PIPE into pytest, and one "index rebuilt (stale)"
    line in it becomes a pytest argument that does not exist.
    """
    import contextlib
    err = sys.stderr
    with contextlib.redirect_stdout(err):
        s = ensure_fresh(idx)
    if files:
        targets = []
        for arg in files:
            rel, exists = normalize(arg)
            if not exists:
                print(f"ERROR: no such file in repo: {arg}", file=err)
                return 2
            targets.append(rel)
    else:
        targets = diff_files(ref)
        if not targets:
            print(f"# no .py file differs from {ref} — nothing to select",
                  file=err)
            return 0
    changed, wide = {}, {}
    for rel in targets:
        syms, why = changed_symbols(rel, ref)
        changed[rel] = syms
        if not syms and not why:
            why = [f"NO top-level symbol changed vs {ref} (identical, or the "
                   f"edit is formatting/comments only)"]
        if why:
            wide[rel] = why
    result = select_tests(changed, s, ceiling, wide_reasons=wide)
    selected = result["selected"]

    print(f"# blast --tests-for  [index {s['meta']['head_sha'][:7]}] "
          f"vs {ref}", file=err)
    for rel in targets:
        syms = sorted(changed[rel])
        print(f"#   {rel}: {len(syms)} changed symbol(s)"
              + (": " + ", ".join(syms[:12]) + (" ..." if len(syms) > 12 else "")
                 if syms else ""), file=err)
    c = result["clauses"]
    print("#   clauses: symbol-attributed=%d cheap-file(<=%d)=%d "
          "fallback-wide=%d changed-test=%d"
          % (len(c["symbol"]), ceiling, len(c["cheap_file"]),
             len(c["fallback"]), len(c["changed_test"])), file=err)
    for line in result["fallbacks"]:
        print(f"#   FALLBACK {line}", file=err)
    print("#   SELECTED %d test file(s) of the %d-file full direct-importer "
          "sweep" % (len(selected), len(result["full_sweep"])), file=err)
    for path in selected:
        print(path)
    return 0


# ── the mutation-recall twin (--audit --mutations N) ──────────────────
# A selection law can only be believed if something INDEPENDENT of it says
# which tests a change breaks.  That witness is a real mutation and a real
# pytest run: seed one mutation per hot symbol of a sample file, run the
# file's FULL direct-importer sweep against it, and require that every test
# file the sweep reports failing is IN the selection.  Recall is the
# acceptance; precision (selected vs the full sweep) is printed beside it
# because a selector that returns everything is trivially 100 % recalling.

#: The mutation spec the audit hands its pytest child: ``<rel path>::<symbol>``.
MUTATE_ENV = "BLAST_MUTATE"


def pytest_configure(config):                       # pragma: no cover - hook
    """THE MUTATION, applied at RUNTIME — blast.py is its own pytest plugin.

    The obvious implementation (rewrite the symbol's definition on disk, run
    pytest, restore) is unsafe HERE: lanes build concurrently against this
    same working tree, and a build that imports the file inside the mutation
    window measures a tree nobody authored.  Deleting the attribute from the
    imported module instead touches NO file, needs no restore (the child
    process dies with it), and is at least as broad a break: ``from mod
    import sym`` raises ImportError, ``mod.sym`` raises AttributeError, and
    the defining module's own internal uses resolve through the same module
    dict and break too.

    Loaded only when the audit passes ``-p blast`` with :data:`MUTATE_ENV`
    set; blast.py imports with no side effects otherwise.  NOTE: pluggy
    validates EVERY ``pytest_*`` name in a plugin module as a hook, so no
    other function here may carry that prefix (``sweep_failures`` is the
    audit's runner for exactly that reason).
    """
    spec = os.environ.get(MUTATE_ENV)
    if not spec:
        return
    import importlib
    rel, sym = spec.rsplit("::", 1)
    src = os.path.join(REPO, "Ortho4XP", "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    mod = importlib.import_module(modkey(rel))
    if not hasattr(mod, sym):
        raise SystemExit(f"BLAST_MUTATE: {modkey(rel)} has no attribute "
                         f"{sym!r} — the mutation would be a no-op and the "
                         f"recall number meaningless")
    delattr(mod, sym)
    print(f"[blast] MUTATION ACTIVE: {modkey(rel)}.{sym} deleted")


FAIL_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+?)(?:::|\s|$)", re.M)


def sweep_failures(tests, mutation=None):
    """Run ``tests`` (optionally under a mutation) and return the
    repo-relative test FILES that failed.

    ``-o addopts=`` on purpose: the ini's ``-n auto`` would scatter the run
    across xdist workers for no gain on a handful of files, and the audit
    needs the plain short-summary lines it parses.
    """
    cwd = os.path.join(REPO, "Ortho4XP")
    rel = [os.path.relpath(os.path.join(REPO, t), cwd) for t in tests]
    env = dict(os.environ)
    extra = []
    if mutation:
        env[MUTATE_ENV] = "%s::%s" % mutation
        env["PYTHONPATH"] = os.pathsep.join(
            [os.path.join(REPO, "tools")] + ([env["PYTHONPATH"]]
                                             if env.get("PYTHONPATH") else []))
        extra = ["-p", "blast"]
    else:
        env.pop(MUTATE_ENV, None)
    cmd = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "--tb=no",
           "-rfE", "-p", "no:cacheprovider", *extra, *rel]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          env=env)
    out = proc.stdout + proc.stderr
    failed = {os.path.join("Ortho4XP", p) for p in FAIL_RE.findall(out)}
    return failed, proc.returncode, out


def mutation_audit(shards, sample, n, ceiling=CHEAP_CEILING):
    """The twin: N mutations, each judged by a real run of the FULL sweep."""
    card = shards["modules"].get(sample)
    if card is None:
        print(f"  MUTATION AUDIT: {sample} is not in the index — FAIL")
        return ["mutation-sample-unindexed"]
    full = _card_tests(card)
    hot = [s for s in (card.get("hot_symbols") or {})][:n]
    if not full or not hot:
        print(f"  MUTATION AUDIT: {sample} has {len(full)} direct-importer "
              f"test(s) and {len(hot)} hot symbol(s) — nothing to mutate, "
              f"FAIL (pick another --mutation-sample)")
        return ["mutation-sample-empty"]
    bad, signals = [], 0
    print(f"  sample {sample}: {len(full)} test file(s) in the FULL "
          f"direct-importer sweep, mutating {hot}")
    # THE BASELINE, once: a file already red at this tree would otherwise be
    # counted as this mutation's signal, and a selector would be judged on a
    # failure it had no way to predict (the matched-control law).
    base_fail, _rc, _o = sweep_failures(full)
    if base_fail:
        print(f"    baseline (UNMUTATED) already failing, discounted from "
              f"every mutation: {sorted(base_fail)}")
    for sym in hot:
        selected = select_tests({sample: {sym}}, shards, ceiling)["selected"]
        # Clause 1 ALONE (ceiling -1 disables the cheap-file clause).  On a
        # cheap sample the whole law degenerates to "run everything", which
        # would make recall unfalsifiable; this second number says whether
        # the SYMBOL ATTRIBUTION itself predicted the failures, and where it
        # falls short it is exactly what clause 2 exists to cover.
        sym_only = select_tests({sample: {sym}}, shards, -1)["selected"]
        failing, rc, _out = sweep_failures(full, mutation=(sample, sym))
        failing = set(failing) - set(base_fail)
        missed = sorted(set(failing) - set(selected))
        if not failing:
            print(f"    {sym:<28} the full sweep reported NO failing file "
                  f"(pytest rc={rc}) — no signal, not counted")
            continue
        signals += 1
        hit = len(failing & set(selected))
        sym_hit = len(failing & set(sym_only))
        print(f"    {sym:<28} failures {len(failing):3d}  selected "
              f"{len(selected):3d}/{len(full)} (precision "
              f"{hit}/{len(selected)})  LAW recall {hit / len(failing):.2f}"
              f"  symbol-clause-only {sym_hit}/{len(failing)} via "
              f"{len(sym_only)} file(s)"
              + ("" if not missed else f"  MISSED {missed}"))
        if missed:
            bad.append(f"mutation:{sym}")
    if not signals:
        print("  MUTATION AUDIT: no mutation produced a single failing test "
              "— the audit proved NOTHING, FAIL")
        bad.append("mutation-no-signal")
    else:
        print(f"  MUTATION AUDIT: {signals} mutation(s) with signal, recall "
              f"{'1.00 (100%)' if not bad else 'INCOMPLETE'}")
    return bad


GT = (r"(?:from\s+(?:[.\w]*\.)?{s}\s+import"          # from [pkg.]mod import x
      r"|import\s+(?:[.\w]*\.)?{s}\b"                 # import [pkg.]mod
      r"|from\s+[.\w]+\s+import\s+[^\n]*\b{s}\b)")    # from pkg import mod


#: The mutation twin's default sample: a real module with a SMALL full
#: direct-importer sweep, so one audit costs seconds instead of the whole
#: suite.  Override with --mutation-sample.
MUTATION_SAMPLE = SRC_PREFIX + "auto_patch/strip_seam_law.py"


def cmd_audit(idx, mutations=0, mutation_sample=None, ceiling=CHEAP_CEILING):
    s, bad = ensure_fresh(idx, force=True), []
    print("== canaries ==")
    for rel, floor in ((SRC_PREFIX + "auto_patch/layout.py", 120),
                       (SRC_PREFIX + "auto_patch/pavement/strips.py", 1)):
        n = len(s["modules"].get(rel, {}).get("imported_by", []))
        ok = rel in s["modules"] and n >= floor
        print("  %-46s %3d importers (need >=%d)  %s"
              % (rel[len(SRC_PREFIX):], n, floor, "OK" if ok else "FAIL"))
        bad += [] if ok else [rel]
    for c in sorted(ROLE_CANARIES):
        ok = c in s["roles"]
        print("  role literal %-20s %s" % (c, "OK" if ok else "FAIL"))
        bad += [] if ok else ["role:" + c]
    print("== recall sample (15 src modules, AST index vs grep ground truth) ==")
    src = sorted(r for r in s["modules"] if r.startswith(SRC_PREFIX)
                 and r.endswith(".py") and not r.endswith("__init__.py"))
    corpus = {r: _read(r) for r in scan_paths()}
    tot_gt = tot_hit = 0
    for rel in [src[i] for i in range(0, len(src), max(1, len(src) // 15))][:15]:
        key = modkey(rel)
        pat = re.compile(GT.format(s=re.escape(key.split(".")[-1])))
        truth = {r for r, t in corpus.items() if r != rel and pat.search(t)}
        got = set(s["modules"].get(rel, {}).get("imported_by", ()))
        tot_gt, tot_hit = tot_gt + len(truth), tot_hit + len(truth & got)
        r = len(truth & got) / len(truth) if truth else 1.0
        print("  %-52s truth %3d  index %3d  recall %.2f%s"
              % (key, len(truth), len(got), r, "" if r >= 0.9 else "  LOW"))
    recall = tot_hit / tot_gt if tot_gt else 1.0
    print("  OVERALL recall %.3f (%d/%d)  %s"
          % (recall, tot_hit, tot_gt, "OK" if recall >= 0.9 else "FAIL"))
    bad += [] if recall >= 0.9 else ["recall"]
    print("== fail-loud ==")
    rc = cmd_query("no/such/file_xyz.py", idx)
    print("  bogus path exit=%d  %s" % (rc, "OK" if rc == 2 else "FAIL"))
    bad += [] if rc == 2 else ["bogus-exit"]
    drift = any("WIRE DRIFT" in x for x in _wire_lines(
        dict(s["wire"], python_only=["GhostEvent"], swift_only=[])))
    print("  synthetic drift renders  %s" % ("OK" if drift else "FAIL"))
    bad += [] if drift else ["drift"]
    w = s["wire"]
    print("  live wire: %d events, python_only=%s swift_only=%s, commands=%s"
          % (len(w["events"]), w["python_only"] or "[]", w["swift_only"] or "[]",
             w["commands_scan"]))
    if mutations:
        print("== sweep-selection recall (%d seeded mutation(s), judged by a "
              "REAL run of the full direct-importer sweep) ==" % mutations)
        bad += mutation_audit(s, mutation_sample or MUTATION_SAMPLE,
                              mutations, ceiling)
    print("\n" + ("AUDIT PASS" if not bad else "AUDIT FAIL: %s" % bad))
    return 0 if not bad else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="blast-radius index")
    p.add_argument("file", nargs="?")
    p.add_argument("--rebuild", action="store_true")
    p.add_argument("--audit", action="store_true")
    p.add_argument("--index-dir")
    p.add_argument("--tests-for", nargs="*", metavar="FILE",
                   help="print the test files a change to FILE(s) selects "
                        "(no FILE: every .py the diff touched).  stdout is "
                        "the pipeable list; the header goes to stderr")
    p.add_argument("--since", default=None, metavar="REF",
                   help="--tests-for: diff against REF instead of HEAD")
    p.add_argument("--diff", action="store_true",
                   help="--tests-for: the working-tree diff vs HEAD (the "
                        "default; explicit for readable command lines)")
    p.add_argument("--cheap-ceiling", type=int, default=CHEAP_CEILING,
                   help="clause 2's threshold: a changed file with at most "
                        "this many direct-importer tests contributes ALL of "
                        "them (default %d)" % CHEAP_CEILING)
    p.add_argument("--mutations", type=int, default=0, metavar="N",
                   help="--audit: also seed N mutations (one per hot symbol "
                        "of --mutation-sample) and require the selection to "
                        "contain every test file the full sweep fails on")
    p.add_argument("--mutation-sample", default=None, metavar="FILE",
                   help="--audit --mutations: the file to mutate (default "
                        "%s)" % MUTATION_SAMPLE)
    a = p.parse_args(argv)
    idx = index_dir(a.index_dir)
    if a.tests_for is not None:
        return cmd_tests_for(a.tests_for, idx, ref=a.since or "HEAD",
                             ceiling=a.cheap_ceiling)
    if a.audit:
        return cmd_audit(idx, mutations=a.mutations,
                         mutation_sample=a.mutation_sample,
                         ceiling=a.cheap_ceiling)
    if a.rebuild:
        ensure_fresh(idx, force=True)
        return 0
    if not a.file:
        p.print_help()
        return 2
    return cmd_query(a.file, idx)


if __name__ == "__main__":
    sys.exit(main())
