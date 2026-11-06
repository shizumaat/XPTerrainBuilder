#!/usr/bin/env python3
"""Master session age guard (owner 2026-11-06T15:01Z "Yes, go ahead").

The 2026-11-04 master ran two days through several compactions and began
dropping steps (stale engine, unsigned app, an unmerged branch, a stalled
lane). Rule: a fresh master each day (efficiency rules 2026-11-03 #5);
the project coordinator starts it when the master posts "handoff ready".

UserPromptSubmit: after WARN_H hours, or once the session was compacted,
  every turn opens with the instruction to write the handoff.
PreToolUse (Agent, Bash app builds): past BLOCK_H hours, refused.
Subagent transcripts (lanes) are not checked.
"""
import json
import os
import sys
import time

WARN_H, BLOCK_H = 20, 24
BUILD_WORDS = ("make_app.sh", "make_engine.sh", "build_test_app.sh")

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
path = data.get("transcript_path") or ""
if not path or "/subagents/" in path or not os.path.exists(path):
    sys.exit(0)


def first_and_compacted(p):
    first, compacted = None, False
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if first is None and '"timestamp"' in line:
                try:
                    ts = json.loads(line).get("timestamp")
                    if ts:
                        parsed = time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
                        first = time.mktime(parsed) - time.timezone
                except Exception:
                    pass
            if '"isCompactSummary":true' in line.replace(" ", ""):
                compacted = True
                break
    return first, compacted


start, compacted = first_and_compacted(path)
if start is None:
    sys.exit(0)
age_h = (time.time() - start) / 3600.0
event = data.get("hook_event_name")
msg = (f"MASTER SESSION EXPIRED ({age_h:.0f} h old{', compacted' if compacted else ''}): "
       "update memory handoff-<date>-master.md, post it in the thread with "
       "\"handoff ready\" so the coordinator starts a fresh master, and start no new work.")

if event == "UserPromptSubmit":
    if age_h >= WARN_H or compacted:
        print(msg)
    sys.exit(0)

if event == "PreToolUse" and age_h >= BLOCK_H:
    tool = data.get("tool_name")
    cmd = (data.get("tool_input") or {}).get("command", "")
    if tool in ("Agent", "Task") or (tool == "Bash" and any(w in cmd for w in BUILD_WORDS)):
        print("REFUSED: " + msg, file=sys.stderr)
        sys.exit(2)
sys.exit(0)
