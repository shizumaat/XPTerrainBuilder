# Lane-local mask routing (Fable spec, 2026-08-12b)

Owner ruling (RULINGS.md 2026-08-12b): lane mask writes land lane-local.
Precedent implementations to FOLLOW, not fork: the suite's env-overridden
cache roots (`O4_DSF_CACHE_DIR`, `O4_AIRPORT_MOD_CACHE_DIR` — env read at
call time inside the path resolution, so module reloads and
`set_data_root` cannot un-redirect) and #15's copy-on-write overlay
(`shared_repo_guard.mirror_tree_as_overlay`, clonefile + copy fallback,
NO symlinks — symlinked entries are the truncate-through defect #15
killed).

Trigger: HECA lane tile arm refused rc=1 — `O4_Mask_Utils.py:427-434`
legacy-mask cleanup `os.remove`s 16 shared `Masks/+30+030/+30+031/*.png`
under a bare `except: pass`; the guard blocked all 16 and the harness
flagged the swallowed refusal. Every lane tile build on a warm tile
refuses this way.

## Requirements

1. **Env-overridable masks root** (`O4_MASKS_DIR`), resolved AT CALL TIME
   in the engine's mask path resolution (one resolution point; find the
   masks-dir accessor and thread every mask read/write/delete through
   it — a call site that bypasses the accessor is the defect class).
2. **Harness arming**: `build_airport.py`'s engine-cache redirection
   (`redirect_engine_caches`) adds the masks root: overlay dir seeded
   copy-on-write from the shared `Masks/` subtree for the tile(s) in
   scope via `mirror_tree_as_overlay` (quote cloned/copied counts in the
   build log line, same as the mod cache). Warm reads stay warm; writes
   and the legacy cleanup land on lane-local clones.
3. **The swallow site surfaces**: the `except: pass` at
   `O4_Mask_Utils.py:427-434` narrows to the expected class
   (FileNotFoundError) and logs anything else — with redirection armed
   it should never fire on a guard refusal again, but a swallowed
   refusal must never again read as a clean stage.
4. **Guard stays as backstop** — no allowance added for mask deletes on
   the shared root.

## Twins (extend the existing guard/redirect test families in
## tests/test_harness.py — no new file)

- Redirect honored after module reload (the env-at-call-time property).
- Legacy cleanup under redirection deletes ONLY lane-local clones;
  shared files untouched (assert on a tmp_path fixture pair).
- Overlay seeding reports clonefile/copy counts; NO symlink mode exists
  for masks (source-text assertion, same idiom as
  test_the_overlay_seeding_offers_NO_symlink_mode).
- The narrowed except: an injected non-FileNotFoundError surfaces in the
  log.

## Acceptance

- Unit twins green, once, ledgered.
- ONE lane tile-arm smoke: re-run the refused HECA tile arm shape
  (steps 1-3 suffice — `run_tile_mesh_only`-class or the 4-step with
  early stop if available; the point is step 3 completing with rc=0,
  legacy cleanup landing lane-local, shared repo UNCHANGED, and the
  guard reporting zero blocked writes). Quote the mask overlay seed
  counts and the step-3 wall time (it was 1.6 s bailed; a real masks
  stage will cost more — that is the feature, note it).
- Build-time impact statement (overlay seeding cost expected ~0.1 s per
  the #15 measurement; quote it).

Convergence guards as standard (materiality n/a — this is
infrastructure; attempt cap 2; heartbeat; shared repo UNCHANGED; commit
on the lane branch; no merge; STOP-and-report on any deviation).

## Out of scope

Mask ALGORITHM changes; the data-vs-product status of masks in the
corpus (owner question, unchanged); redirecting the app's own production
builds (they legitimately write the shared corpus).
