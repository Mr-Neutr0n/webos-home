# Tailscale on rooted webOS

Tailscale provides remote access when the TV and your computer use different
networks. This setup needs working root access, persistent writable storage, and
`/dev/net/tun`. It uses the kernel TUN interface. It does not route the home LAN
or make the TV an exit node.

The tested combination was Tailscale `1.104.1`, the `arm64` static release,
webOS Hub22 `7.5.9-36`, and Linux `5.4.96`. The firmware userland was 32-bit, but
these static aarch64 binaries ran on its 64-bit kernel. Check both the kernel
architecture and actual binary execution on your own device. Tailscale offers
these binaries on a best-effort basis for systems it does not directly support.
See [the official static installation guide](https://tailscale.com/docs/install/static).

All commands below use `webos-tv` as an example hostname or private SSH alias.
Set it to your device locally. Keep the existing LAN root connection open while
enrolling and testing. Do not run a second daemon if Tailscale is already installed.

## Download and verify

Run on your computer from the repository root:

```sh
mkdir -p .local/tailscale-download
cd .local/tailscale-download
curl -fLO https://pkgs.tailscale.com/stable/tailscale_1.104.1_arm64.tgz
printf '%s  %s\n' \
  f60294374967f3dfd8cf57bbbd474d6cfce32d123e3a8ddeab82a87940daa806 \
  tailscale_1.104.1_arm64.tgz | shasum -a 256 -c -
tar -xzf tailscale_1.104.1_arm64.tgz
cd ../..
```

The archive hash was checked against
[Tailscale's published checksum](https://pkgs.tailscale.com/stable/tailscale_1.104.1_arm64.tgz.sha256).
These are the extracted binary hashes from the tested release:

| File | SHA-256 |
| --- | --- |
| `tailscale` | `6c2c134abad7cbbc8bc94a226b2972b4b7d5603daa0ca0bb9dc3b74a1dc15814` |
| `tailscaled` | `6367abc3ffd608ed64a762928444ee53ac4e99bf19baabb0321852d7f02b10b6` |

This is a reproducibility pin, not a claim that this version remains the newest.
When upgrading, verify the new release and update both hashes before replacing
the binaries. Do not bypass a failed hash check.

## Copy to persistent storage

First run these read-only checks in the TV's root shell:

```sh
id -u
uname -m
test -c /dev/net/tun && echo 'TUN exists'
df -h /media/developer /var
pidof tailscaled || true
```

Stop here if root or TUN is missing, or an existing daemon is present. Do not
remove another installation's socket, process, or saved state.

For a fresh installation, create the directories on the TV:

```sh
umask 077
mkdir -p /media/developer/tailscale/bin
mkdir -p /var/lib/webosbrew/tailscale/.secrets
chmod 700 /var/lib/webosbrew/tailscale
chmod 700 /var/lib/webosbrew/tailscale/.secrets
```

Copy the two binaries from your computer. These SSH commands use a previously
verified host key and your existing root authentication:

```sh
ssh root@webos-tv 'cat > /media/developer/tailscale/bin/tailscale' \
  < .local/tailscale-download/tailscale_1.104.1_arm64/tailscale
ssh root@webos-tv 'cat > /media/developer/tailscale/bin/tailscaled' \
  < .local/tailscale-download/tailscale_1.104.1_arm64/tailscaled
```

Back in the TV's root shell:

```sh
chown 0:0 /media/developer/tailscale/bin/tailscale /media/developer/tailscale/bin/tailscaled
chmod 755 /media/developer/tailscale/bin/tailscale /media/developer/tailscale/bin/tailscaled
sha256sum /media/developer/tailscale/bin/tailscale /media/developer/tailscale/bin/tailscaled
/media/developer/tailscale/bin/tailscale version
```

Compare both hashes with the table. A version string alone does not verify the
file. No Tailscale binaries or enrolled identity files belong in this repository.

## Start and enroll

For the first start, run in the TV's root shell:

```sh
umask 077
mkdir -p /tmp/webosbrew-tailscale
chmod 700 /tmp/webosbrew-tailscale
test ! -e /tmp/webosbrew-tailscale/tailscaled.sock || exit 1
nohup /media/developer/tailscale/bin/tailscaled \
  --tun=tailscale0 \
  --state=/var/lib/webosbrew/tailscale/.secrets/tailscaled.state \
  --statedir=/var/lib/webosbrew/tailscale/.secrets \
  --socket=/tmp/webosbrew-tailscale/tailscaled.sock \
  --no-logs-no-support \
  --port=0 \
  > /tmp/webosbrew-tailscale/daemon.log 2>&1 < /dev/null &
echo $! > /tmp/webosbrew-tailscale/tailscaled.pid
```

The saved state is opaque Tailscale data. Do not source, edit, print, or commit
it. Runtime logs, the socket, and the PID file stay under `/tmp`; the identity survives under
`/var/lib`. The daemon's `--no-logs-no-support` option disables its log upload.
Local files can still contain private data.

Wait for `/tmp/webosbrew-tailscale/tailscaled.sock` to appear. If the daemon exits,
inspect its private log before retrying. Use a shell function so every CLI
command reaches this daemon:

```sh
ts() {
  /media/developer/tailscale/bin/tailscale \
    --socket=/tmp/webosbrew-tailscale/tailscaled.sock "$@"
}
ts up --hostname=webos-tv \
  --netfilter-mode=off \
  --accept-dns=false \
  --accept-routes=false
```

Open the login URL privately on your computer and approve the node. Do not put
the URL or an auth key in a transcript or repository. Then run:

```sh
chmod 600 /var/lib/webosbrew/tailscale/.secrets/tailscaled.state
ts status
ts ip -4
ip link show tailscale0
```

The tested kernel had no usable iptables filter table. It required
`--netfilter-mode=off`; `nodivert` still needs rule creation and did not solve
that limitation. With `off`, Tailscale manages no host firewall rules. Tailnet
access policy still controls tailnet connections, but it does not protect LAN
services or add local firewall filtering. See
[Tailscale's netfilter modes](https://tailscale.com/docs/reference/netfilter-modes).

DNS and accepted routes stay off to avoid changing the TV's DNS or routing it
through other nodes. This procedure does not advertise routes or an exit node.
For an already enrolled node, inspect its existing settings before changing
anything. Use `tailscale set` for deliberate preference changes rather than
re-enrolling. See [the CLI reference](https://tailscale.com/docs/reference/tailscale-cli).

## Choose the SSH server

There are two separate options:

| Option | Authentication |
| --- | --- |
| Regular SSH over a Tailscale connection | Homebrew Channel's Dropbear server and your SSH key |
| Tailscale SSH | The SSH server inside `tailscaled`, authorized by tailnet policy |

For regular SSH, leave Tailscale SSH disabled and use the TV's tailnet hostname
or address with your existing SSH key. Keep host-key checking enabled.

To enable Tailscale SSH, first allow both network access to port 22 and an SSH
rule permitting your user to log in as `root`. The following policy fragment
allows members to access their own devices in check mode. It applies to all
their own devices, not only this TV. Merge and test it against your existing
policy; do not replace the whole policy file:

```json
{
  "grants": [
    {
      "src": ["autogroup:member"],
      "dst": ["autogroup:self"],
      "ip": ["tcp:22"]
    }
  ],
  "ssh": [
    {
      "action": "check",
      "src": ["autogroup:member"],
      "dst": ["autogroup:self"],
      "users": ["root"]
    }
  ]
}
```

Then run `ts set --ssh=true` from the TV's LAN root shell. Enabling it intercepts
port 22 on the Tailscale address and can interrupt an existing tailnet SSH
session. It leaves the separate LAN SSH server available. Follow the
[official Tailscale SSH policy and setup guide](https://tailscale.com/docs/features/tailscale-ssh).

From another enrolled computer:

```sh
tailscale ssh root@webos-tv id
```

The expected UID is 0. Preserve host verification. Do not solve a key-publication
delay by disabling verification; wait for enablement to complete and retry.

## Start at boot

Homebrew Channel runs executable hooks in `/var/lib/webosbrew/init.d/`. Review
the included [`tailscale-start.sh`](../scripts/tailscale-start.sh), then copy it
there as `40-tailscale`. Its paths and hash checks must match the installation
above. Do not overwrite an existing hook without reviewing its ownership.

```sh
ssh root@webos-tv 'test ! -e /var/lib/webosbrew/init.d/40-tailscale && cat > /var/lib/webosbrew/init.d/40-tailscale' \
  < scripts/tailscale-start.sh
ssh root@webos-tv 'chown 0:0 /var/lib/webosbrew/init.d/40-tailscale && chmod 755 /var/lib/webosbrew/init.d/40-tailscale'
```

The hook starts the daemon with saved state. It must never run a login command
or generate a new identity on each boot. State directories use mode `700`;
state files and local logs use mode `600`. Keep backups equally private. Run
only one daemon with a given identity.

Test the hook manually after stopping only the daemon you started above. Inspect
the saved PID's executable and arguments before signaling it. Never use a broad
`pkill` against an unknown installation. Then test a software reboot and a cold
boot without starting anything from the computer. Confirm that root access still
works, `tailscale0` exists, and the same enrolled node reconnects.

To disable boot startup, rename the owned hook to `.40-tailscale.disabled`, then
stop the verified daemon. Keep the saved state if you intend to resume. Use your
tailnet admin controls to revoke an identity you intend to discard.

## What was tested

The original installation passed direct traffic in both directions over the
tailnet and software reboot startup without a computer-side start command.
A physical cold boot also restarted the daemon with its saved identity. The
final scheduling revision, which waits briefly for Home startup, received a
software reboot test but no new physical cold boot test.

Tailscale SSH worked from two enrolled computers and survived a daemon restart.
Its newly enabled SSH preference did not receive a separate full TV reboot test.
An outside-home-network session and standby reachability were not measured.
Repeat those tests for your installation before relying on remote recovery.

The included public boot hook is a portable version of the setup. This exact
hook has not been installed or boot-tested on a TV. It has shell syntax checks
and local failure-path tests. The original installation used a separate hook.

Observed daemon memory was about 22 to 35 MiB PSS in short samples. This is an
added memory cost, not evidence of sustained playback performance. Measure it on
your own firmware, especially on devices with less than 1 GiB RAM.
