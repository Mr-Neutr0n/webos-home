#!/usr/bin/env python3
"""Rooted webOS Home deployment. Local files and backups stay under .local/."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
BASE = '/media/developer/native-home'
HOOK = '/var/lib/webosbrew/init.d/20-native-home'
OWNER = 'webos-home-v1'
Q = shlex.quote


class GuardError(RuntimeError):
    """A deployment precondition failed."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def private_write(path: Path, data: bytes):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)


def load_config(path: Path):
    config = json.loads(path.read_text())
    p = config['profile']
    for key in ('home_binary_sha256', 'stock_qml_sha256'):
        if not re.fullmatch('[a-f0-9]{64}', p[key]):
            raise GuardError('Invalid profile digest: ' + key)
    for key in ('home_binary', 'target'):
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+', p[key]) or '..' in p[key].split('/'):
            raise GuardError('Invalid profile path: ' + key)
    if p['home_binary'] != '/usr/bin/com.webos.app.home' or p['target'] != (
        '/usr/palm/applications/com.webos.app.home/qml/UserInterfaceLayer/Containers/MainView_WEE.qml'
    ):
        raise GuardError('This tool supports the documented native Home paths only')
    if not 30 <= int(config.get('trial_seconds', 120)) <= 600:
        raise GuardError('trial_seconds must be between 30 and 600')
    return config


class SSH:
    def __init__(self, config):
        ssh = config['ssh']
        if not re.fullmatch(r'[A-Za-z0-9_.:-]+', ssh['host']) or ssh['host'].startswith('-'):
            raise GuardError('Invalid SSH host')
        if ssh.get('user', 'root') != 'root':
            raise GuardError('The native Home mount requires root')
        port = int(ssh.get('port', 22))
        if not 1 <= port <= 65535:
            raise GuardError('Invalid SSH port')
        self.args = ['ssh', '-p', str(port), '-i', str(Path(ssh['identity_file']).expanduser()),
                     '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                     '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
                     '-o', 'UserKnownHostsFile=' + str((ROOT / Path(
                         ssh['known_hosts_file']).expanduser()).resolve()),
                     'root@' + ssh['host']]

    def run(self, script, data=None, timeout=30):
        result = subprocess.run(self.args + [script], input=data, capture_output=True, timeout=timeout)
        if result.returncode:
            raise GuardError('Remote command failed: ' + result.stderr.decode(errors='replace')[:1500])
        return result.stdout.decode().strip()

    def get(self, script, timeout=60):
        result = subprocess.run(self.args + [script], capture_output=True, timeout=timeout)
        if result.returncode:
            raise GuardError('Remote backup failed: ' + result.stderr.decode(errors='replace')[:1000])
        return result.stdout

    def put(self, data, target):
        self.run('umask 077; cat > ' + Q(target), data=data)


class Home:
    def __init__(self, config, transport=None):
        self.c = config
        self.p = config['profile']
        self.t = transport or SSH(config)

    def remote(self, script, **kwargs):
        return self.t.run('set -eu\n' + script, **kwargs)

    def hash(self, path):
        value = self.remote('sha256sum ' + Q(path)).split()[0]
        if not re.fullmatch('[a-f0-9]{64}', value):
            raise GuardError('Invalid remote hash: ' + path)
        return value

    def root_guard(self):
        if self.remote('id -u') != '0':
            raise GuardError('Root is not available')
        if self.hash(self.p['home_binary']) != self.p['home_binary_sha256']:
            raise GuardError('Home binary differs from the selected firmware profile')

    def mounted(self):
        return bool(self.remote('awk -v t=' + Q(self.p['target']) +
                                " '$5==t {print $0}' /proc/self/mountinfo"))

    def stock_guard(self):
        self.root_guard()
        if self.mounted():
            raise GuardError('A mount already covers MainView. Roll back or inspect it first')
        if self.hash(self.p['target']) != self.p['stock_qml_sha256']:
            raise GuardError('MainView differs from stock. Refusing to overwrite it')

    def owner_guard(self):
        if self.remote('cat ' + BASE + '/.webos-home-owner') != OWNER:
            raise GuardError('The remote directory is not owned by this tool')

    def receipt(self, action, data):
        data = {'time_utc': datetime.now(timezone.utc).isoformat(), **data}
        private_write(LOCAL / (action + '.json'), (json.dumps(data, indent=2) + '\n').encode())
        return data

    def check(self):
        self.root_guard()
        return {'root': True, 'profile': self.p['name'], 'home_binary_verified': True,
                'state': self.state()}

    def state(self):
        self.root_guard()
        return {'target_sha256': self.hash(self.p['target']), 'mounted': self.mounted(),
                'boot_enabled': self.remote('test -f ' + BASE + '/enabled && echo yes || echo no') == 'yes'}

    def backup(self):
        self.stock_guard()
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        directory = LOCAL / 'backups' / stamp
        home_dir = '/usr/palm/applications/com.webos.app.home'
        data = self.t.get('tar -czf - -C ' + Q(home_dir) + ' .', timeout=120)
        if not data:
            raise GuardError('Empty backup')
        private_write(directory / 'home-stock.tar.gz', data)
        stock = self.t.get('cat ' + Q(self.p['target']))
        if digest(stock) != self.p['stock_qml_sha256']:
            raise GuardError('Stock QML changed during backup')
        private_write(directory / 'MainView.stock.qml', stock)
        return self.receipt('backup', {'directory': str(directory.relative_to(ROOT)),
                                      'archive_sha256': digest(data),
                                      'stock_qml_sha256': digest(stock)})

    def backup_guard(self):
        receipt = json.loads((LOCAL / 'backup.json').read_text())
        directory = (ROOT / receipt['directory']).resolve()
        if not directory.is_relative_to((LOCAL / 'backups').resolve()):
            raise GuardError('Backup must be inside .local/backups')
        if digest((directory / 'home-stock.tar.gz').read_bytes()) != receipt['archive_sha256']:
            raise GuardError('Backup archive changed')
        if digest((directory / 'MainView.stock.qml').read_bytes()) != self.p['stock_qml_sha256']:
            raise GuardError('Backup QML differs from this firmware profile')

    def build(self):
        files = {}
        source = ROOT / 'native-home'
        for path in sorted(source.rglob('*')):
            if path.is_symlink():
                raise GuardError('Symlink in public source: ' + str(path))
            if path.is_file() and (path.suffix in ('.qml', '.js', '.png')):
                relative = path.relative_to(source).as_posix()
                files[relative] = path.read_bytes()
        if (LOCAL / 'Config.js').is_file():
            files['Config.js'] = (LOCAL / 'Config.js').read_bytes()
        if (LOCAL / 'characters.png').is_file():
            files['assets/sprites/characters.png'] = (LOCAL / 'characters.png').read_bytes()
        hashes = {name: digest(data) for name, data in files.items()}
        release = digest(json.dumps(hashes, sort_keys=True).encode())[:20]
        hook = self.boot_script(hashes, release).encode()
        build = LOCAL / 'build' / release
        for name, data in {**files, '20-native-home': hook}.items():
            private_write(build / name, data)
        manifest = {'release': release, 'files': hashes, 'hook_sha256': digest(hook),
                    'profile': self.p}
        private_write(build / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
        private_write(LOCAL / 'build.json', (json.dumps(manifest, indent=2) + '\n').encode())
        return manifest

    def current_build(self):
        manifest = json.loads((LOCAL / 'build.json').read_text())
        if not re.fullmatch('[a-f0-9]{20}', manifest['release']):
            raise GuardError('Invalid release identifier')
        if manifest['profile'] != self.p:
            raise GuardError('Build uses a different firmware profile')
        build = LOCAL / 'build' / manifest['release']
        for name, value in {**manifest['files'], '20-native-home': manifest['hook_sha256']}.items():
            if not re.fullmatch(r'[A-Za-z0-9_./-]+', name) or '..' in name.split('/'):
                raise GuardError('Invalid manifest path')
            if digest((build / name).read_bytes()) != value:
                raise GuardError('Build changed: ' + name + '. Run build again')
        return manifest, build

    def restart_script(self):
        # The tested firmware restarts Home through its own keep-alive policy.
        return '''for directory in /tmp/checkpoint/com.webos.app.home /mnt/lg/cmn_data/checkpoint/com.webos.app.home; do
    [ ! -d "$directory" ] || touch "$directory/invalid_img"
done
for p in /proc/[0-9]*; do
    [ "$(readlink "$p/exe" 2>/dev/null || true)" = /usr/bin/com.webos.app.home ] || continue
    kill -TERM "${p##*/}"
done
'''

    def boot_script(self, hashes, release):
        lines = ["#!/bin/sh", "# Generated by webos-home-v1. Firmware and build guards run before mounting.",
                 'set -eu', 'BASE=' + BASE, '[ -f "$BASE/enabled" ] || exit 0',
                 '[ "$(cat "$BASE/.webos-home-owner")" = ' + Q(OWNER) + ' ]',
                 '[ "$(readlink "$BASE/current")" = ' + Q('releases/' + release) + ' ]',
                 "sha256sum -c <<'WEBOS_HASHES'",
                 self.p['home_binary_sha256'] + '  ' + self.p['home_binary']]
        lines += [value + '  ' + BASE + '/current/' + name for name, value in hashes.items()]
        lines += ['WEBOS_HASHES', 'TARGET=' + Q(self.p['target']),
                  # Reject any existing mount, including a different version of this project.
                  "[ -z \"$(awk -v t=\"$TARGET\" '$5==t {print}' /proc/self/mountinfo)\" ]",
                  '[ "$(sha256sum "$TARGET" | cut -d " " -f1)" = ' +
                  Q(self.p['stock_qml_sha256']) + ' ]',
                  'mount --bind "$BASE/current/MainView.qml" "$TARGET"',
                  self.restart_script()]
        return '\n'.join(lines) + '\n'

    def stage(self):
        self.stock_guard()
        self.backup_guard()
        manifest, build = self.current_build()
        exists = self.remote('test -e ' + BASE + ' && echo yes || echo no') == 'yes'
        if exists:
            self.owner_guard()
            self.remote('rm -f ' + BASE + '/enabled ' + BASE + '/trial-active')
        else:
            self.remote('mkdir -m 755 ' + BASE)
            self.t.put((OWNER + '\n').encode(), BASE + '/.webos-home-owner')
        release_dir = BASE + '/releases/' + manifest['release']
        self.remote('mkdir -p ' + Q(release_dir) + '\nchmod 755 ' + BASE + '/releases ' + Q(release_dir))
        for name in [*manifest['files'], '20-native-home']:
            target = release_dir + '/' + name
            self.remote('mkdir -p ' + Q(str(Path(target).parent)) + '\nchmod 755 ' + Q(str(Path(target).parent)))
            self.t.put((build / name).read_bytes(), target)
            self.remote('chmod ' + ('755 ' if name == '20-native-home' else '644 ') + Q(target))
            if self.hash(target) != (manifest['files'].get(name) or manifest['hook_sha256']):
                raise GuardError('Upload differs: ' + name)
        self.remote('find ' + Q(release_dir) + ' -type d -exec chmod 755 {} ' + Q(';'))
        self.remote('ln -sfn ' + Q('releases/' + manifest['release']) + ' ' + BASE + '/current')
        for name in manifest['files']:
            if '/' not in name:
                self.remote('ln -sfn ' + Q('current/' + name) + ' ' + BASE + '/' + Q(name))
        self.remote('ln -sfn current/assets ' + BASE + '/assets')
        return self.receipt('stage', {'release': manifest['release'], 'files': manifest['files']})

    def staged_guard(self):
        self.owner_guard()
        manifest, _ = self.current_build()
        stage = json.loads((LOCAL / 'stage.json').read_text())
        if stage['release'] != manifest['release'] or stage['files'] != manifest['files']:
            raise GuardError('Build differs from staged release')
        if self.remote('readlink ' + BASE + '/current') != 'releases/' + manifest['release']:
            raise GuardError('Remote release changed')
        for name, value in manifest['files'].items():
            if self.hash(BASE + '/current/' + name) != value:
                raise GuardError('Remote build changed: ' + name)
        return manifest

    def owned_mount_guard(self, manifest):
        if not self.mounted():
            raise GuardError('No trial mount is active')
        if self.remote('test ' + Q(self.p['target']) + ' -ef ' + BASE + '/current/MainView.qml && echo yes || echo no') != 'yes':
            raise GuardError('The active mount belongs to another file')
        if self.hash(self.p['target']) != manifest['files']['MainView.qml']:
            raise GuardError('Mounted build changed')

    def rollback_script(self):
        target = Q(self.p['target'])
        return ('rm -f ' + BASE + '/enabled ' + BASE + '/trial-active\n'
                'if [ -n "$(awk -v t=' + target + " '$5==t {print}' /proc/self/mountinfo)" + '" ]; then\n'
                '  test ' + target + ' -ef ' + BASE + '/current/MainView.qml\n'
                '  umount ' + target + '\nfi\n'
                'test "$(sha256sum ' + target + ' | cut -d " " -f1)" = ' +
                Q(self.p['stock_qml_sha256']) + '\n' + self.restart_script())

    def trial(self):
        self.stock_guard()
        self.backup_guard()
        manifest = self.staged_guard()
        # Start the independent rollback timer before modifying the live mount.
        seconds = int(self.c.get('trial_seconds', 120))
        watchdog = ('set -eu\numask 077\ncommand -v sleep >/dev/null\necho "$$" > ' + BASE + '/trial-ready\n'
                    'i=0\nwhile [ "$i" -lt ' + str(seconds) + ' ]; do\n'
                    ' test -f ' + BASE + '/trial-active || exit 0\n sleep 1\n i=$((i + 1))\ndone\n'
                    'while ! mkdir ' + BASE + '/transition.lock 2>/dev/null; do\n'
                    ' test -f ' + BASE + '/trial-active || exit 0\n'
                    ' test ! -f ' + BASE + '/enabled || exit 0\n sleep 1\ndone\n'
                    "trap 'rmdir " + BASE + "/transition.lock' EXIT HUP INT TERM\n"
                    '[ ! -f ' + BASE + '/enabled ] || exit 0\n' + self.rollback_script())
        arm = ('rm -f ' + BASE + '/enabled ' + BASE + '/trial-ready\n'
               'touch ' + BASE + '/trial-active\nnohup sh -c ' + Q(watchdog) +
               ' >' + BASE + '/trial-watchdog.log 2>&1 </dev/null &\n'
               'watchdog_pid=$!\n'
               'for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do\n'
               ' if [ "$(cat ' + BASE + '/trial-ready 2>/dev/null || true)" = "$watchdog_pid" ] && kill -0 "$watchdog_pid" 2>/dev/null; then exit 0; fi\n'
               ' sleep 0.1\ndone\nrm -f ' + BASE + '/trial-active\n'
               'echo "Rollback watchdog did not become ready" >&2\nexit 1')
        self.remote(arm)
        try:
            self.remote('mount --bind ' + BASE + '/current/MainView.qml ' + Q(self.p['target']))
            self.owned_mount_guard(manifest)
            self.remote(self.restart_script())
        except BaseException:
            self.remote(self.rollback_script())
            raise
        return self.receipt('trial', {'release': manifest['release'], 'expires_after_seconds': seconds,
                                     'note': 'Verify appearance and remote controls before activation'})

    def activate(self, confirm_visual=False):
        if not confirm_visual:
            raise GuardError('Verify the live trial, then use activate --confirm-visual')
        self.root_guard()
        self.backup_guard()
        manifest = self.staged_guard()
        trial = json.loads((LOCAL / 'trial.json').read_text())
        if trial['release'] != manifest['release']:
            raise GuardError('No matching trial receipt')
        self.owned_mount_guard(manifest)
        staged_hook = BASE + '/current/20-native-home'
        if self.hash(staged_hook) != manifest['hook_sha256']:
            raise GuardError('Boot hook changed')
        exists = self.remote('test -e ' + HOOK + ' && echo yes || echo no') == 'yes'
        if exists and not (LOCAL / 'activate.json').is_file():
            raise GuardError('An existing boot hook has no ownership receipt')
        if exists:
            old = json.loads((LOCAL / 'activate.json').read_text())
            if self.hash(HOOK) != old['hook_sha256']:
                raise GuardError('Existing boot hook differs from the owned hook')
        self.remote('mkdir ' + BASE + '/transition.lock\n'
                    "trap 'rmdir " + BASE + "/transition.lock' EXIT HUP INT TERM\n"
                    'test -f ' + BASE + '/trial-active\n'
                    'test ' + Q(self.p['target']) + ' -ef ' + BASE + '/current/MainView.qml\n'
                    'test -d /var/lib/webosbrew/init.d\ncp ' + staged_hook + ' ' + HOOK +
                    '\nchmod 755 ' + HOOK + '\ntouch ' + BASE + '/enabled\nrm -f ' + BASE + '/trial-active')
        return self.receipt('activate', {'release': manifest['release'], 'hook_sha256': manifest['hook_sha256'],
                                        'visual_confirmed': True})

    def rollback(self):
        self.root_guard()
        self.owner_guard()
        # No dependency on local source or a changed candidate for recovery.
        self.remote(self.rollback_script())
        return self.receipt('rollback', {'stock_qml_sha256': self.hash(self.p['target']),
                                        'boot_enabled': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=LOCAL / 'config.json')
    parser.add_argument('action', choices=['check', 'state', 'backup', 'build', 'stage', 'trial', 'activate', 'rollback'])
    parser.add_argument('--confirm-visual', action='store_true')
    args = parser.parse_args()
    try:
        os.umask(0o077)
        home = Home(load_config(args.config))
        result = home.activate(args.confirm_visual) if args.action == 'activate' else getattr(home, args.action)()
        print(json.dumps(result, indent=2))
    except (GuardError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print('Stopped: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
