# #879: the object stage after the mesh reuses its work when its inputs did not change

Branch `claude/project-thread-g7d6rw-879`, worktree `/home/user/wt-879`. Read issue #879 whole
(`Ortho4XP/src/O4_Mesh_Utils._auto_patch_post_mesh_rebake` ~2373 →
`src/auto_patch/object_stage.rebake_after_mesh` ~721 → auto_patch_v2's rebake). Owner approved
the work 2026-10-19.

Scope of THIS landing (conservative, correct first; the finer key is measurement-gated):
- Reuse PER AIRPORT. Key = the airport's rebake plan (`o4_v2_rebake_<ICAO>.json`) content
  digest + the digest of the mesh content the stage READS for that airport + the pack object
  sources (OBJ digests) + the stage's own code closure (a `CODE_MODULES` tuple held by a closure
  twin, the `partition_code` / `stage_code` pattern, never a hand-bumped version) + the
  environment fingerprint (`auto_patch_v2.pipeline.xplat.environment()`), if available here.
- The read set: issue #660 says a graded face at one site can regroup bodies 800 m away. Do NOT
  assume "under the footprint". Find the stage's actual mesh read (trace the code); if the read
  is the whole tile mesh or cannot be bounded statically, key on the WHOLE mesh content digest
  for this landing and say so — reuse then pays on re-runs and on development iterations that
  leave the mesh unchanged, which is the owner's ask. A narrower read set is a follow-up gated on
  the corpus measurement.
- Pristine-input rule (`src/auto_patch/provenance.py` ~692-703) and witness-on-read stay: a reused
  result is re-checked against the mesh it is applied to (a cheap witness: the stored mesh digest
  equals the mesh on disk now; a stored output re-hashes to its sha).
- Store beside the existing caches with the same discipline as
  `auto_patch_v2/airport/stage_cache.py` (temp + `os.replace`, refused never repaired); reuse that
  store if it fits rather than writing a new one (`blast.py --find cache store`).
- An off switch through the existing env-classification pattern (`O4_*`, classified in
  `provenance_env`; `test_patch_env_classification`).
- Report lines: per airport `reused` / `ran: <first differing input>`, and the stage's wall time,
  so the master's measurement reads it from the log.
- Twins (synthetic, no corpus): unchanged inputs → reused and byte-identical to a fresh run;
  each key input changed → re-runs; mesh on disk changed after write → refused; closure twin.
Not in scope: the patch freshness gate (#880, another lane), the v2 stage cache files
(`pipeline/*_records.py`, `back_cache.py`, `front_cache.py`, `stage_code.py` — another lane is
editing them; do not touch).
Gate (master, corpus): measure the stage's share of a rebuild at OTHH or HECA and one small
airport, cold vs reused, and byte-identity of the tile's DSF/objects between the two.
