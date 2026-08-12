# Swift provider sign-in — the macOS app gets the credential UI (Qt is the authority, in reverse)

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **swiftsignin**. Pre-ship
mode (docs/RULINGS.md); deviations STOP-and-report to the Fable lead.
Owner-filed 2026-08-11 (RULINGS 2026-08-11b): the macOS app has NO
provider sign-in UI — it only services the brokered Keychain store.
The Qt `_SignInDialog` + `_ProviderSignInSection`
(`src/O4_Qt_Settings.py` ~:321–560) are the behavioural authority;
port SEMANTICS AND COPY into SwiftUI's idiom.

## Architecture (engine-owns-features law)

The login flows are Python (`O4_Authenticated_Sessions`); the Swift
app runs the engine over the JSONL transport. So sign-in RUNS
ENGINE-SIDE and the app is a thin UI:

* THREE NEW PROTOCOL COMMANDS, registered in `jsonl._build_handlers`
  1:1 onto new `EngineSession` methods (the registry's own idiom):
  - `auth_providers` → list of provider-account descriptors for every
    definition carrying credentials: code/session_name, attribution,
    credential_kind ("session" | "http_basic" | "api_key"),
    login_url, registration_url, setup_steps (list), service host,
    signed-in status and stored username where knowable WITHOUT a
    network probe (mirror whatever `_ProviderSignInSection` shows;
    never add a network call the Qt section doesn't make).
  - `provider_sign_in` (session_name, username, secret, remember) →
    returns `{started: true}` IMMEDIATELY; the work runs on a worker
    thread; completion is a NEW EVENT (below). For api_key kind the
    secret is the key and username is empty —
    `sign_in_api_key(definition, key, remember)`; else
    `sign_in(definition, username, password, remember)`.
  - `provider_sign_out` (session_name) → synchronous is fine
    (`sign_out` is local); returns its result.
* ONE NEW EVENT CLASS in `o4_engine/events.py`:
  `SignInResult(session_name, ok, error_text)` — additive wire name,
  matched in Swift by string literal like every event; land BOTH
  sides in the same commit (blast.py reports drift).

**THE DEADLOCK HAZARD (this is why sign_in is async — do not
"simplify" it):** command handlers execute ON the transport read
loop (`jsonl.serve`). With `remember=True`, the engine-side secret
store routes through `UI.secret_broker.request(...)`, which BLOCKS
until the front end's `secret_response` arrives — and that response
is delivered BY THE SAME READ LOOP. The broker detects a same-thread
request and fails fast rather than deadlock. Therefore
`provider_sign_in` MUST dispatch to a worker thread (follow the
session's existing build-worker idiom) and reply via `SignInResult`.
Write the twin test that proves a brokered `remember=True` sign-in
from the transport thread would have failed, and that the worker
path stores successfully.

Protocol version: follow the existing minor-bump idiom (TileClocks
was "protocol 1.3") — find the declaration and bump the minor once
for all three commands + event.

## Engine work

`src/o4_engine/session.py` (+ `jsonl.py` registry, `events.py`).
`auth_providers` enumerates the definitions the Qt section
enumerates (the `.elv` definitions with a credential kind) via
`O4_Authenticated_Sessions`'s own helpers — never a private re-parse.
Under the transport, `credential_store_available()` is True by
construction (broker active) — the descriptor carries it anyway so
the UI never hard-codes it. Errors: `LoginError` text goes into
`SignInResult.error_text` verbatim (the Qt dialog shows `str(error)`
— same). Any other exception becomes `LoginError(str(error))`
semantics, exactly as the Qt worker does.

## Swift work

* `Sources/SceneryKit/OrthoEngineClient.swift`: decode `SignInResult`
  (string-literal match, same as every event) and expose the three
  commands with typed wrappers.
* `Sources/XPTerrainBuilder/SettingsView.swift`: a "Provider
  Accounts" section (GeneralPane, beside the existing providers
  count row) listing each auth provider with its attribution, status
  ("Signed in as …" / "Not signed in" per the descriptor), and a
  Sign in / Sign out control.
* A sign-in SHEET porting the Qt dialog exactly:
  - Title: "Sign in — {attribution or service host}".
  - Intro copy, VERBATIM from the Qt dialog (api_key kind: "This
    provider requires a (free) account at {host} and an API key
    generated there.  Paste the key below; it is stored in the
    system keychain." — under this app "system keychain" is true via
    the broker; session kinds: "This provider requires a (free)
    account at {host}.  Your password is sent only to that
    service.").
  - `registration_url` present ⇒ "No account yet?  Create one here."
    as a tappable link.
  - `setup_steps` present ⇒ a numbered Setup checklist, http(s) URLs
    in a step rendered as links (the Qt `_linkify_urls` behaviour).
  - Fields: username ("Username or email address") + secure field
    ("Password"); api_key kind hides username and the secure field's
    placeholder is "API key".
  - Remember: "Remember on this device (stored in the system
    keychain)". Checked by default when the store is available (it
    is, under the app); api_key kind: forced on and HIDDEN (a key
    only works stored).
  - Validation before sending, same messages: api_key kind empty key
    ⇒ "Paste an API key."; else missing either field ⇒ "Enter both a
    username and a password."
  - Busy state: button "Signing in…", fields disabled; completion on
    `SignInResult`: ok ⇒ dismiss; error ⇒ red error text, re-enable,
    focus the secure field. Cancel always available (the engine-side
    attempt just completes into a dismissed sheet — dropping the
    event for a dismissed sheet is fine; no cancellation protocol).
  - The password/key value lives only in the sheet's state and the
    one command send; never logged, never persisted app-side.
* NO app-side Keychain writes for provider credentials — storage is
  the engine's `remember` path through the existing broker (the
  app's `ProviderSecretStore` services it; that is the whole point).

## Tests

Engine: new-command tests in the o4_engine test idiom (fake sessions
module / monkeypatched `O4_Authenticated_Sessions`, no network):
registry lookup, descriptor shape, async sign-in delivers
`SignInResult` (ok and LoginError arms), sign-out, the read-loop
deadlock twin (above). Swift: `DEVELOPER_DIR=/Applications/
Xcode-beta.app swift build` must succeed; add SceneryKit decode
tests for `SignInResult` if the existing event-decode test idiom
exists (follow it; if none exists, the build is the check — say so).
Run directly-covering Python test files once, ledgered. Pre-existing
failures matched at base are out of scope.

## Acceptance

Headless: tests once, ledgered; swift build green. Visual: the
owner's in-app pass (pre-ship law). Report quotes: the protocol
additions (commands, event, version bump), the descriptor shape, the
sheet copy as landed, and proof the secret rode the broker (the twin
test's assertion, not a live Keychain read).

## Bookkeeping

Convergence guards: attempt cap 2, STOP-and-report on the second
miss; `.progress` heartbeat. DEFERRED candidates for skipped
verifications (lead writes final). Build-time: engine-side additions
are command-path only (no build-path cost); state that in the
report. Cross-refs: RULINGS 2026-08-11b (this item's filing + QB4
retirement), secret_broker.py's threading contract, the qtbacklog
lane's QB4 measurement (DEFERRED 2026-08-11 line).
