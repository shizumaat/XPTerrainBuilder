# Qt parity — selection restore + stop/resume reach the Windows/Linux app

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **qtparity**. Pre-ship mode
(docs/RULINGS.md); deviations STOP-and-report. Owner directive: "Make
sure the Windows and Linux UI has been kept up to date with any changes
made to the swift UI."

## The parity contract

The Swift specs are the behavioural authority — port SEMANTICS, not
code, into the Qt app's own idiom:

* `../docs/specs/app-restore-tile-selection-spec.md` (repo root) —
  selection restore across launches.
* `../docs/specs/app-activity-stop-resume-spec.md` — immediate local
  stopped state, stop-sign button, resume with run-settings snapshot;
  §S2 as amended (octagon, 16 pt-equivalent, white square centred by
  construction — owner-confirmed).

Engine-owns-features law: BOTH features are pure UI state over the
existing engine surface (`cancel_tile` protocol command, tile build
start) — NO engine/wire change is needed or permitted. If you find one
is needed, STOP and report.

## Q1 Selection restore (Swift c9d004f semantics)

`O4_Qt_Map.py` keeps `_selection` in memory only. Persist the selected
set and the active tile across launches through the Qt app's EXISTING
persistence idiom (find it: QSettings or the app's cfg — follow
whatever the Qt app already uses for window/user state; do not invent
a second store). Canonical tile-key spelling; malformed entries drop
silently; restore ordering must let any "adopt the built tile's
provider/zoom on selection" behaviour (if the Qt app has the
equivalent) fire as on a user click; empty state = today's launch.
Persist on selection change, restore at startup.

## Q2 Stop/resume (Swift 765a51c + 368ca09 semantics)

`O4_Qt_GUI.py` has a per-tile cancel (QToolButton, "the platform
style's standard close icon", ~line 1859) that sends the cancel and
waits on the engine. Port the Swift laws:

* S1: clicking stop flips the row to a local "stopped" state
  IMMEDIATELY (orange status + frozen progress/clock); later engine
  events for that tile are stale and dropped, EXCEPT terminal done /
  error which still win. Sweep every reader of the row state
  (progress bars, map badges in O4_Qt_Map) for the new state.
* S2: the button is a red stop-sign OCTAGON with a centred white
  square — in Qt, PAINT it (QPainterPath octagon + centred rect into
  a QIcon/pixmap at the row control size, crisp at HiDPI); no
  platform close icon. A stopped row's button becomes a green
  resume control (standard play triangle), tooltip "Resume this
  tile"; stopped rows and their resume buttons SURVIVE run end.
* S3: resume re-runs the tile with the settings its run STARTED with
  (snapshot per run); engine idle ⇒ start a single-tile run; engine
  busy ⇒ ordered/deduped resume queue, row shows "resumes after
  current run", one follow-up run auto-starts at run end; stopping a
  queued-for-resume row returns it to stopped. A wholesale run-stop
  DROPS the pending resume queue (the Swift edge ruling).

## Q3 The drift sweep

After Q1/Q2, diff the recent Swift UI history
(`git log --oneline -15 -- Sources/XPTerrainBuilder/` in the repo
root) against the Qt app and REPORT (not fix) any OTHER user-facing
Swift behaviour with no Qt counterpart — one line each, so the lead
can decide. Known-not-applicable examples don't need listing (macOS
packaging, TCC, SwiftUI-only plumbing).

## Tests

The Qt app's existing test idiom (tests/ has Qt coverage? — find it;
if the Qt GUI has no test harness, the pure logic — stale-event rule,
resume-queue order/dedup, key round-trip — lands as plain-Python
helpers testable headless, with one new test file in the repo's
pytest idiom, run once, ledgered). `Ortho4XP_Qt.py` must import-clean:
`venv/bin/python -c "import sys; sys.path.insert(0,'src'); import
O4_Qt_GUI"` headless-safe check per the repo's convention (core
modules never import a GUI toolkit — the INVERSE applies here: the Qt
modules may, but must not break the headless import convention the
tests use; follow whatever the existing tests do).

## Acceptance

Headless: tests once, ledgered. Visual: the owner runs the Qt app
(Windows/Linux release path) — pre-ship law, in-sim/in-app pass is
acceptance. Quote in your report: the persistence keys written, the
painted-icon code, and the Q3 drift list.
