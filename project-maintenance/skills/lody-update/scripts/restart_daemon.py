#!/usr/bin/env python3
"""Restart an installed macOS cloud daemon; persist progress and verified results."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import time

ANSI = re.compile(r'\x1b\[[0-9;]*m')
RETRY_DELAYS = (2, 5)


def connected(status, machine):
    status = ANSI.sub('', status)
    fields = dict(re.findall(r'^\s*(Phase|Stage|Connectivity|Backend Auth|Backend Link|Machine ID|Workspaces):\s*(.*?)\s*$', status, re.M))
    backends = re.findall(r'^\s*Backend:\s*(\S+)', status, re.M)
    return ('Daemon is running' in status
            and all(fields.get(k) == v for k, v in {
                'Phase': 'running', 'Stage': 'ready', 'Connectivity': 'online',
                'Backend Auth': 'authorized', 'Backend Link': 'connected',
                'Machine ID': machine}.items())
            and fields.get('Workspaces', '').isdigit()
            and int(fields['Workspaces']) > 0
            and len(backends) == int(fields['Workspaces'])
            and all(x == 'connected' for x in backends))


def workspace_ids(status):
    return set(re.findall(r'^\s+ID:\s*(\S+)', ANSI.sub('', status), re.M))


def json_output(output):
    decoder = json.JSONDecoder()
    for match in re.finditer(r'(?m)^\s*\{', ANSI.sub('', output)):
        try:
            value, _ = decoder.raw_decode(ANSI.sub('', output)[match.end() - 1:])
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
    raise RuntimeError('Command did not return a JSON object')


class CommandFailure(RuntimeError):
    def __init__(self, command, code, output):
        self.output = output
        # Only explicit transient HTTP responses qualify; 401/403 never retry.
        statuses = re.findall(r'\bHTTP\s+(\d{3})\b|["\']?status["\']?\s*:\s*(\d{3})\b', output, re.I)
        codes = {int(a or b) for a, b in statuses}
        self.http_statuses = sorted(codes)
        self.retryable = bool(codes) and all(x in (408, 429) or 500 <= x <= 599 for x in codes)
        detail = ('; HTTP ' + ','.join(str(x) for x in self.http_statuses)) if codes else ''
        super().__init__(f'Command failed: {command[0]} exit {code}{detail}; see task.log')


def clean_env():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('LODY_SUPERVISOR_', 'LODY_ELECTRON_')) or key in {
            'ELECTRON_RUN_AS_NODE', 'LODY_SESSION_ID', 'LODY_WORKSPACE_SESSION_ID',
            'LODY_MCP_SESSION_ID', 'LODY_DAEMON_SUPERVISED'}:
            env.pop(key, None)
    return env


def package_root(entry, name):
    for parent in entry.resolve().parents:
        manifest = parent / 'package.json'
        if manifest.is_file() and json.loads(manifest.read_text()).get('name') == name:
            return parent
    raise RuntimeError(f'Cannot locate {name} package from stable launcher; inspect custom launchers manually')


def runtime_preflight(launcher, env, run):
    """Use npm's semver implementation; do not approximate Node engine ranges."""
    root = package_root(launcher, 'lody')
    manifest = json.loads((root / 'package.json').read_text())
    engine = manifest.get('engines', {}).get('node')
    if not engine:
        raise RuntimeError('Installed package has no Node engine contract')
    shebang = launcher.resolve().read_text().splitlines()[0]
    if shebang in ('#!/usr/bin/env node', '#!/usr/bin/env -S node'):
        node = shutil.which('node', path=env.get('PATH'))
    elif re.fullmatch(r'#!/[^\s]+/node', shebang):
        node = shebang[2:]
    else:
        raise RuntimeError('Unsupported launcher shebang; inspect its actual Node runtime manually')
    npm = shutil.which('npm', path=env.get('PATH'))
    if not node or not npm:
        raise RuntimeError('Node/npm missing from the launch environment')
    npm_root = package_root(Path(npm), 'npm')
    script = "const semver=require(require.resolve('semver',{paths:[process.argv[1]]}));console.log(JSON.stringify({node:process.versions.node,engine:process.argv[2],compatible:semver.satisfies(process.versions.node,process.argv[2])}));"
    result = json_output(run([node, '--eval', script, str(npm_root), engine], 15))
    if result.get('compatible') is not True:
        raise RuntimeError(f'Node {result.get("node")} does not satisfy {engine}; keep existing daemon running')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launcher', required=True, type=Path)
    p.add_argument('--version', required=True)
    p.add_argument('--machine-id', required=True)
    p.add_argument('--app', type=Path, default=Path('/Applications/Lody.app'))
    p.add_argument('--data-dir', type=Path, default=Path(os.environ.get('LODY_DATA_DIR', str(Path.home() / '.lody'))))
    p.add_argument('--task-dir', required=True, type=Path)
    p.add_argument('--ready-timeout', type=int, default=120)
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--detach', action='store_true')
    args = p.parse_args()
    if any(not path.is_absolute() for path in (args.task_dir, args.launcher, args.app, args.data_dir)):
        p.error('Use absolute paths')
    if args.ready_timeout < 0:
        p.error('ready-timeout must be non-negative')
    if sys.platform != 'darwin':
        p.error('This helper supports macOS only')
    if not args.launcher.is_file():
        p.error('Use an existing stable launcher')
    env = clean_env()
    env['LODY_DATA_DIR'] = str(args.data_dir)
    if args.detach:
        args.task_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        with (args.task_dir / 'task.log').open('ab') as log:
            command = [sys.executable, str(Path(__file__).resolve())] + [x for x in sys.argv[1:] if x != '--detach']
            child = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=log, start_new_session=True)
        (args.task_dir / 'task.pid').write_text(str(child.pid))
        print(json.dumps({'submitted': True, 'pid': child.pid, 'taskDir': str(args.task_dir)}))
        return 0
    args.task_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if any((args.task_dir / name).exists() for name in ('result.json', 'progress.json')):
        p.error('Use a fresh task directory; inspect the original task instead of resubmitting')
    result = {'ok': False, 'stage': 'dependency-preflight', 'targetVersion': args.version,
              'machineId': args.machine_id, 'cliInstalled': False, 'daemonVerified': False,
              'restartCompleted': False, 'startAttempts': 0, 'cloudPreflight': 'not-run',
              'operation': 'check' if args.check_only else 'restart'}
    reopen = False
    stopped = False
    expected_workspaces = set()
    executable = None
    app_info = {}

    def persist(name):
        path = args.task_dir / name
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        temp.replace(path)

    def stage(name):
        result['stage'] = name
        persist('progress.json')

    def run(command, timeout=90, check=True):
        command = [str(x) for x in command]
        r = subprocess.run(command, env=env, text=True, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        print(r.stdout, flush=True)
        if check and r.returncode:
            raise CommandFailure(command, r.returncode, r.stdout)
        return r.stdout

    def processes():
        out = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,command='], text=True)
        return {int(a): (int(b), c) for line in out.splitlines()
                for a, b, c in [line.strip().split(None, 2)]}

    def app_running():
        return any(cmd == executable for _, cmd in processes().values())

    def observe():
        status = run([args.launcher, 'daemon', 'status'], 15, check=False)
        procs = processes()
        try:
            record = json.loads((args.data_dir / 'run/daemon.json').read_text())
        except (OSError, ValueError):
            record = {}
        parent, command = procs.get(record.get('pid'), (None, ''))
        owner_command = procs.get(parent, (None, ''))[1]
        host_pid = re.search(r'^\s*PID:\s*(\d+)', ANSI.sub('', status), re.M)
        standalone = ('Daemon is running' in status and host_pid is not None
                      and int(host_pid[1]) == parent and 'lody' in command
                      and re.search(r'\bstart(?:\s|$)', command) is not None
                      and re.search(r'\bdaemon-runner(?:\s|$)', owner_command) is not None)
        owner = 'standalone' if standalone else ('electron' if 'Local agent Host: electron' in status else 'unknown')
        absent = ('Daemon is not running' in status and 'Local agent Host:' not in status
                  and 'orphan' not in status.lower() and record.get('pid') not in procs)
        healthy = bool(standalone and connected(status, args.machine_id)
                       and workspace_ids(status) == expected_workspaces)
        return {'owner': owner, 'healthy': healthy, 'absent': absent,
                'targetVersion': record.get('version') == args.version,
                'runtime': record, 'status': status}

    def verify():
        observation = observe()
        if not observation['healthy'] or not observation['targetVersion']:
            raise RuntimeError('Runtime version, ownership or connectivity is not ready')
        return observation['runtime']

    def await_ready():
        deadline = time.monotonic() + args.ready_timeout
        while True:
            try:
                return verify()
            except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Readiness deadline exceeded: ' + str(error)) from error
                time.sleep(2)

    def retry_read(command):
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                return run(command, 30)
            except CommandFailure as error:
                if not error.retryable or attempt == len(RETRY_DELAYS):
                    raise
                print(f'Transient preflight failure; retry {attempt + 1}', flush=True)
                time.sleep(RETRY_DELAYS[attempt])

    def start_daemon():
        for attempt in range(len(RETRY_DELAYS) + 1):
            observation = observe()
            if observation['owner'] == 'standalone':
                # A previous start may have been accepted despite a failing command.
                stage('verify-daemon')
                return await_ready()
            if not observation['absent']:
                raise RuntimeError('Local Host is occupied or ownership is uncertain; no duplicate start attempted')
            result['startAttempts'] += 1
            persist('progress.json')
            try:
                run([args.launcher, 'daemon', 'start'])
                stage('verify-daemon')
                return await_ready()
            except CommandFailure as error:
                observation = observe()
                if observation['owner'] == 'standalone':
                    stage('verify-daemon')
                    return await_ready()
                if not observation['absent']:
                    raise RuntimeError('Host appeared during failed start; inspect its owner before recovery') from error
                if not error.retryable or attempt == len(RETRY_DELAYS):
                    raise
                print(f'Transient start failure; retry {attempt + 1}', flush=True)
                time.sleep(RETRY_DELAYS[attempt])

    try:
        stage('dependency-preflight')
        manifest = json.loads((package_root(args.launcher, 'lody') / 'package.json').read_text())
        result['cliInstalled'] = manifest.get('version') == args.version
        if not result['cliInstalled']:
            raise RuntimeError('Installed package does not match target version')
        result['runtimeEnvironment'] = runtime_preflight(args.launcher, env, run)
        installed = ANSI.sub('', run([args.launcher, '--version'])).splitlines()
        if args.version not in installed:
            raise RuntimeError('Installed CLI does not match target version')
        result['cliInstalled'] = True
        if args.app.exists():
            with (args.app / 'Contents/Info.plist').open('rb') as f:
                app_info = plistlib.load(f)
            executable = str(args.app / 'Contents/MacOS' / app_info['CFBundleExecutable'])
        stage('service-preflight')
        initial = run([args.launcher, 'daemon', 'status'])
        expected_workspaces = workspace_ids(initial)
        if not expected_workspaces or not connected(initial, args.machine_id):
            raise RuntimeError('Initial machine/connection must be verified before restarting')
        initial_owner = observe()
        if not initial_owner['healthy']:
            raise RuntimeError('This helper requires a verified existing standalone daemon')
        if not args.check_only:
            result['cloudPreflight'] = 'checking'
            stage('cloud-preflight')
            # Public, read-only command using this CLI's own credentials, not the old daemon.
            cloud = json_output(retry_read([args.launcher, 'workspace', 'list', '--json']))
            cloud_ids = {x['id'] for x in cloud.get('workspaces', []) if isinstance(x, dict) and 'id' in x}
            if cloud.get('ok') is not True or not expected_workspaces.issubset(cloud_ids):
                raise RuntimeError('Target CLI cannot read the original workspaces; preserve existing service')
            result['cloudPreflight'] = 'workspace-read-passed'
            # This read reduces risk; daemon start still validates its own auth endpoint.
            reopen = app_running()
            result['desktopWasRunning'] = reopen
            if reopen:
                stage('quit-desktop')
                run(['osascript', '-e', 'tell application id ' + json.dumps(app_info['CFBundleIdentifier']) + ' to quit'], 30)
                deadline = time.monotonic() + 45
                while app_running() and time.monotonic() < deadline:
                    time.sleep(1)
                if app_running():
                    raise RuntimeError('Desktop did not exit; existing daemon preserved')
            stage('stop-daemon')
            run([args.launcher, 'daemon', 'stop'])
            stopped = True
            stage('start-daemon')
            record = start_daemon()
            result['restartCompleted'] = True
        else:
            stage('verify-daemon')
            record = await_ready()
        result['daemonVerified'] = True
        result['runtime'] = record
        if reopen:
            stage('reopen-desktop')
            run(['open', '-a', args.app], 30)
            deadline = time.monotonic() + 30
            while not app_running() and time.monotonic() < deadline:
                time.sleep(1)
            if not app_running():
                raise RuntimeError('Desktop did not reopen')
            stage('verify-after-reopen')
            result['daemonVerified'] = False
            result['runtime'] = await_ready()
            result['daemonVerified'] = True
        if args.app.exists():
            with (args.app / 'Contents/Info.plist').open('rb') as f:
                result['desktopVersion'] = plistlib.load(f).get('CFBundleShortVersionString')
        result.update(ok=True, stage='complete')
    except Exception as error:
        if result['stage'] == 'cloud-preflight':
            result['cloudPreflight'] = 'failed'
        result['error'] = str(error)
        result['retryable'] = isinstance(error, CommandFailure) and error.retryable
        if isinstance(error, CommandFailure):
            result['httpStatuses'] = error.http_statuses
        result['oldDaemonStopCompleted'] = stopped
        recovery = {}
        # Re-observe health even when the original command failed or timed out.
        if expected_workspaces:
            try:
                before = observe()
                recovery.update(owner=before['owner'], daemonHealthy=before['healthy'],
                                atTargetVersion=before['targetVersion'], runtime=before['runtime'])
            except Exception as observation_error:
                recovery['observationError'] = str(observation_error)
        if reopen:
            try:
                if not app_running():
                    run(['open', '-a', args.app], 30)
                recovery['desktopOpenRequested'] = True
                after = observe()
                recovery.update(owner=after['owner'], daemonHealthy=after['healthy'],
                                atTargetVersion=after['targetVersion'], runtime=after['runtime'])
            except Exception as recovery_error:
                recovery['desktopError'] = str(recovery_error)
        result['recovery'] = recovery
        # Recovery is a snapshot, not proof of successful upgrade or rollback.
    persist('progress.json')
    persist('result.json')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
