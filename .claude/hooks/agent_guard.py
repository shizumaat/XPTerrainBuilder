#!/usr/bin/env python3
"""PreToolUse guard for Agent/Task launches.

Owner standing rule 2026-10-13 (root CLAUDE.md "Lanes", RULINGS 13c;
memory: agents-run-on-opus): every subagent runs on OPUS (effort set per task
at launch, owner ruling 2026-10-20), model passed explicitly, through the
project definitions `lane` / `scout`.  Fable 5.1 is launched only after the
owner approved that launch
in chat; the prompt then carries `OWNER-APPROVED-FABLE: <date> "<words>"`
and this guard refuses a Fable launch without it.  Precedent: nine Fable
implementation lanes used half the weekly Fable allowance in a day.
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
        "BLOCKED (owner standing rule 2026-10-13): every Agent launch must "
        "pass `model: \"opus\"` explicitly — subagents are Opus, effort set per "
        "task at launch (definitions default to medium), never the "
        "inherited session model. Re-issue with model set.",
        file=sys.stderr,
    )
    sys.exit(2)
if model not in ("fable", "opus"):
    # Owner amendment 2026-09-03 EVENING (root CLAUDE.md "Lanes", "Fable
    # limits are finite"): lanes and scouts run on OPUS by default; Fable
    # 5.1 is reserved for briefs where the judgement is the deliverable.
    # Both pass explicitly; anything else is refused.  Applied 2026-09-08
    # when the Fable limit stopped two lanes mid-round.
    print(
        f"BLOCKED (owner standing rule 2026-09-03, amended that evening): model "
        f"'{model}' is not a lane model. Subagents run on Opus by default "
        "(`model: \"opus\"`) or Fable 5.1 for judgement briefs (`model: "
        "\"fable\"`), always explicit, with `subagent_type: \"lane\"` / "
        "\"scout\".",
        file=sys.stderr,
    )
    sys.exit(2)

if model == "fable" and "OWNER-APPROVED-FABLE:" not in (tool_input.get("prompt") or ""):
    print(
        "BLOCKED (owner standing rule 2026-10-13, RULINGS 13c): a Fable launch "
        "needs the owner's approval of THIS launch in chat. Launch it on "
        "`model: \"opus\"` — specs, audits and review included. If Opus is "
        "truly not enough, ask the owner (name the brief, say why, quote "
        "get_usage Weekly Fable) and, on a yes, put the line "
        "`OWNER-APPROVED-FABLE: <date> \"<the owner's words>\"` in the prompt. "
        "Never write that line without the owner's yes.",
        file=sys.stderr,
    )
    sys.exit(2)

ALLOWED_TYPES = {"lane", "scout", "claude-code-guide"}
subagent_type = tool_input.get("subagent_type") or "general-purpose"
if subagent_type not in ALLOWED_TYPES:
    print(
        f"BLOCKED (owner standing rule 2026-09-03): subagent_type "
        f"'{subagent_type}' is not a project lane definition. Use "
        "`lane` (implementation, all tools) or `scout` (read-only "
        "research) from .claude/agents/ — both are Opus (default effort "
        "medium, set per task at launch); built-in types inherit the session's HIGH effort.",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
