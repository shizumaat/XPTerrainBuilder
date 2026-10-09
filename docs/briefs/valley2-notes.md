# valley2 notes — implementing spec §61 (taxiway edge takes its centreline's level)

Lane `valley2`, branch `claude/valley2`, based on main `3a64a153`. Ruling 2026-10-09e.

## Step 0 — setup
- §61 was FREE on main (last section §60), so no renumbering: appended verbatim from
  `origin/claude/valleyspec` 51313c41 (297 lines).
- Brought `docs/briefs/valleyspec-{notes,summary}.md`, `valleyspec-scratch/`,
  `flatvalley-notes.md`, `flatvalley-scratch/` (design record, probe arms; no engine code).
- NOT brought: that branch's 14 `docs/frames.jsonl` rows (captures taken on older main
  `e2eec15c`; this lane re-takes controls on main).
