# Working on this repository

This is a worked example for a rooted webOS Home replacement. Begin with
read-only inspection. A firmware profile is valid only when its binary and
stock QML hashes match the target.

For a new device, read [docs/setup.md](docs/setup.md), collect its versions,
verify root and the SSH host key, and save the Home backup locally. Complete
the timed trial and inspect remote navigation before activating the boot hook.
For rooting history or Developer Mode persistence, read
[docs/root-access.md](docs/root-access.md). For remote administration, read
[docs/tailscale.md](docs/tailscale.md). For performance claims, read
[docs/comparison.md](docs/comparison.md).

Keep target-specific config, client keys, host keys, captures, inventories,
and firmware backups under ignored `.local/`. Device changes need the owner's
authorization. Preserve a separate working recovery login before a UI trial.
Treat firmware hash mismatches as a stop condition. Do not replace the
expected hash merely to make a check pass.

The public scripts intentionally refuse unknown Home paths and unowned
deployment directories. Inspect an existing custom installation separately.
Core input, Bluetooth, HDMI, networking, and DRM services are outside the Home
installer's scope. An installed application record does not prove a running
workload.

Use `bun run verify` after code changes. Keep host-only dependencies off the
TV. A screenshot proves visible output; a launch acknowledgement proves only
that the API accepted the request. Record successful playback, physical
power-cycle tests, and software reboots as separate results.

Before publishing captures or reports, remove addresses, account details,
device identifiers, pairing material, and private paths. The demonstration's
owner-approved first name is the only personal data intentionally included
in the supplied media.
