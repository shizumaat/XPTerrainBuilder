#!/usr/bin/env bash
# Notarize and staple a SIGNED XPTerrainBuilder.app.
#
#   scripts/notarize_app.sh APP
#
# Requires, in the environment (App Store Connect API key — Users and Access
# ▸ Integrations ▸ Team Keys, role Developer):
#   NOTARY_KEY_PATH   path to the .p8 private key file
#   NOTARY_KEY_ID     the key's Key ID
#   NOTARY_ISSUER_ID  the team's Issuer ID (a UUID)
#
# With any of them absent this script REFUSES BY NAME (rc != 0).  It never
# silently skips: a release that quietly shipped un-notarized would look
# exactly like a good one until a tester's Mac refused to open it.
#
# Run scripts/sign_app.sh first — the notary service rejects anything that
# is not hardened-runtime signed with a Developer ID and a secure timestamp.
#
# bash, not zsh: this also runs on the GitHub macOS runner.
set -euo pipefail

APP="${1:?usage: notarize_app.sh APP}"
APP="${APP%/}"

if [[ ! -d "$APP" ]]; then
  echo "ERROR: no app bundle at $APP" >&2
  exit 1
fi

MISSING=""
for var in NOTARY_KEY_PATH NOTARY_KEY_ID NOTARY_ISSUER_ID; do
  eval "val=\${$var:-}"
  [[ -n "$val" ]] || MISSING="$MISSING $var"
done
if [[ -n "$MISSING" ]]; then
  echo "REFUSED: notarization credentials missing:$MISSING" >&2
  echo "         Set NOTARY_KEY_PATH (.p8), NOTARY_KEY_ID and NOTARY_ISSUER_ID." >&2
  exit 1
fi
if [[ ! -f "$NOTARY_KEY_PATH" ]]; then
  echo "REFUSED: NOTARY_KEY_PATH does not name a file." >&2
  exit 1
fi

# The app must already be signed with a Developer ID and the hardened
# runtime; catching that here costs a second, catching it at the notary
# service costs a round trip.
info="$(codesign --display --verbose=4 "$APP" 2>&1 || true)"
case "$info" in
  *TeamIdentifier=not\ set*|*"TeamIdentifier=-"*)
    echo "REFUSED: $APP is not Developer ID signed — run scripts/sign_app.sh first." >&2
    exit 1 ;;
esac
case "$info" in
  *runtime*) ;;
  *) echo "REFUSED: $APP is not signed with the hardened runtime (flags lack 'runtime')." >&2
     exit 1 ;;
esac

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
ZIP="$WORK/$(basename "$APP" .app)-notarize.zip"

# ditto, not `zip`: only ditto preserves the symlinks and the extended
# attributes that carry the signature inside the bundle.
echo "Zipping for submission …"
ditto -c -k --keepParent "$APP" "$ZIP"

echo "Submitting to the notary service (this waits for the verdict) …"
SUBMIT_LOG="$WORK/submit.txt"
set +e
xcrun notarytool submit "$ZIP" \
  --key "$NOTARY_KEY_PATH" \
  --key-id "$NOTARY_KEY_ID" \
  --issuer "$NOTARY_ISSUER_ID" \
  --wait --output-format json > "$SUBMIT_LOG" 2>&1
SUBMIT_RC=$?
set -e
cat "$SUBMIT_LOG"

# Parse without jq (not on a stock mac): the JSON is one flat object.
STATUS="$(sed -n 's/.*"status" *: *"\([^"]*\)".*/\1/p' "$SUBMIT_LOG" | tail -1)"
SUBMIT_ID="$(sed -n 's/.*"id" *: *"\([^"]*\)".*/\1/p' "$SUBMIT_LOG" | head -1)"

if [[ "$STATUS" != "Accepted" ]]; then
  echo "REFUSED: notarization status '${STATUS:-<none>}' (notarytool rc $SUBMIT_RC)." >&2
  if [[ -n "$SUBMIT_ID" ]]; then
    echo "--- notarytool log $SUBMIT_ID ---" >&2
    xcrun notarytool log "$SUBMIT_ID" \
      --key "$NOTARY_KEY_PATH" \
      --key-id "$NOTARY_KEY_ID" \
      --issuer "$NOTARY_ISSUER_ID" >&2 || true
  fi
  exit 1
fi

echo "Accepted (submission $SUBMIT_ID). Stapling …"
xcrun stapler staple "$APP"
xcrun stapler validate "$APP"

echo "Gatekeeper assessment:"
SPCTL_OUT="$WORK/spctl.txt"
set +e
spctl --assess --type exec -vv "$APP" > "$SPCTL_OUT" 2>&1
SPCTL_RC=$?
set -e
cat "$SPCTL_OUT"
if ! grep -q "Notarized Developer ID" "$SPCTL_OUT"; then
  echo "REFUSED: spctl does not report 'Notarized Developer ID' (rc $SPCTL_RC)." >&2
  exit 1
fi

echo "OK: $APP is notarized and stapled — it opens with no Gatekeeper dialog."
