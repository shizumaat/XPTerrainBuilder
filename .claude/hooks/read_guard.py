#!/usr/bin/env python3
"""PreToolUse guard for Read. Ortho4XP/STATUS.md is ~90k tokens of append-only
history; only the TOP dated block is current. Block whole-file reads."""
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

ti = data.get("tool_input") or {}
fp = (ti.get("file_path") or "").rstrip("/")

if fp.endswith("/STATUS.md") and "Ortho4XP" in fp:
    if not ti.get("limit") and not ti.get("offset"):
        print(
            "BLOCKED: Ortho4XP/STATUS.md is ~90k tokens; only the TOP dated "
            "block is current, the rest is history. Re-read with a limit "
            "(e.g. limit=120). Use offset+limit only when a specific "
            "historical block is needed.",
            file=sys.stderr,
        )
        sys.exit(2)

sys.exit(0)
