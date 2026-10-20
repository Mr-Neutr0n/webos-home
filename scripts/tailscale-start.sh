#!/bin/sh
# Optional webOSbrew boot hook. Install only after the manual daemon test succeeds.
# Tailscale 1.104.1, linux-arm64. This hook never runs login or changes preferences.
set -eu
TS_BASE=${TS_BASE:-/media/developer/tailscale}
TS_STATE_DIR=${TS_STATE_DIR:-/var/lib/webosbrew/tailscale/.secrets}
TS_RUN_DIR=${TS_RUN_DIR:-/tmp/webosbrew-tailscale}
[ "$(id -u)" = 0 ]
[ -c /dev/net/tun ]
[ ! -L "$TS_STATE_DIR" ]
[ ! -L "$TS_RUN_DIR" ]
[ -s "$TS_STATE_DIR/tailscaled.state" ]
umask 077
mkdir -p "$TS_STATE_DIR" "$TS_RUN_DIR"
chmod 700 "$TS_STATE_DIR" "$TS_RUN_DIR"
[ ! -e "$TS_STATE_DIR/tailscaled.state" ] || chmod 600 "$TS_STATE_DIR/tailscaled.state"
# A new binary version needs a reviewed hash and a new manual test.
[ "$(sha256sum "$TS_BASE/bin/tailscale" | cut -d ' ' -f1)" = 6c2c134abad7cbbc8bc94a226b2972b4b7d5603daa0ca0bb9dc3b74a1dc15814 ]
[ "$(sha256sum "$TS_BASE/bin/tailscaled" | cut -d ' ' -f1)" = 6367abc3ffd608ed64a762928444ee53ac4e99bf19baabb0321852d7f02b10b6 ]
# A responsive socket means a daemon already owns the state.
if "$TS_BASE/bin/tailscale" --socket="$TS_RUN_DIR/tailscaled.sock" status --json >/dev/null 2>&1; then
    exit 0
fi
# An occupied but unresponsive socket requires manual inspection.
[ ! -e "$TS_RUN_DIR/tailscaled.sock" ]
mkdir "$TS_RUN_DIR/start.lock"
trap 'rmdir "$TS_RUN_DIR/start.lock"' EXIT HUP INT TERM
nohup "$TS_BASE/bin/tailscaled" --tun=tailscale0 --state="$TS_STATE_DIR/tailscaled.state" --statedir="$TS_STATE_DIR" --socket="$TS_RUN_DIR/tailscaled.sock" --port=0 --no-logs-no-support >"$TS_RUN_DIR/tailscaled.log" 2>&1 </dev/null &
daemon_pid=$!
printf '%s\n' "$daemon_pid" >"$TS_RUN_DIR/tailscaled.pid"
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if "$TS_BASE/bin/tailscale" --socket="$TS_RUN_DIR/tailscaled.sock" status --json >/dev/null 2>&1; then
        exit 0
    fi
    kill -0 "$daemon_pid" 2>/dev/null || exit 1
    sleep 1
done
# Leave the known daemon for the owner to inspect rather than starting a second.
exit 1
