#!/bin/bash
# Clear a wedged "access files on a removable volume" TCC dialog without
# rebooting. The dialog is hosted by the user-session tccd; on the macOS 27
# betas it can hang after Allow and survive the app quitting. Restarting
# tccd dismisses it. launchd respawns tccd on demand, so this is safe.
#
#   ./scripts/unstick_tcc.sh           # dismiss a stuck dialog
#   ./scripts/unstick_tcc.sh --reset   # also clear the app's removable-volume
#                                      # grant so the next launch prompts fresh
#
# Note: SIGTERM is ignored and `launchctl kickstart` is blocked by SIP on
# these builds — SIGKILL is the only signal that works.

set -u
BUNDLE_ID="com.novemberlima.XPTerrainBuilder"

echo "Restarting user-session tccd..."
killall -9 tccd 2>/dev/null || true
sleep 2

if ! pgrep -q -U "$(id -u)" tccd; then
    # tccd is launched on demand; poke it so we can confirm it's back.
    launchctl print "gui/$(id -u)/com.apple.tccd" >/dev/null 2>&1
    sleep 1
fi

if pgrep -q -U "$(id -u)" tccd; then
    echo "tccd restarted (pid $(pgrep -U "$(id -u)" tccd | head -1))."
else
    echo "tccd not running yet — it relaunches on the next permission check."
fi

if [[ "${1:-}" == "--reset" ]]; then
    echo "Resetting removable-volume grant for $BUNDLE_ID..."
    tccutil reset SystemPolicyRemovableVolumes "$BUNDLE_ID" || true
fi

cat <<'EOF'

If the dialog is still on screen, the fallbacks (each harmless) are:
  killall -9 UserNotificationCenter CoreServicesUIAgent
  sudo killall -9 tccd        # also restarts the system tccd instance
EOF
