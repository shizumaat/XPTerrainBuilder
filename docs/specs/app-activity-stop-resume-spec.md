# App — the activity pane's stop is immediate, honest, and reversible

Spec: 2026-08-11, FROZEN (Fable lead). App-side Swift only; NO engine
or wire-protocol change. Pre-ship mode (Ortho4XP/docs/RULINGS.md);
deviations STOP-and-report.

## Owner report

Clicking the X next to a tile build's progress "does not appear to
work, or there's a long delay"; the UI should update immediately,
showing the task stopped, and the button should become a RESUME button
so the tile can be restarted without re-finding it on the map. The X
"feels like a close" — replace it with a red stop-sign shape.

## Mechanism (measured in code)

`BuildModel.cancelTile` (BuildModel.swift:1069) sends `cancel_tile` and
only rewrites the row's LABEL to "stopping…"; the row's STATE stays
`.active`/`.queued` until the engine notices its cancel flag, which it
polls at phase boundaries — minutes on a mesh phase. The button
(BuildPane.swift:911-923, `xmark.circle`) renders only for
queued/active/indeterminate states, so after eventual cancellation it
disappears and nothing offers a restart.

## The laws

### S1 STOPPING IS A LOCAL STATE CHANGE, IMMEDIATELY

* `TileProgress.State` gains `.stopped`. Clicking stop: send
  `cancel_tile` exactly as today AND set the row to
  `.stopped`, label "stopped", percent frozen where it was — in the
  same action, no engine round-trip.
* Row presentation for `.stopped`: status text and progress tint
  `.orange`; the tile clock freezes (stop feeding it).
* Engine events arriving for a locally-stopped tile are STALE and are
  dropped — with ONE exception: a terminal tile-done event still wins
  (a tile that completed before the cancel took effect is genuinely
  built, and saying "stopped" over a built tile would be a lie). A
  terminal tile-error event also wins.
* The map badge / any other reader of `activity.tiles` must render
  `.stopped` without crashing — sweep the `switch` sites (the two in
  ActivityBox, plus MapCanvasView's progress-ring badge if it switches
  on state) and give `.stopped` the same visual family (orange).

### S2 THE STOP BUTTON IS A STOP SIGN; STOPPED ROWS GET RESUME

* For queued/active/indeterminate rows, the button becomes a red
  stop-sign: `Image(systemName: "octagon.fill")` in `.red` with a
  small white `stop.fill` overlaid (ZStack, the octagon is the
  stop-sign shape), `.help("Stop this tile")`. Same borderless/small
  styling as today. (If the owner's "hexagon" is meant literally a
  6-sided swap is one symbol name; the octagon IS the stop-sign shape
  and is what ships.)
* For a `.stopped` row the button is `play.circle.fill` in `.green`,
  `.help("Resume this tile")`, calling `resumeTile(coord)`.
* The stop/resume buttons no longer require `buildModel.isBuilding` —
  a stopped row must keep its resume button after the run ends (the
  whole point: no re-finding the tile). Keep `usesProtocol`.

### S3 RESUME RE-RUNS THE TILE WITH ITS OWN RUN'S SETTINGS

* At run start, snapshot the run's build settings (provider, zoom —
  whatever `startBuild` passes per tile today) into the activity model
  (`runSettings`), so resume uses the settings the tile was STARTED
  with, not whatever the pickers say now.
* `resumeTile(coord)`:
  * engine idle (`!isBuilding`): start a single-tile run for `coord`
    with the snapshot settings, through the existing `startBuild`
    machinery (factor a `startBuild(tiles:settings:)` core if needed —
    behaviour of the existing button path must stay byte-identical).
  * engine busy: add `coord` to a `resumeQueue` (ordered, deduped),
    set the row to `.queued` with label "resumes after current run";
    when the current run ends (the existing run-end handling), the
    app automatically starts one follow-up run with the queued tiles
    and the snapshot settings. NO engine protocol change — the queue
    is client-side.
  * A resumed tile's row resets its clock and percent.
* Stopping a "resumes after current run" row removes it from
  `resumeQueue` and returns it to `.stopped` (stop is always the
  inverse of resume).

## Tests

No app test target exists (SceneryKitTests only — the selrestore
precedent). Testable pure logic (the stale-event rule: which incoming
states may overwrite `.stopped`; the resumeQueue order/dedup) should
live as small static/pure helpers on BuildModel so a future target can
pin them; the skip gets the ledger line at merge. `swift build` and
`swift test` (47 existing) with DEVELOPER_DIR=/Applications/
Xcode-beta.app, once.

## Acceptance (owner, in-app)

Start a multi-tile build; stop an active tile — the row flips to
orange "stopped" INSTANTLY with a green resume button; the engine's
eventual phase-boundary cancel changes nothing visibly. Resume while
the run is still going — the row shows "resumes after current run"
and the tile rebuilds automatically afterward with the original
provider/zoom. Stop a queued tile; resume after the whole run ended —
a fresh single-tile run starts. A tile that finishes before its
cancel lands shows done, not stopped.

## Constraints

Match the surrounding SwiftUI idiom (borderless small controls,
`.help` tooltips, caption fonts). No PrefKeys/persistence (the
resumeQueue is session-local). Do not touch `Ortho4XP/`,
`Resources/VERSION`, or the engine client's wire-protocol matching.
