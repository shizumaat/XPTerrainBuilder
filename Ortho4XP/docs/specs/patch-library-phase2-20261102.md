# Patch library, phase 2 — airport entries (#1699)

Status: IMPLEMENTED 2026-11-02 (lane `plib2`, branch `claude/plib2-airport-entries`).
Design: "Patch library: design and plan" (owner, final 2026-11-02), phase 2.
Owner answers that apply: Q303 (pack-relative encoding for community payware
entries; verified developers exempt), Q304 (ODbL 1.0), Q319 (2026-11-03, "a":
per-source terms; a non-commercial source publishes and marks the whole entry
non-commercial; Northern Ireland and registration-required sources stay held), Q315 (2026-11-02T23:40Z,
"For 301, option a.": `road_level` is matched, not refused), and the 2026-11-02
replacements of #1699 decisions 4 and 6 (everyone publishes into one library
on GitHub; publishing needs a GitHub account, downloading never does; we host
no service).

## 1. What phase 2 delivers

publish → find → apply → fallback, against a library that is ONE public GitHub
repository (skeleton: `library_template/`):

| Piece | Engine | Mac app | Qt window |
|---|---|---|---|
| The check when the app opens | `library_check` (`patch_library.scan.check`) | Library view, "Patch library" section, run once at launch | Library dialog, "Patch library" box, run when it opens |
| Download + lay down (Build / Update) | `library_apply` | row button | row button |
| Ignore | `library_ignore` | row button | row button |
| Match list in the build box | `library_matches` | Airports card, "Library patches" rows | Airports card, "Library patches" label |
| Publish patch (preview, licence, sign-in, PR) | `library_publish_preview`, `library_signin_start` / `_poll`, `library_publish`, `library_signout` | Library view, tile row ▸ "Publish Patch…" sheet | Library dialog, "Publish Patch…" button |
| The library's checks and index | `patch_library.checks`, `patch_library.index` (stdlib only) | — | — |
| Reuse gate | `auto_patch.driver._auto_patch_is_current` input 0 (`patch_library.adoption.verdict`) | — | — |

## 2. Consumer census — every file an airport entry carries

The entry carries the airport's PATCH FAMILY (`O4_Unpatched_Airports.
airport_patch_family`, the one list of per-airport files) and the user's edits.
Each row names who reads the file on the RECEIVING machine.

| File | Written by | Read by (receiver) | Carried |
|---|---|---|---|
| `<ICAO>_auto.patch.osm` | vector step (driver → v2 emit) | the reuse gate (head stamps), `include_patches` (vector step), the vector step's reuse record (`O4_Step_Reuse._patch_inputs`), the patch editor | yes; head stamps tokenised, body untouched (`rebake_screen.patch_body_sha256` stays valid) |
| `<ICAO>_auto.patch.osm.axes.json` | v2 emit | **the vector/mesh step**: `O4_Vector_Map.road_bridge_deck_pins` and `road_join_yield_pins` (deck pins, join yields); the driver's manifest check; the patch editor | **yes — not optional**: the design called it optional ("the app can rebuild it"), but the mesh reads it, and rebuilding it is a re-solve |
| `<ICAO>.graded.json` | v2 emit | the object stage (`placement_boxes`, `placement_read`, `object_stage_reuse` recipe digest) | yes |
| `o4_v2_rebake_<ICAO>.json` | object stage | the object stage (the plan); the reuse gate's input 8 (`object_plan.unservable`: a screen with no plan and no partition cache rebuilds) | yes, when present; pack paths tokenised, a renamed pack folder renamed on the way in |
| `o4_v2_rebake_<ICAO>.screen.json` | v2 emit | object stage, `object_plan.unservable` | yes |
| `o4_v2_rebake_<ICAO>~<k>.json` (companion plans) | object stage | object stage | yes |
| `o4_v2_rebake_<ICAO>.screen.refused` | object stage (a LOCAL refusal) | `object_plan.unservable` | **no** — it is the publisher's machine's verdict; apply removes a stale one |
| `o4_object_anchor_worklist.json` | driver, per tile | object stage | no — tile-wide; the receiver's driver writes its own (computed before the reuse gate) |
| `<ICAO>_edited.patch.osm` | patch editor | `include_patches` (a manual patch replaces the auto patch) | yes, as the entry's edits (`edits/`); laid down only where the user has none (#1699 decision 8) |
| `auto_patch_verify_debug.log` | v2 | nobody | no |

New file on the receiver: `o4_library_<ICAO>.json` (the adoption record,
`patch_library.adoption`), read only by the reuse gate and the app-open check.
It is not a `*.patch.osm` and not a folder, so `include_patches` and
`manual_patch_icaos_in` never see it.

## 3. The match key

An entry is used AS SOLVED only when all three match; otherwise the airport is
solved locally (the fallback). `patch_library.key.first_difference` names the
first difference in the user's words.

1. **Pack signature** — `auto_patch_v2.airport.pack_identity.pack_signature`,
   the one derivation (moved out of `tile_bundle.key`, which now re-exports it):
   apt.dat block hash, the pristine (`.anchor_bak`) tile DSF hash(es), the
   borrowed Global Airports block, `1302 flatten`. Cached by size and mtime of
   every file it read (`<data>/Library/signatures.json`).
2. **Auto-patch law** — `o4_fresh_v`, `o4_cfg` (the configuration digest taken
   without the two cache-location variables, `provenance_env.
   without_cache_locations`, which name a machine), `o4_code`, `o4_ap_engine`.
   A newer engine (another code digest) re-solves (design "Engine versions").
3. **Solve settings** — `o4_solve_cfg` (`road_grade_limit`, `lane_width`).
   `road_level` is NOT in an airport entry's key: the solve does not read it
   (no stamp carries it; it shapes the mesh). Q315 applies to the TILE BUNDLE
   key: `tile_bundle.key.MATCHED_NOT_REFUSED = ("road_level",)` — still in the
   mesh-profile digest (matched), no longer a reason to refuse an export.

Not matched (the publisher's data snapshot, which an entry exists to spare the
receiver): `o4_dem`, `o4_osm`, `o4_cifp`, `o4_imagery`, `o4_tools`. A publish
REFUSES a patch any other stamp of which is stale on the publisher's machine
(`driver.auto_patch_stale_inputs`), so the law and signature recorded are the
ones that solved it. `min_engine` is the publisher's engine version; an older
app warns (decision 11).

## 4. The reuse gate (receiver)

`_auto_patch_is_current` asks `adoption.verdict` first. `None` (no record, or
the patch is no longer the file apply laid down — a local rebuild rewrote it)
→ the normal stamp gate. `(True, "")` → inputs 1–7 are skipped ("library patch
matches your pack and engine — solve skipped") and input 8 (object plan
servable) still runs. `(False, why)` → rebuild, reason `o4_library`. The gate
module chain (`patch_library.adoption`, `patch_library.key`,
`auto_patch_v2.airport.pack_identity`) is in the patch build's import closure
and keyed in `provenance_code.PATCH_CODE_MODULES` and `O4_Step_Code`; the rest
of `patch_library` is not.

## 5. The library repository

`library_template/` (the master creates the real repository from it):
`entries/<ICAO>/<pack slug>/<signature[:12]>/v<N>/` (the design's
`<ICAO>/<pack>/<pack version>/`, under one `entries/` folder) with
`manifest.json`, `edits.json`, `ATTRIBUTION.txt`, `solved/*.xz`, `edits/*.xz`;
`index/<region>.json` per 10° region; `publishers.json` (verified developers,
pack name patterns, reviewers); `licences.json` (the licence gate, `patch_library.terms`:
`allowed` / `noncommercial` / `held`, each row with licence, attribution,
terms URL, evidence and summary — every row to be confirmed);
`schema/manifest.schema.json`; `.github/workflows/check.yml`
(`pull_request_target`, the head checked out as DATA, the checker a sparse
checkout of this repository's `Ortho4XP/src/patch_library`; verified
developer's own pack + all checks pass → `gh pr merge`, else label
`needs-review`) and `index.yml` (rebuild on merge). `checks.py`, `index.py`,
`layout.py` and the package `__init__` are stdlib-only (twin).

The checks (`patch_library.checks`): layout and names; manifest schema and
agreement with its folder; sha256 and size of every file and of its
decompressed content; caps (50 MB a file, 100 MB an entry); no local path in
any text; licence allowlist and an OpenStreetMap credit; payware + not the
verified developer → refused (Q303, pack-relative encoding not built); a
version that skips one; a change to a published version; any path outside
`entries/` → review. The app runs the same checks before publishing (preview).

## 6. Publishing

Device flow (`client_id` only, no secret; scope `public_repo`); the token in
the credential store (`O4_Authenticated_Sessions.store_api_key`, session
`github_library` — the Mac Keychain through the secret broker). The publish
needs no git: fork (`POST /repos/{repo}/forks`), `merge-upstream`, blobs → tree
over the fork's `main` → commit → ref `xptb/<ICAO>-<sig8>-v<N>` → pull request.
The version is one past the library's latest for that pack signature. The
licence (ODbL 1.0 and each source's terms, shown in the preview) is accepted once (`<data>/Library/licence_accepted.json`).

Configuration: `patch_library/config.py` `REPO` and `CLIENT_ID` (empty until
go-live: every library command then answers "not set up"); `XPTB_LIBRARY_*`
environment overrides (not `O4_`: the configuration digest reads those).

## 7. Fallbacks (design tiers 2–4)

Exact match → solved files laid down, solve skipped. Any mismatch (pack, law,
solve settings) → nothing solved is written, a stale adoption record is
dropped, the edits are laid down where the user has none, the next build
solves the airport here. Unreachable library → the cached index (any age); no
cache → the check says so; the build is today's. A hash mismatch refuses the
apply before any file is written.

## 8. The gate (2026-11-02, final code)

`tools/patch_library_gate.py --build plib2_B --world G2` (KPDX, tile +45-123,
pack `c_USA - 100_airport - KPDX (Flightbeam)`, signature `ccc0e0ffbd1d…`;
build `plib2_B` = steps 1 vector + 2 mesh on this branch) → **rc 0**:
v1 published (20.9 s), checks ok, auto-merged (verified developer); in an
empty data folder the app-open check lists KPDX `available`, usable as
solved (2.4 s); apply lays 6 files down (32.1 MB raw from 2.9 MB of entry,
16.8 s); the reuse gate logs "library patch matches your pack and engine —
solve skipped". v2 (19.3 s) → `newer` (v2, you have v1), applied, skipped.
An apt.dat row added in the world's pack clone → `pack_changed`; the reuse
gate rebuilds (`o4_library`: "your installed scenery pack is not the version
the patch was made for"); apply answers `re-solve`. No non-`file://` network
event in any receiver phase.

## 9. Deferred (not in phase 2)

* Pack-relative encoding for community payware entries (Q303) — refused by
  the checks until it exists.
* Ratings and problem reports (decision 12), the "submit your improvement"
  prompt (decision 8), `xpterrainbuilder://` links.
* Role overrides in `edits.json` (#1697 not built); edits are the edited patch.
* Re-solve "offers the new result back to the library" — the user publishes.
* The entries' object plans are carried, but the receiver's object stage on
  a library plan is not gate-tested (the KPDX gate covers the patch reuse).
* Tile bundles in the library (phase 3).
