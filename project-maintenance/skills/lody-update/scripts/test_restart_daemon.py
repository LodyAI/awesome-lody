"""Behavioral checks with synthetic files, injected clocks, and no live services."""
import contextlib
import io
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import restart_daemon as helper

STATUS = '''Daemon is running
 PID: 1
 Phase: running
 Stage: ready
 Connectivity: online
 Backend Auth: authorized
 Backend Link: connected
 Workspaces: 1
   ID: workspace
   Backend: connected
 Machine ID: machine
'''
TARGET = '2.0.0'
OLD = '1.0.0'


class RestartTests(unittest.TestCase):
    def test_connection_requires_all_evidence(self):
        self.assertTrue(helper.connected(STATUS, 'machine'))
        for text in (STATUS.replace('authorized', 'pending'),
                     STATUS.replace('Backend: connected', 'Backend: disconnected'),
                     STATUS.replace('Workspaces: 1', 'Workspaces: 2'),
                     STATUS.replace('Stage: ready', ''),
                     STATUS.replace('Machine ID: machine', 'Machine ID: other')):
            self.assertFalse(helper.connected(text, 'machine'))

    def scenario(self, starts=(), cloud_failures=(), fail_quit=False, bad_node=False,
                 after_open_status=None, fail_open=False, collision=False,
                 wrong_machine=False, check_only=False, wrong_parent=False,
                 app_initial=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = root / 'lody'
            launcher.touch()
            (root / 'package.json').write_text(json.dumps({'name': 'lody', 'version': TARGET}))
            app = root / 'Lody.app'
            (app / 'Contents').mkdir(parents=True)
            info = {'CFBundleExecutable': 'Lody', 'CFBundleIdentifier': 'test.lody',
                    'CFBundleShortVersionString': OLD}
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
            (root / 'run').mkdir()
            state = {'app': app_initial, 'owner': 'standalone', 'version': TARGET if check_only else OLD,
                     'reopened': False, 'startAttempts': 0, 'stopCompleted': False}
            def write_record(pid=2):
                (root / 'run/daemon.json').write_text(json.dumps({'pid': pid, 'version': state['version']}))
            write_record()
            start_results = list(starts)
            cloud_results = list(cloud_failures)
            def status():
                if state['owner'] == 'standalone':
                    text = after_open_status if state['reopened'] and after_open_status is not None else STATUS
                    return text.replace('Machine ID: machine', 'Machine ID: other') if wrong_machine else text
                if state['owner'] == 'electron':
                    return 'Daemon is not running\n Local agent Host: electron process 3\n'
                return 'Daemon is not running\n'
            def run(command, **kwargs):
                command = [str(x) for x in command]
                output, code = '', 0
                if command[-1] == '--version':
                    output = TARGET + '\n'
                elif command[-2:] == ['daemon', 'status']:
                    output = status()
                    code = 0 if state['owner'] == 'standalone' else 1
                elif command[-3:] == ['workspace', 'list', '--json']:
                    failure = cloud_results.pop(0) if cloud_results else None
                    if failure:
                        code, output = 1, f'HTTP {failure}: synthetic backend failure'
                    else:
                        output = json.dumps({'ok': True, 'workspaces': [{'id': 'workspace'}]})
                elif command[-2:] == ['daemon', 'stop']:
                    state.update(owner='none', stopCompleted=True)
                elif command[-2:] == ['daemon', 'start']:
                    state['startAttempts'] += 1
                    outcome = start_results.pop(0) if start_results else 'ok'
                    if outcome in ('ok', 'accepted-error'):
                        state.update(owner='standalone', version=TARGET)
                        write_record()
                    if outcome == 'collision' or (collision and outcome != 'ok'):
                        state.update(owner='electron', app=True)
                        write_record(4)
                    if outcome != 'ok':
                        code = 1
                        output = f'CLI token validation request failed: HTTP {401 if outcome == "unauthorized" else 500}; retryable: true'
                elif command[0] == 'osascript':
                    code = 1 if fail_quit else 0
                    if not code:
                        state['app'] = False
                elif command[0] == 'open':
                    code = 1 if fail_open else 0
                    if not code:
                        state.update(app=True, reopened=True)
                        info['CFBundleShortVersionString'] = TARGET
                        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
                        # Desktop autostarts its embedded runtime only when no daemon owns Host.
                        if state['owner'] == 'none':
                            state.update(owner='electron', version=TARGET)
                            write_record(4)
                else:
                    raise AssertionError('Unexpected command (including chat/probe): ' + ' '.join(command))
                return subprocess.CompletedProcess(command, code, output)
            def ps(*args, **kwargs):
                text = ''
                if state['owner'] == 'standalone':
                    text += '1 0 node /prefix/bin/lody daemon-runner\n'
                    text += f'2 {9 if wrong_parent else 1} node /prefix/bin/lody start\n'
                if state['app']:
                    text += f'3 0 {app}/Contents/MacOS/Lody\n'
                if state['owner'] == 'electron':
                    text += '4 3 Lody Helper /resources/cli/index.js start\n'
                return text
            def dependency_check(*args):
                if bad_node:
                    raise RuntimeError('Node does not satisfy installed engines.node')
                return {'node': '26.12.1', 'engine': '>=26.12.1 <27', 'compatible': True}
            argv = ['restart', '--launcher', str(launcher), '--version', TARGET,
                    '--machine-id', 'machine', '--app', str(app), '--data-dir', str(root),
                    '--task-dir', str(root / 'task'), '--ready-timeout', '0']
            if check_only:
                argv.append('--check-only')
            clock = iter(range(1000))
            with patch.object(sys, 'argv', argv), patch.object(sys, 'platform', 'darwin'), \
                 patch.object(helper, 'runtime_preflight', dependency_check), \
                 patch.object(helper.subprocess, 'run', run), patch.object(helper.subprocess, 'check_output', ps), \
                 patch.object(helper.time, 'sleep'), patch.object(helper.time, 'monotonic', lambda: next(clock)), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = helper.main()
            result = json.loads((root / 'task/result.json').read_text())
            progress = json.loads((root / 'task/progress.json').read_text())
            self.assertEqual(result, progress)
            return code, result, state

    def test_restart_verifies_new_daemon_after_desktop_reopens(self):
        code, result, state = self.scenario()
        self.assertEqual(code, 0)
        self.assertTrue(result['ok'] and result['daemonVerified'] and result['restartCompleted'])
        self.assertEqual(result['runtime']['version'], TARGET)
        self.assertEqual(result['desktopVersion'], TARGET)
        self.assertEqual(state['owner'], 'standalone')
        self.assertTrue(state['app'] and state['stopCompleted'])

    def test_dependency_or_preflight_failure_preserves_existing_service(self):
        for kwargs, stage in [({'bad_node': True}, 'dependency-preflight'),
                              ({'cloud_failures': [500, 500, 500]}, 'cloud-preflight'),
                              ({'wrong_machine': True}, 'service-preflight'),
                              ({'wrong_parent': True}, 'service-preflight'),
                              ({'fail_quit': True}, 'quit-desktop')]:
            with self.subTest(stage=stage):
                code, result, state = self.scenario(**kwargs)
                self.assertEqual(code, 1)
                self.assertEqual(result['stage'], stage)
                self.assertEqual(state['version'], OLD)
                self.assertEqual(state['owner'], 'standalone')
                self.assertFalse(state['stopCompleted'])
                self.assertTrue(state['app'])
                if kwargs.get('bad_node'):
                    self.assertTrue(result['cliInstalled'])

    def test_transient_preflight_failure_can_recover_before_stopping(self):
        code, result, state = self.scenario(cloud_failures=[500])
        self.assertEqual(code, 0)
        self.assertEqual(result['cloudPreflight'], 'workspace-read-passed')
        self.assertEqual(state['version'], TARGET)

    def test_start_retries_transient_failure_and_keeps_independent_ownership(self):
        code, result, state = self.scenario(starts=['transient', 'ok'])
        self.assertEqual(code, 0)
        self.assertEqual(result['startAttempts'], 2)
        self.assertEqual(state['owner'], 'standalone')
        self.assertTrue(result['daemonVerified'])

    def test_closed_desktop_stays_closed_after_successful_upgrade(self):
        code, result, state = self.scenario(app_initial=False)
        self.assertEqual(code, 0)
        self.assertFalse(state['app'])
        self.assertTrue(result['daemonVerified'])
        self.assertEqual(result['desktopVersion'], OLD)

    def test_accepted_start_is_observed_without_duplicate_start(self):
        code, result, state = self.scenario(starts=['accepted-error'])
        self.assertEqual(code, 0)
        self.assertEqual(state['startAttempts'], 1)
        self.assertTrue(result['daemonVerified'])

    def test_auth_rejection_does_not_retry_or_claim_desktop_recovery_is_upgrade(self):
        code, result, state = self.scenario(starts=['unauthorized'])
        self.assertEqual(code, 1)
        self.assertEqual(result['startAttempts'], 1)
        self.assertFalse(result['ok'] or result['daemonVerified'])
        self.assertEqual(result['recovery']['owner'], 'electron')
        self.assertFalse(result['recovery']['daemonHealthy'])
        self.assertTrue(state['app'])

    def test_exhausted_retry_reports_missing_daemon_and_actual_recovery_owner(self):
        code, result, state = self.scenario(starts=['transient'] * 3)
        self.assertEqual(code, 1)
        self.assertEqual(state['startAttempts'], 3)
        self.assertTrue(result['retryable'])
        self.assertEqual(result['httpStatuses'], [500])
        self.assertFalse(result['restartCompleted'])
        self.assertEqual(result['recovery']['owner'], 'electron')
        self.assertTrue(state['stopCompleted'])

    def test_host_collision_stops_retries(self):
        code, result, state = self.scenario(starts=['collision'])
        self.assertEqual(code, 1)
        self.assertEqual(state['startAttempts'], 1)
        self.assertEqual(result['recovery']['owner'], 'electron')
        self.assertFalse(result['ok'])

    def test_lost_connection_or_workspace_after_open_is_not_success(self):
        for text in (STATUS.replace('Backend: connected', 'Backend: disconnected'),
                     STATUS.replace('ID: workspace', 'ID: different')):
            code, result, state = self.scenario(after_open_status=text)
            self.assertEqual(code, 1)
            self.assertEqual(result['stage'], 'verify-after-reopen')
            self.assertTrue(result['restartCompleted'])
            self.assertFalse(result['daemonVerified'])
            self.assertFalse(result['recovery']['daemonHealthy'])
            self.assertEqual(state['startAttempts'], 1)

    def test_desktop_open_failure_preserves_and_reports_healthy_daemon(self):
        code, result, state = self.scenario(fail_open=True)
        self.assertEqual(code, 1)
        self.assertEqual(result['stage'], 'reopen-desktop')
        self.assertTrue(result['daemonVerified'])
        self.assertTrue(result['recovery']['daemonHealthy'])
        self.assertEqual(state['owner'], 'standalone')

    def test_check_only_does_not_restart_or_test_chat(self):
        code, result, state = self.scenario(check_only=True)
        self.assertEqual(code, 0)
        self.assertFalse(state['stopCompleted'])
        self.assertEqual(state['startAttempts'], 0)
        self.assertEqual(result['cloudPreflight'], 'not-run')
        self.assertFalse(result['restartCompleted'])
        self.assertTrue(result['daemonVerified'])

    def test_http_classifier_retries_only_explicit_transient_responses(self):
        for text in ('HTTP 500', 'status: 503', '"status": 429'):
            self.assertTrue(helper.CommandFailure(['lody'], 1, text).retryable)
        for text in ('HTTP 401; retryable: true', 'HTTP 403', 'exit 1', 'HTTP 500 then HTTP 401'):
            self.assertFalse(helper.CommandFailure(['lody'], 1, text).retryable)

    def test_runtime_preflight_rejects_unsupported_node_before_service_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lody = root / 'lody'
            (lody / 'dist').mkdir(parents=True)
            entry = lody / 'dist/index.js'
            entry.write_text('#!/usr/bin/env node\n')
            (lody / 'package.json').write_text(json.dumps({'name': 'lody', 'engines': {'node': '>=26.12.1 <27'}}))
            npm = root / 'npm'
            (npm / 'bin').mkdir(parents=True)
            npm_entry = npm / 'bin/npm-cli.js'
            npm_entry.touch()
            (npm / 'package.json').write_text(json.dumps({'name': 'npm'}))
            def run(*args):
                return json.dumps({'node': '26.8.2', 'compatible': False})
            def which(name, **kwargs):
                return str(npm_entry) if name == 'npm' else '/synthetic/node'
            with patch.object(helper.shutil, 'which', which):
                with self.assertRaisesRegex(RuntimeError, 'does not satisfy'):
                    helper.runtime_preflight(entry, {}, run)


if __name__ == '__main__':
    unittest.main()
