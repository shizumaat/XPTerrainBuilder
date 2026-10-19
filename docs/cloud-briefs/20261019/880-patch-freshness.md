# #880: the airport patch freshness gate keys each airport on its own inputs and its code closure

Branch `claude/project-thread-g7d6rw-880`, worktree `/home/user/wt-880`, stacked on the #843
back half (`claude/project-thread-g7d6rw-843-backhalf`, PR #979, not yet merged). Read issue
#880 whole, #346 (why the gate is whole-tree), `common.md` here, `Ortho4XP/CLAUDE.md`,
`src/auto_patch/CLAUDE.md`, and RULINGS 18b-18g. Owner approved the work 2026-10-19; the owner
still confirms the trade (narrowing #346's whole-tree gate) before it lands, so the PR waits on
that, not the code.

Today: `src/auto_patch/driver.py` ~448-516 keys every patch on ONE digest over every
`.py`/`.toml` under `src` (`src/auto_patch/provenance_code.py` ~10-16).

Do:
- Replace the whole-tree digest in the patch freshness key with the CODE CLOSURE of the patch
  build: every module the airport patch path imports (driver → v2 build → every stage), computed
  with the existing machinery (`O4_Code_Closure`, `stage_code`, `partition_code`,
  `object_stage_code` on PR #984 — `blast.py --find closure`; extend, never fork). Frozen into
  both `.spec` files like the other closure digests. Held by a closure twin that fails when the
  patch path imports a module the closure omits (the `test_stage_code_closure` pattern). Data
  files the code reads (`.toml` law tables etc.) stay in the key: either in the closure or by
  their own digest — whichever the existing key already carries; do not drop one.
- Per-airport inputs: keep (or add, if missing) apt.dat row, pack and DSF dump, OSM, DEM and
  insets via the witnesses #843 uses, the law rows / whole-law digest, ruleset. Report which were
  already in the key.
- Development reuse: when the patch is stale because of a stage-local change, the rebuild goes
  through the #843 stage cache (it already does on this branch — confirm, do not re-implement).
- Twins (synthetic): a change to a module outside the closure (e.g. a Qt/UI file) keeps the patch
  fresh; a change to a module inside it stales it; a change to an input stales only that airport;
  the closure twin. A cold-vs-reuse byte-identity twin if the synthetic fixtures allow one.
- Off switch: `O4_PATCH_FRESHNESS_WHOLE_TREE=1` restores the #346 whole-tree key (classified in
  `provenance_env`), so the owner's trade is reversible without a revert.
Not in scope: the object stage (#879, PR #984), the back-half record files (#979).
Gate (master, corpus): one airport, edit a UI file, rebuild — patch reused; edit a stage file —
patch rebuilt, byte-identical to cold.
