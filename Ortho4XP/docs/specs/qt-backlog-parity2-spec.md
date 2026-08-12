# Qt backlog — the four Q3 drift items reach the Windows/Linux app

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **qtbacklog**. Pre-ship
mode (docs/RULINGS.md); deviations STOP-and-report to the Fable lead.
Owner-ruled (closing interview 2026-08-11): all four items, one
implementer. Source of the list: the lane/qtparity Q3 drift sweep
(DEFERRED_VERIFICATION 2026-08-11 line). The Swift sources are the
behavioural authority — port SEMANTICS, not code, into the Qt app's
own idiom. Engine-owns-features law: none of these items needs or
permits an engine/wire change; if you find one is needed, STOP and
report.

## QB1 Optimistic launch overlay

Authority: `Sources/XPTerrainBuilder/TileScanCache.swift` +
`BuildModel.swift` `loadCachedTileStates()` (~:289).

The Qt map currently shows nothing until the engine's first scan
completes (the engine takes seconds just to boot). Port: persist the
scan results (built-tile info incl. provider, and installed [lat,lon]
pairs) keyed by the EXACT (working dir, Custom Scenery dir) pair the
scan ran against, with a schema version; at launch, if the pair
matches and the in-memory state is empty, the cached squares appear
immediately; the first rescan revalidates in the background and the
scan-done swap replaces the overlay with the truth. Conflict badges
(QB3) refresh from the cached state too. Cache location: the Qt app's
existing cache/prefs idiom (`.qt_prefs.json` is USER STATE — the scan
cache is a CACHE; use the platform cache dir via the app's existing
path helpers, not a second prefs store). Carry the Swift version
lesson: providers are cached NORMALIZED (the v3 bump existed because
legacy cfg quotes poisoned the imagery-source audit).

## QB2 ETA suppression (honest estimates)

Authority: `BuildModel.swift` ~:590–606 (the climbing-estimate
detector), `BuildPane.swift` `tileClockText` (~:1000),
`BuildConsoleView.swift` (run clock placement).

* A nil/absent remaining ⇒ render a DASH, never a wild number.
* Climbing detector, exact constants: keep (elapsed, remaining)
  samples; drop samples older than 45 s; baseline = the first sample
  ≥30 s old; if current remaining > baseline + 5 s ⇒ the UI shows
  "still estimating" (not the number). A nil remaining clears the
  sample window and the flag.
* Per-tile clock text: finished ⇒ the frozen final elapsed alone;
  active ⇒ "elapsed · ~remaining" (dash for remaining without a
  basis); queued ⇒ the bare "~estimate", or nothing at all.
* Verify the stopped-row rule shipped with Qt stop/resume: a stopped
  row's clock stays frozen where the stop left it even while the
  engine keeps counting until the cancel lands. If missing, it is in
  scope here.

## QB3 Per-tile imagery-source conflict badges

Authority: `BuildModel.swift` `conflictTiles` /
`refreshConflictTiles()` / `reauditConflict(for:)` (~:200, ~:308–345),
`TileTextureAudit.hasForeignSources`, `MapCanvasView.swift` ~:398
(badge drawn only when the tile square is wide enough, r.width > 14
equivalent).

A built tile whose textures folder carries imagery from a DIFFERENT
provider than the tile was built with gets a warning badge on the map
(and the selection pane's equivalent if the Qt app has one). Port the
audit semantics: names-only directory listings — one readdir per
tile, NO stat calls — swept off the UI thread over every built tile,
cancellable and re-armed on each scan; plus a single-tile re-audit
hook after any cleanup action the Qt app offers, so the badge clears
immediately. The audit predicate is a pure function — implement it as
a headless-testable Python unit in the Qt app's own module space (it
is UI-side state over scan results on both platforms; moving it into
the engine is an interface change = STOP-and-report if you conclude
it's needed).

## QB4 SecretRequest / credential path — ATTRIBUTE FIRST, then close the measured gap

The Q3 line claims: "NO SecretRequest handler — provider credential
prompts have no UI on Windows/Linux." Lead recon partially refutes
the second half: `src/O4_Qt_Settings.py` ~:332–484 already carries a
provider sign-in dialog (`sign_in`, `sign_in_api_key`, worker-thread
+ Signal completion), and `o4_engine/secret_broker.py`'s own contract
says in-process Qt sessions use `keyring` directly — `SecretRequest`
is only emitted at a front end that serves the engine over the JSONL
transport.

So: MEASURE before building anything (mechanism-before-fix):
1. Enumerate every path the Qt app executes engine work (in-process?
   any transport/subprocess path in the packaged Win/Linux app?
   parallel-build workers route secrets to the parent — verify the
   parent-side servicing works in the Qt app's process on
   Windows/Linux, i.e. `keyring` backends resolve there).
2. Audit the existing sign-in dialog's coverage: all three
   credential kinds (session / http_basic / api_key), error surfaces,
   registration_url display, sign-out — against
   `O4_Authenticated_Sessions`'s contract.
3. Audit the BUILD-TIME path: what does a Win/Linux user see when
   `ensure_session` finds no stored credential mid-build — is there
   any affordance pointing at the settings sign-in?

THEN: close only the MEASURED gap. If the gap is a missing transport
handler on a real Qt execution path, implement the `secret_response`
servicing over the platform store through the app's existing
`keyring` dependency (Windows Credential Locker / Linux Secret
Service), mirroring the Swift handler's get/set/delete semantics
(`Sources/SceneryKit/ProviderSecretStore.swift`,
`BuildModel.swift` ~:644–688) — the reply always carries
`request_id`, `ok`, and `secret` (get) or `error`. If the gap is
instead UX (no mid-build affordance / dialog gaps), fix that. If the
measured mechanism contradicts the Q3 line entirely, STOP and report
— the finding may retire the item, and that is the owner's call, not
yours.

## Tests

The qtparity round's idiom: pure-logic pieces land headless-testable
(climbing detector; scan-cache round-trip incl. the key-pair
mismatch and version-bump drops; the foreign-source audit predicate;
QB4's handler logic behind a fake store if built). One run, ledgered
(`tools/run_with_ledger.py`). `Ortho4XP_Qt` import-clean check per
the repo convention. Pre-existing failures matched at base are out
of scope.

## Acceptance

Headless: tests once, ledgered. Visual: the owner's Windows/Linux
app pass is acceptance (pre-ship law). The report quotes: the cache
file path + schema; the detector constants (45 s window / 30 s
baseline / +5 s tolerance) as landed; the badge paint site; and
QB4's measured attribution with what was (or was deliberately NOT)
built.

## Bookkeeping

Convergence guards: attempt cap 2 per target, second miss =
STOP-and-report; `.progress` heartbeat in the lane scratch dir.
Skipped verifications = DEFERRED_VERIFICATION.md candidate lines
(lead writes the final). Build-time impact: none permitted on the
engine (UI-only lane); the Qt app's own launch cost must not grow
user-visibly (the overlay exists to HIDE latency, not add it).
