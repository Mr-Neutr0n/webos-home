# Set up native Home

The starting point is a TV you own, with working root SSH and a tested recovery
login. For the rooting route used in the original project, read
[root-access.md](root-access.md). For another device, inspect its firmware
before you reuse the supplied profile.

## Configure the connection

Run these commands from the repository root on your computer:

```sh
bun install --frozen-lockfile
bun run verify
mkdir -p .local
chmod 700 .local
cp config.example.json .local/config.json
chmod 600 .local/config.json
```

Set `ssh.host` to your TV's LAN address or tailnet hostname. Set
`ssh.identity_file` to your own recovery key outside the repository. Keep
credentials under `~/.secrets/` with mode `600`. Only paths belong in the
configuration.

Populate `.local/known_hosts` with the TV's SSH host key. Compare its
fingerprint with the key from an existing trusted device session before
accepting it. `ssh-keyscan` collects a key; it does not authenticate it.

```sh
ssh-keyscan -p 22 webos-tv > .local/known_hosts.candidate
ssh-keygen -lf .local/known_hosts.candidate
# After the independent fingerprint comparison:
mv .local/known_hosts.candidate .local/known_hosts
chmod 600 .local/known_hosts
```

Replace `webos-tv` with the same host you configured. If you use a non-default
SSH port, use it in both places. The Python tools use regular SSH, including
regular SSH carried over Tailscale. The optional `tailscale ssh` command is a
separate login method described in [tailscale.md](tailscale.md).

## Check and back up

```sh
python3 scripts/webos.py --config .local/config.json check
python3 scripts/webos.py --config .local/config.json state
python3 scripts/webos.py --config .local/config.json backup
```

The supplied profile checks two SHA-256 digests and one exact QML path.
Stop on a mismatch. Establish which view the firmware loads, inspect its
controller interface, and verify rollback before adding a new profile.
The tools deliberately support only the documented Home paths today.

`backup` requires the stock view to be exposed. It saves the Home application
archive, selected stock QML file, and receipt under `.local/backups/` on your
computer. Keep a second copy outside the working directory. It is not a full
firmware or account backup.

An existing custom Home installation needs separate inspection. This tool
refuses to adopt an unowned `/media/developer/native-home` directory or an
unknown mount. Do not remove that guard to reuse the original project's live
installation.

## Choose the content

Copy `native-home/Config.js` to `.local/Config.js` and edit the local file.
The build uses it in place of the public defaults.

- `greetingNames` contains the names to cycle every ten seconds. An empty
  array gives a generic greeting.
- `quoteText` and `quoteAuthor` set the dashboard and full-room quotation.
- `apps` has four app IDs from your own inventory. Change the labels, colours,
  and optional images to match your apps.
- `showCharacters` enables the existing sample character atlas. Set it to
  `false` for a room with the cyborg cat and props only. See
  [the artwork notice](../NOTICE.md).
- Weather is off by default. Set its label and Open-Meteo URL only if you
  want requests from the TV. Use a city-level location and select the desired
  timezone in that URL. The room uses the TV's local time for lighting.

An optional `.local/characters.png` overrides the sample atlas. Keep its
six-column, four-row layout and 100 by 100 pixel cells. This substitutes art
without changing sprite timing.

```sh
python3 scripts/webos.py --config .local/config.json build
python3 scripts/webos.py --config .local/config.json stage
```

`build` makes a content-addressed directory and hash manifest under
`.local/build/`. `stage` verifies the backup and uploads the files. It does
not mount the new view. Build again after changing any config or source.

## Run the timed trial

Keep the recovery terminal open and watch the TV:

```sh
python3 scripts/webos.py --config .local/config.json trial
```

The default trial lasts 120 seconds. A TV-local watchdog restores stock when
it expires. Check the screen, all four focus frames, DPAD movement, the room
view, Play/Pause, and Back. Launch an installed app and return with Home.
Check playback separately if you want to claim that it works.

If the view works, activate it before the trial expires:

```sh
python3 scripts/webos.py --config .local/config.json activate --confirm-visual
```

Activation installs the owned webOSbrew startup hook and enables it. It does
not prove cold-boot behavior. Test a software reboot, remote standby wake,
and a physical power cycle separately. Quick Start+ can make standby wake
fast, at the cost of standby power. It does not shorten a wall-power boot.
The original installation can show stock Home during full startup.

## Restore stock Home

```sh
python3 scripts/webos.py --config .local/config.json rollback
```

Rollback clears the owned enable marker, unmounts the owned QML view, checks
the exposed stock hash, invalidates Home's own process checkpoint, and
restarts Home. It keeps other applications and services intact. It needs a
working root connection. Retain the original recovery channel and backup.

## Optional paired remote and captures

The Node.js SSAP helper pairs with the TV, saves an inventory, sends remote
buttons, and captures the display. Configure `ssap.url` and its SHA-256 TLS
certificate fingerprint first. Verify the fingerprint using an existing
trusted channel. Keep the client key at the configured private `.env` path.

```sh
node scripts/ssap.mjs --config .local/config.json pair
node scripts/ssap.mjs --config .local/config.json inventory
node scripts/ssap.mjs --config .local/config.json capture home.jpg
node scripts/ssap.mjs --config .local/config.json button UP ENTER BACK
```

Accept the pairing prompt on the physical TV. Raw captures and inventories
stay under `.local/`. Review them for names, locations, account state, and
device identifiers before sharing. `launch` reports an API acknowledgement;
it cannot establish that a stream is ready to play.

The helper uses Node's WebSocket TLS implementation with a pinned TV
certificate. Bun installs dependencies and runs verification. Some firmware
rejects the software-version API with a permission error; inventory records
that field as unavailable and still saves the supported results. The pointer
API can return an unencrypted `ws://` socket on the local network. The helper
accepts only the configured TV's socket and sends allowlisted buttons there.
It sends no pairing key to that socket.

## What was tested

The original device project tested the native view, root access, app switching,
rollback, software reboots, and a separate physical startup check. This public
installer is a new extraction of that work. Its automated tests exercise
guards and deployment failure paths with fake transports. The public helpers
passed root-state, inventory, display-capture, and remote-button checks on the
original device. The public installer was not activated there. A fresh
end-to-end deployment of this exact package has not been tested.
