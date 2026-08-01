#!/usr/bin/env python3
"""PreToolUse guard for Bash. Blocks the four command classes that have
historically produced destroyed work or corrupted evidence in this repo.

Exit 2 + stderr = deny (message is fed back to the model). Exit 0 = allow.
Every check is cheap; the pgrep only runs when a timing command matches.
"""
import json
import os
import re
import subprocess
import sys


def deny(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # malformed input: never wedge the session

cmd = (data.get("tool_input") or {}).get("command") or ""
cwd = data.get("cwd") or os.getcwd()

# Pattern checks run against the command with quoted strings blanked, so
# prose that merely MENTIONS a guarded pattern (commit messages, echo text,
# grep patterns) cannot false-positive. Sentinel and `cd` extraction use the
# original string.
scan = re.sub(r"'[^']*'", "''", cmd)
scan = re.sub(r'"[^"]*"', '""', scan)

# --- 1. Shared stash stack (concurrent sessions share it; a wrong pop
#        destroys another session's work). ---------------------------------
if re.search(r"\bgit\b[^\n;|&]*\bstash\b\s+(pop|drop|clear)\b", scan) and \
        "O4_STASH_OK=1" not in cmd:
    deny(
        "BLOCKED (shared stash stack): concurrent sessions share this repo's "
        "stash. Inspect provenance first — `git stash list` then "
        "`git stash show -p stash@{0}` — and confirm the entry is from THIS "
        "session. If it is, re-run the exact command prefixed with "
        "O4_STASH_OK=1 (the prefix is the audit trail that inspection "
        "happened). Never chain stash -> long run -> pop in one call."
    )

# --- 2. Broken pip shim. ---------------------------------------------------
if re.search(r"venv/bin/pip\b", scan):
    deny(
        "BLOCKED: venv/bin/pip is broken in this repo. Use "
        "`venv/bin/python -m pip ...` instead."
    )

# --- 3. Fake-layout trap: engine builds/tests outside a dir with venv/ AND
#        OSM_data/ exit 0 with a silently smaller layout. -------------------
if re.search(r"(build_airport_pavement|Ortho4XP\.py|check_build_time\.py"
             r"|test_pavement_grade|-m\s+pytest)", scan):
    cds = list(re.finditer(r"(?:^|[;&|]\s*)cd\s+([^\s;&|]+)", cmd))
    target = cds[-1].group(1).strip("'\"") if cds else cwd
    target = os.path.expanduser(target)
    if not os.path.isabs(target):
        target = os.path.normpath(os.path.join(cwd, target))
    missing = [d for d in ("venv", "OSM_data")
               if not os.path.isdir(os.path.join(target, d))]
    if missing:
        deny(
            f"BLOCKED (fake-layout trap): engine build/test but effective cwd "
            f"'{target}' lacks {' and '.join(missing)}. Builds exit 0 with a "
            f"silently smaller layout from the wrong cwd — run from "
            f"Ortho4XP/ in the main tree, or symlink venv/ and OSM_data/ "
            f"into the worktree (never git-add the symlinks)."
        )

# --- 4. Timing purity: anything whose OUTPUT IS A TIME must run exclusively
#        and never inside the run ledger. ----------------------------------
is_timing = (("check_build_time" in scan and "--run" in scan)
             or "py-spy" in scan or "cProfile" in scan)
if is_timing:
    if "run_with_ledger" in scan:
        deny(
            "BLOCKED: never wrap wall-time benchmarks in run_with_ledger.py — "
            "timing must be measured fresh, a ledger replay would report a "
            "stale number as a measurement."
        )
    try:
        out = subprocess.run(
            ["pgrep", "-fl", r"Ortho4XP\.py|build_airport_pavement|pytest"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        out = ""
    if out:
        deny(
            "BLOCKED (timing contamination): another build/test is live and "
            "would contaminate the measurement (noise floor is already "
            "±25%). Owner ruling 2026-07-31: only runs whose output is a "
            "time are exclusive. Wait for these, or coordinate:\n" + out
        )

sys.exit(0)
