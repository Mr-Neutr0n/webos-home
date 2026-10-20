# Contributing

Run `bun install --frozen-lockfile` and `bun run verify` before sending a pull
request. Keep each change focused. Describe what changed, how you checked it,
and which firmware you tested.

For a new firmware profile, include the webOS/SDK/firmware versions, Home
binary hash, stock target hash, selected QML path, and the reason that path is
active. Include the result of backup, timed trial, remote focus, app launch,
return to Home, and rollback. State whether a reboot was a software reboot,
remote standby wake, or physical power cycle. Mark untested steps explicitly.

Use generated or self-authored fixtures in tests. Keep firmware files,
credentials, addresses, serials, raw inventories, and personal screenshots
out of issues and patches. Add only artwork you can license and explain its
source in `NOTICE.md`. Contributions are offered under this repository's
license unless a file states otherwise.
