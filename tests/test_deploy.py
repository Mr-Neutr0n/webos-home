import copy
import importlib.util
import json
from pathlib import Path
import shutil
import shlex
import os
import threading
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location('webos', Path(__file__).parents[1] / 'scripts/webos.py')
w = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w)
SOURCE_ROOT = w.ROOT
CONFIG = json.loads((SOURCE_ROOT / 'config.example.json').read_text())


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(SOURCE_ROOT / 'native-home', self.root / 'native-home')
        self.patches = [patch.object(w, 'ROOT', self.root), patch.object(w, 'LOCAL', self.root / '.local')]
        for p in self.patches:
            p.start()
        self.transport = Mock()
        self.home = w.Home(copy.deepcopy(CONFIG), self.transport)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_stock_guard_rejects_wrong_binary_before_any_write(self):
        self.home.remote = Mock(return_value='0')
        self.home.hash = Mock(return_value='0' * 64)
        with self.assertRaisesRegex(w.GuardError, 'binary differs'):
            self.home.stock_guard()
        self.assertEqual(len(self.home.remote.call_args_list), 1)
        self.transport.put.assert_not_called()

    def test_stock_guard_rejects_existing_mount(self):
        self.home.root_guard = Mock()
        self.home.mounted = Mock(return_value=True)
        self.home.hash = Mock()
        with self.assertRaisesRegex(w.GuardError, 'mount already'):
            self.home.stock_guard()
        self.home.hash.assert_not_called()

    def test_stock_guard_rejects_changed_stock_qml(self):
        self.home.root_guard = Mock()
        self.home.mounted = Mock(return_value=False)
        self.home.hash = Mock(return_value='a' * 64)
        with self.assertRaisesRegex(w.GuardError, 'differs from stock'):
            self.home.stock_guard()

    def test_backup_guard_rejects_missing_or_changed_backup(self):
        with self.assertRaises(FileNotFoundError):
            self.home.backup_guard()
        backup = self.root / '.local/backups/example'
        backup.mkdir(parents=True)
        (backup / 'home-stock.tar.gz').write_bytes(b'changed')
        (self.root / '.local/backup.json').write_text(json.dumps({
            'directory': '.local/backups/example', 'archive_sha256': 'a' * 64}))
        with self.assertRaisesRegex(w.GuardError, 'archive changed'):
            self.home.backup_guard()

    def test_build_verifies_every_source_and_hook(self):
        manifest = self.home.build()
        loaded, build = self.home.current_build()
        self.assertEqual(manifest, loaded)
        self.assertIn('Config.js', manifest['files'])
        self.assertIn('assets/sprites/characters.png', manifest['files'])
        subprocess.run(['sh', '-n', str(build / '20-native-home')], check=True)
        hook = (build / '20-native-home').read_text()
        self.assertIn(CONFIG['profile']['home_binary_sha256'], hook)
        self.assertIn(CONFIG['profile']['stock_qml_sha256'], hook)
        for name, sha in manifest['files'].items():
            self.assertIn(sha + '  ' + w.BASE + '/current/' + name, hook)
        (build / 'RoomScene.qml').write_text('changed')
        with self.assertRaisesRegex(w.GuardError, 'Build changed'):
            self.home.current_build()

    def test_local_personalization_changes_release(self):
        first = self.home.build()
        (self.root / '.local/Config.js').write_text('.pragma library\nvar quoteText = "Local";\n')
        second = self.home.build()
        self.assertNotEqual(first['release'], second['release'])
        self.assertNotEqual(first['files']['Config.js'], second['files']['Config.js'])
        self.assertEqual((self.root / 'native-home/Config.js').read_text(),
                         (SOURCE_ROOT / 'native-home/Config.js').read_text())

    def test_stage_rejects_backup_failure_before_upload(self):
        self.home.stock_guard = Mock()
        self.home.backup_guard = Mock(side_effect=w.GuardError('backup missing'))
        with self.assertRaisesRegex(w.GuardError, 'backup missing'):
            self.home.stage()
        self.transport.put.assert_not_called()

    def prepare_trial(self):
        self.home.stock_guard = Mock()
        self.home.backup_guard = Mock()
        self.home.staged_guard = Mock(return_value={'release': 'b' * 20})
        self.home.owned_mount_guard = Mock()
        self.home.remote = Mock(return_value='')

    def test_trial_arms_watchdog_before_mount(self):
        self.prepare_trial()
        result = self.home.trial()
        commands = [call.args[0] for call in self.home.remote.call_args_list]
        self.assertIn('nohup sh -c', commands[0])
        self.assertIn('sleep 1', commands[0])
        self.assertIn('transition.lock', commands[0])
        self.assertTrue(commands[1].startswith('mount --bind'))
        self.assertEqual(result['expires_after_seconds'], 120)
        self.assertTrue((self.root / '.local/trial.json').is_file())

    def test_trial_rolls_back_when_post_mount_validation_fails(self):
        self.prepare_trial()
        self.home.owned_mount_guard.side_effect = w.GuardError('wrong mounted file')
        with self.assertRaisesRegex(w.GuardError, 'wrong mounted file'):
            self.home.trial()
        commands = [call.args[0] for call in self.home.remote.call_args_list]
        self.assertEqual(commands[-1], self.home.rollback_script())
        self.assertIn('umount ', commands[-1])
        self.assertFalse((self.root / '.local/trial.json').exists())

    def test_no_mount_when_watchdog_start_fails(self):
        self.prepare_trial()
        self.home.remote.side_effect = w.GuardError('watchdog failed')
        with self.assertRaisesRegex(w.GuardError, 'watchdog failed'):
            self.home.trial()
        self.assertEqual(self.home.remote.call_count, 1)
        self.home.owned_mount_guard.assert_not_called()

    def test_shell_watchdog_rejects_missing_background_executable(self):
        self.prepare_trial()
        self.home.trial()
        remote_dir = self.root / 'remote'
        remote_dir.mkdir()
        arm = self.home.remote.call_args_list[0].args[0].replace(w.BASE, str(remote_dir))
        arm = arm.replace('nohup sh -c', 'missing-webos-nohup sh -c')
        result = subprocess.run(['sh', '-c', 'set -eu\n' + arm], capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Rollback watchdog did not become ready', result.stderr)
        self.assertFalse((remote_dir / 'trial-active').exists())

    def test_shell_watchdog_recovers_after_failed_activation_releases_lock(self):
        self.prepare_trial()
        remote_dir = self.root / 'remote'
        remote_dir.mkdir()
        marker = remote_dir / 'recovered'
        self.home.rollback_script = Mock(return_value='touch ' + str(marker))
        self.home.trial()
        arm = self.home.remote.call_args_list[0].args[0]
        tokens = shlex.split(arm)
        watchdog = tokens[tokens.index('nohup') + 3].replace(w.BASE, str(remote_dir))
        # A fake clock completes the bounded trial without waiting thirty seconds.
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        sleeper = bin_dir / 'sleep'
        sleeper.write_text('#!/bin/sh\nexit 0\n')
        sleeper.chmod(0o755)
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
        (remote_dir / 'trial-active').touch()
        lock = remote_dir / 'transition.lock'
        lock.mkdir()
        timer = threading.Timer(0.1, lock.rmdir)
        timer.start()
        try:
            subprocess.run(['sh', '-c', watchdog], check=True, env=env, timeout=5)
        finally:
            timer.join()
        self.assertTrue(marker.is_file())
        self.assertFalse(lock.exists())

    def test_activation_requires_explicit_visual_check(self):
        self.home.root_guard = Mock()
        with self.assertRaisesRegex(w.GuardError, 'confirm-visual'):
            self.home.activate()
        self.home.root_guard.assert_not_called()

    def test_activation_rejects_unowned_boot_hook(self):
        self.home.root_guard = Mock()
        self.home.backup_guard = Mock()
        manifest = {'release': 'a' * 20, 'hook_sha256': 'b' * 64}
        self.home.staged_guard = Mock(return_value=manifest)
        self.home.owned_mount_guard = Mock()
        self.home.hash = Mock(return_value='b' * 64)
        self.home.remote = Mock(return_value='yes')
        w.private_write(self.root / '.local/trial.json', json.dumps({'release': 'a' * 20}).encode())
        with self.assertRaisesRegex(w.GuardError, 'ownership receipt'):
            self.home.activate(True)
        self.assertFalse(any('cp ' in call.args[0] for call in self.home.remote.call_args_list))

    def test_rollback_works_without_local_build(self):
        self.home.root_guard = Mock()
        self.home.owner_guard = Mock()
        self.home.remote = Mock(return_value='')
        self.home.hash = Mock(return_value=CONFIG['profile']['stock_qml_sha256'])
        result = self.home.rollback()
        command = self.home.remote.call_args.args[0]
        self.assertIn('/enabled', command)
        self.assertIn(' -ef ', command)
        self.assertIn('umount ', command)
        self.assertFalse(result['boot_enabled'])
        self.assertFalse((self.root / '.local/build.json').exists())

    def test_rollback_refuses_foreign_mount(self):
        self.home.root_guard = Mock()
        self.home.owner_guard = Mock()
        self.home.remote = Mock(side_effect=w.GuardError('foreign inode'))
        with self.assertRaisesRegex(w.GuardError, 'foreign inode'):
            self.home.rollback()
        self.assertFalse((self.root / '.local/rollback.json').exists())

    def test_ssh_host_validation_and_strict_keys(self):
        config = copy.deepcopy(CONFIG)
        config['ssh']['host'] = '-oProxyCommand=anything'
        with self.assertRaises(w.GuardError):
            w.SSH(config)
        args = w.SSH(CONFIG).args
        self.assertIn('StrictHostKeyChecking=yes', args)
        self.assertIn('BatchMode=yes', args)
        self.assertIn('IdentitiesOnly=yes', args)

    def test_profile_rejects_unknown_paths(self):
        config = copy.deepcopy(CONFIG)
        config['profile']['target'] = '/etc/passwd'
        file = self.root / 'config.json'
        file.write_text(json.dumps(config))
        with self.assertRaisesRegex(w.GuardError, 'documented native Home paths'):
            w.load_config(file)


if __name__ == '__main__':
    unittest.main()
