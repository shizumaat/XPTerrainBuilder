# roadramp2 — lane notes (issue #484, PR #487 follow-up; RULINGS 2026-10-09d (2))

Branch `claude/roadramp2`, from `claude/roadramp484` @ `2676e011` + `origin/main` @ `729e140d`
+ `claude/rampreview` @ `baf03e31` (docs only). Scratch `<scratch>/roadramp2/`.

## Step 1 — setup, spec to one copy (F3b)

* Merged main (one conflict, `docs/frames.jsonl`, append-only: union of both sides) and the
  review branch (spec + `docs/briefs/rampreview-summary.md`).
* F3b: the stale second copy of §38–§41 (with §37 (6)–(9)), 1,634 lines from the review's
  HTML marker to before `## §42`, DELETED. `grep -c '^## §38 THE TILE SEAM'` = 1; the surviving
  copy carries "AIRSIDE IS KING — ROUND 2". The deleted copy was the round-1 snapshot (its
  "AIRSIDE MOTION — REPORTED" block and `v2roadcontactHECA2` closing build are superseded by
  round 2 in the canonical copy). No other file referenced the second copy by line.
