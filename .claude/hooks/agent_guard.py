#!/usr/bin/env python3
"""PreToolUse guard for Agent/Task launches. Owner standing rule
(2026-07-30, memory: agents-run-on-opus): every Agent launch passes an
explicit model — Opus implements, Fable is design/review only. Inheriting
the session model silently puts a Fable-class model on implementation."""
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

model = (data.get("tool_input") or {}).get("model")
if not model:
    print(
        "BLOCKED (owner standing rule): every Agent launch must pass an "
        "explicit `model` — 'opus' for implementation/mechanical work, "
        "'fable' only for design or review briefs. Never inherit the "
        "session model. Re-issue the Agent call with model set.",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
