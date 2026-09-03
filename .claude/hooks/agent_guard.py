#!/usr/bin/env python3
"""PreToolUse guard for Agent/Task launches.

Owner standing rule, 2026-09-03 (supersedes the 2026-07-30 "Opus
implements" rule; memory: agents-run-on-opus): every subagent runs on
Fable 5.1 at MODERATE effort, orchestrated by the Fable 5.1 high-effort
session acting as project manager.  So every Agent launch must pass
`model: "fable"` explicitly — inheriting the session model would put
the orchestrator's HIGH effort on a lane, and any other model is the
retired rule.  Effort is pinned by the project agent definition
`.claude/agents/lane.md`; prefer `subagent_type: "lane"` for
implementation briefs so the effort pin applies.
"""
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = data.get("tool_input") or {}
model = tool_input.get("model")
if not model:
    print(
        "BLOCKED (owner standing rule 2026-09-03): every Agent launch must "
        "pass `model: \"fable\"` explicitly — subagents are Fable 5.1 at "
        "moderate effort (project definition `lane` pins the effort), never "
        "the inherited session model. Re-issue with model set.",
        file=sys.stderr,
    )
    sys.exit(2)
if model != "fable":
    print(
        f"BLOCKED (owner standing rule 2026-09-03): model '{model}' is the "
        "retired rule. Subagents run on Fable 5.1 at moderate effort: pass "
        "`model: \"fable\"` (and `subagent_type: \"lane\"` for "
        "implementation briefs).",
        file=sys.stderr,
    )
    sys.exit(2)

ALLOWED_TYPES = {"lane", "scout", "claude-code-guide"}
subagent_type = tool_input.get("subagent_type") or "general-purpose"
if subagent_type not in ALLOWED_TYPES:
    print(
        f"BLOCKED (owner standing rule 2026-09-03): subagent_type "
        f"'{subagent_type}' does not carry the moderate-effort pin. Use "
        "`lane` (implementation, all tools) or `scout` (read-only "
        "research) from .claude/agents/ — both are Fable 5.1 at effort "
        "medium; built-in types inherit the session's HIGH effort.",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
