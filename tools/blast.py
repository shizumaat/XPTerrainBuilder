#!/usr/bin/env python3
"""Blast-radius index for XPTerrainBuilder: what else moves when a file moves.

    Ortho4XP/venv/bin/python tools/blast.py <file>   # print the blast card
    tools/blast.py --rebuild                         # force a rebuild
    tools/blast.py --audit                           # recall audit + canaries

Design rule: the index must fail LOUD ("not indexed", "stale", "low
confidence"), never fail PLAUSIBLE.  Absence of data is never rendered as a
safety claim.  Import lines are AST-exact; co-change is a weak historical
signal and is labelled as such.  Importable without side effects.
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

VERSION = "1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_ROOTS = ("Ortho4XP/src", "Ortho4XP/tools", "Ortho4XP/tests")
SRC_PREFIX = "Ortho4XP/src/"
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
    for rel in d["paths"]:
        key, card = modkey(rel), {}
        imps = sorted(d["importers"].get(key, ()))
        if imps:
            card["imported_by"] = imps
            card["tests"] = [f for f in imps if f.startswith("Ortho4XP/tests/")]
        hot = sorted(((len(v), s) for (m, s), v in d["sym_users"].items()
                      if m == key and len(v) >= 3), reverse=True)[:12]
        if hot:
            card["hot_symbols"] = {s: n for n, s in hot}
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


GT = (r"(?:from\s+(?:[.\w]*\.)?{s}\s+import"          # from [pkg.]mod import x
      r"|import\s+(?:[.\w]*\.)?{s}\b"                 # import [pkg.]mod
      r"|from\s+[.\w]+\s+import\s+[^\n]*\b{s}\b)")    # from pkg import mod


def cmd_audit(idx):
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
    print("\n" + ("AUDIT PASS" if not bad else "AUDIT FAIL: %s" % bad))
    return 0 if not bad else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="blast-radius index")
    p.add_argument("file", nargs="?")
    p.add_argument("--rebuild", action="store_true")
    p.add_argument("--audit", action="store_true")
    p.add_argument("--index-dir")
    a = p.parse_args(argv)
    idx = index_dir(a.index_dir)
    if a.audit:
        return cmd_audit(idx)
    if a.rebuild:
        ensure_fresh(idx, force=True)
        return 0
    if not a.file:
        p.print_help()
        return 2
    return cmd_query(a.file, idx)


if __name__ == "__main__":
    sys.exit(main())
