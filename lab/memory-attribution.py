#!/usr/bin/env python3
"""M8-F1 memory attribution controller derived from the frozen workload.

M8-F bridge controller. Consumes frozen M8-E; never boots or builds the target.

Run under a transient systemd unit so an SSH tool/session interruption cannot
terminate the qualification. A pilot is always labelled NOT a 24-hour soak.
Completion is provisional until independent evidence and leak review pass.
"""
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
M = runpy.run_path(str(HERE/'msd-hil.py'))
LAB = runpy.run_path(str(HERE/'labctl'))


def atomic(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n'); temp.replace(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--boot-result', type=Path, required=True)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--provenance', type=Path, required=True)
    p.add_argument('--expected-commit', default='6b2e4217df9d8e66950f960e1a6de6e5c4629e4d')
    p.add_argument('--observation-seconds', type=int, default=43200)
    p.add_argument('--release-seconds', type=int, default=900)
    a = p.parse_args()
    if a.observation_seconds != 43200 or not 600 <= a.release_seconds <= 900:
        p.error('M8-F1 requires 12 hours plus 10-15 minutes release observation')
    root = a.output.resolve(); root.mkdir(parents=True, exist_ok=False)
    seconds = a.observation_seconds + a.release_seconds
    result = {'result': 'failed', 'qualification': False, 'diagnostic': 'M8-F1', 'observation_seconds': a.observation_seconds, 'release_seconds': a.release_seconds,
              'required_seconds': seconds, 'atx': 'DEFERRED', 'events': [], 'cycles': []}
    children = []; source = None; off = None; uart = None
    uart_stop = threading.Event(); uart_errors = []
    h = None
    known = Path(json.loads(a.boot_result.read_text())['run_directory'])/'known_hosts'
    ssh = ['ssh', '-i', '/home/user/.local/share/blikvm-m7/id_ed25519', '-o', 'BatchMode=yes',
           '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
           '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile='+str(known), 'blikvm@192.168.88.2']

    def run(label, argv, stdin=None, timeout=60):
        with (root/(label+'.stdout')).open('w') as out, (root/(label+'.stderr')).open('w') as err:
            proc = subprocess.run(argv, input=stdin, text=True, stdout=out, stderr=err, timeout=timeout)
        if proc.returncode:
            raise RuntimeError(label+' exit '+str(proc.returncode))
        return (root/(label+'.stdout')).read_text()

    def target(label, code):
        return run(label, ssh+['sudo -n python3 -'], code)

    def spawn(label, argv):
        with (root/(label+'.log')).open('w') as log:
            proc = subprocess.Popen(argv, stdout=log, stderr=log)
        return proc

    def stop(proc):
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=5)

    def event_window(name, duration=60):
        value = {'event': name, 'id': name+'-'+str(time.monotonic_ns()),
                 'start': time.monotonic(), 'until': time.monotonic()+duration}
        atomic(root/'control.json', value)
        if name == 'startup':
            atomic(root/'startup-window.json', value)
        else:
            with (root/'lifecycle-windows.jsonl').open('a') as f:
                f.write(json.dumps(value)+'\n')
        return value

    def start_source(label):
        run('dpms-on-'+label, ['modetest', '-M', 'i915', '-w', f'{connector}:DPMS:0'])
        proc = spawn('hdmi-'+label, ['gst-launch-1.0', '-q', 'videotestsrc', 'is-live=true',
                    'pattern=ball', 'animation-mode=frames', '!',
                    'video/x-raw,width=1920,height=1080,framerate=30/1', '!', 'videoconvert', '!',
                    'kmssink', 'connector-id='+str(connector), 'force-modesetting=true', 'restore-crtc=true'])
        time.sleep(3)
        assert proc.poll() is None, 'HDMI source failed'
        return proc

    class Recorder:
        def log_uart(self, direction, data):
            if data:
                with (root/'uart.log').open('ab') as f:
                    f.write(data)
        def save_text(self, name, text):
            (root/name).write_text(text)

    def capture_uart():
        try:
            with LAB['SerialConsole'](Path('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'), Recorder()) as console:
                (root/'uart.log').touch()
                (root/'uart-monitor.json').write_text(json.dumps({'passive': True, 'started_monotonic': time.monotonic()}))
                while not uart_stop.is_set():
                    console.read_for(.2)
        except Exception as ex:
            uart_errors.append(str(ex))

    def resources(label):
        row = json.loads(target(label, "BASE_SOURCE = " + repr((HERE/'soak-resources.py').read_text()) + '\n' + (HERE/'memory-resources.py').read_text()))
        row['bridge_monotonic'] = time.monotonic()
        row['planned'] = json.loads((root/'control.json').read_text())['until'] > time.monotonic()
        row['completed_cycles'] = len(result['cycles'])
        with (root/'resources.jsonl').open('a') as f:
            f.write(json.dumps(row)+'\n')
        assert row['boot_id'] == result['boot_id'], 'target reboot during soak'
        assert row['failed_units']['rc'] == 0 and not row['failed_units']['stdout'].strip(), 'failed systemd unit'
        if not row['planned']:
            assert row['video_mode']['rc'] == 0
            for item in ('1920/1080', "'MJPG'", '30.000 (30/1)'):
                assert item in row['video_mode']['stdout'], 'device mode changed'
            streamers = [x for x in row['processes'] if x['comm'] == 'ustreamer']
            assert len(streamers) == 1, 'uStreamer ownership/count'
            assert any(x['pid'] == streamers[0]['ppid'] and x['comm'].startswith('kvmd') for x in row['processes'])
            assert row['streamer']['result']['stream']['clients'] == 2, 'two active video clients required'
            assert list(row['udc'].values()) == ['configured'], 'UDC not configured'
        main = next((p for p in row['processes'] if p['comm'].startswith('kvmd/main')), None)
        if not row['planned']:
            assert main and all('sample_error' not in p and not p.get('unavailable') for p in row['processes']) and not row.get('unavailable'), 'incomplete memory sample'
            identity = [main['pid'], main['start_ticks']]
            if not result['events']:
                assert identity == result.setdefault('observation_identity', identity), 'unexpected kvmd generation change'
            else:
                assert identity != result['observation_identity'], 'release restart did not change generation'
                assert identity == result.setdefault('release_identity', identity), 'extra kvmd restart'
        row['completed_cycles'] = len(result['cycles'])
        return row

    def direct_reads(label):
        h.ready(label)
        identity = M['G4']['block_identity'](M['G4']['wait_device'](True, 20))
        with (root/'reads.jsonl').open('a') as log:
            for i in range(3):
                fd = os.open(identity['node'], os.O_RDONLY | os.O_DIRECT)
                start = time.monotonic()
                try:
                    with mmap.mmap(-1, 8388608) as buffer:
                        size = os.readv(fd, [buffer])
                        digest = hashlib.sha256(buffer).hexdigest()
                finally:
                    os.close(fd)
                row = {'start': start, 'end': time.monotonic(), 'label': label, 'index': i,
                       'bytes': size, 'sha256': digest, 'identity': identity}
                log.write(json.dumps(row)+'\n'); log.flush()
                assert size == 8388608 and digest == M['IMAGE_HASH'], 'MSD whole-image mismatch'

    def cycle(index):
        label = f'cycle-{index:04d}'
        before = time.monotonic()
        h.client.login(); h.state(label+'-before', True); direct_reads(label+'-before')
        run(label+'-hid', [sys.executable, str(HERE/'hid-api-hil.py'), '--private-dir', 'private',
                          '--output', str(root/(label+'-hid')), '--keep-session'], timeout=90)
        h.client.login(); h.eject(label+'-eject')
        h.client.request('/msd/set_params', {'image': 'g4-storage.img', 'rw': 'false', 'cdrom': 'false'})
        h.client.request('/msd/set_connected', {'connected': 'true'})
        h.state(label+'-attached', True); direct_reads(label+'-attached')
        result['cycles'].append({'index': index, 'start': before, 'end': time.monotonic(), 'result': 'passed'})
        h.result['result'] = 'running'
        h.finish()

    try:
        availability = json.loads(target('required-interfaces', "import json,os\nfrom pathlib import Path\nprint(json.dumps({p:Path(p).exists() for p in ['/proc/self/smaps_rollup','/proc/slabinfo']}))\n"))
        assert all(availability.values()), 'required memory interfaces absent; no observation started'
        provenance = json.loads(a.provenance.read_text())
        assert provenance['baseline_tag'] == 'ubuntu-26.04.1-kvmd-msd-baseline'
        assert re.fullmatch(r'[0-9a-f]{40}', a.expected_commit), 'invalid expected source commit'
        assert provenance['commit'] == a.expected_commit, 'source provenance commit mismatch'
        for name, digest in provenance['automation_sha256'].items():
            assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == digest, 'automation hash mismatch: '+name
        shutil.copyfile(a.provenance, root/'provenance.json')
        shutil.copyfile(a.boot_result, root/'boot-reference.json')
        bootdir = Path(json.loads(a.boot_result.read_text())['run_directory'])
        shutil.copytree(bootdir, root/'boot-evidence')
        (root/'automation').mkdir()
        for path in HERE.iterdir():
            if path.is_file():
                shutil.copyfile(path, root/'automation'/path.name)
        manifest = json.loads((a.artifacts/'manifest.json').read_text())
        for name in ('Image', 'sun50i-h616-blikvm-v4.dtb', 'linux.config', 'initramfs.cpio.gz'):
            with (a.artifacts/name).open('rb') as f:
                assert hashlib.file_digest(f, 'sha256').hexdigest() == manifest['artifacts'][name]['sha256']
        shutil.copyfile(a.artifacts/'manifest.json', root/'frozen-artifacts.json')
        run('inventory-source', ssh+['sudo -n tee /run/m8e-hid-inventory.py'], (HERE/'hid-inventory.py').read_text())
        before = json.loads(target('inventory-before', (HERE/'msd-inventory.py').read_text()))
        assert before['result'] == 'passed', before.get('error')
        result['boot_id'] = before['boot_id']
        assert result['boot_id'] in (bootdir/'identity.log').read_text(), 'boot reference differs'
        target('privilege-before', (HERE/'msd-privilege-inventory.py').read_text())
        run('host-before', ['lsusb', '-t'])
        run('host-descriptors-before', ['lsusb', '-v', '-d', '1d6b:0106'])
        children.append(spawn('host-kernel-live', ['journalctl', '-k', '-f', '-n', '0', '-o', 'short-monotonic']))
        children.append(spawn('target-journal-live', ssh+['sudo -n journalctl -b -f -n 0 -o short-monotonic']))
        uart = threading.Thread(target=capture_uart, daemon=True); uart.start()
        connector = int(Path('/sys/class/drm/card0-HDMI-A-2/connector_id').read_text())
        connectors = run('hdmi-before', ['modetest', '-M', 'i915', '-c'])
        section = connectors.split(f'{connector}\t', 1)[1]
        dpms = int(re.search(r'\n\s*(\d+) DPMS:', section)[1])
        run('source-vt', ['chvt', '3']); source = start_source('initial')
        target('preparatory-inventory-before', (HERE/'msd-inventory.py').read_text())
        prep = {'start': time.monotonic(), 'authorized': True}
        run('preparatory-restart', ssh+['sudo -n systemctl restart kvmd'], timeout=45)
        prep['action_end'] = time.monotonic()
        result['preparatory_restart'] = prep
        time.sleep(5)
        target('preparatory-inventory-after', (HERE/'msd-inventory.py').read_text())
        h = M['Harness'](root/'msd', a.boot_result)
        h.state('soak-initial', True); direct_reads('initial')
        event_window('startup', 60)
        # Browser user can write only its evidence subdirectory. No private inputs are copied.
        ui = root/'ui'; ui.mkdir(); os.chmod(ui, 0o777)
        for name in ('control.json', 'stop'):
            (ui/name).symlink_to(root/name)
        video = spawn('video', [sys.executable, str(HERE/'soak-video.py'), '--output', str(root), '--private-dir', 'private'])
        browser = spawn('browser', ['runuser', '-u', 'user', '--', 'env',
            'NODE_EXTRA_CA_CERTS='+str(Path('private/ca.crt').resolve()),
            'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64',
            'PLAYWRIGHT_BROWSERS_PATH='+str(Path('out/kvmd-web/browser/browsers').resolve()),
            'xvfb-run', '-a', '-s', '-screen 0 1600x1200x24 -nolisten tcp',
            'node', str(HERE/'soak-browser.mjs'), str(Path('private').resolve()), str(ui)])
        children += [video, browser]
        deadline = time.monotonic()+55
        while not (root/'video-heartbeat.json').exists() or not (ui/'browser-heartbeat.json').exists():
            assert time.monotonic() < deadline and all(x.poll() is None for x in children), 'client startup failed'
            time.sleep(.5)
        # The qualification clock starts only after both authenticated clients are verified.
        atomic(root/'control.json', {'event': 'steady', 'id': 'steady', 'until': 0})
        (root/'lifecycle-windows.jsonl').touch()
        start = time.monotonic(); result.update(start_monotonic=start, start_utc=time.time(), result='running')
        resources('baseline')
        schedule = [(a.observation_seconds, 'kvmd')]
        result['schedule'] = schedule.copy()
        next_sample = start+60; next_cycle = start; index = 0
        while time.monotonic()-start < seconds:
            now = time.monotonic()
            assert not uart_errors, uart_errors
            assert all(x.poll() is None for x in children), 'soak child stopped'
            assert source.poll() is None, 'moving HDMI source stopped'
            for path in (root/'video-heartbeat.json', ui/'browser-heartbeat.json'):
                assert now-json.loads(path.read_text())['t'] < 65, 'client heartbeat lost: '+path.name
            if schedule and now-start >= schedule[0][0]:
                offset, name = schedule.pop(0)
                resources('release-before')
                target('release-inventory-before', (HERE/'msd-inventory.py').read_text())
                ev = event_window(name)
                if name in ('nginx', 'kvmd'):
                    run(f'event-{offset}-{name}', ssh+['sudo -n systemctl restart '+name], timeout=45)
                elif name == 'logout':
                    while not (ui/'browser-event.json').exists() or json.loads((ui/'browser-event.json').read_text())['id'] != ev['id']:
                        assert time.monotonic() < ev['until'], 'UI logout/relogin timeout'
                        assert browser.poll() is None, 'browser died during logout'
                        time.sleep(.2)
                else:
                    stop(source)
                    off = spawn(f'hdmi-off-{offset}', [sys.executable, str(HERE/'hdmi-off.py'), '--connector', str(connector), '--property', str(dpms)])
                    time.sleep(2); assert off.poll() is None
                    state = run(f'hdmi-off-state-{offset}', ['modetest', '-M', 'i915', '-c'])
                    assert 'value: 3' in state.split(f'{connector}\t', 1)[1].split('5 link-status', 1)[0]
                    time.sleep(10); stop(off); off = None; source = start_source(str(offset))
                ev['action_end'] = time.monotonic(); result['events'].append(ev)
                # Never change the declared deadline after a failure. Collect recovery continuously.
                next_cycle = max(next_cycle, ev['until']+5)
            if now >= next_sample:
                resources(f'sample-{int(now-start):06d}'); next_sample += 60
            if now >= next_cycle:
                cycle(index); index += 1; next_cycle = time.monotonic()+300
            result['elapsed_seconds'] = time.monotonic()-start
            atomic(root/'progress.json', result)
            time.sleep(.5)
        resources('final')
        assert len(result['events']) == 1 and result.get('release_identity'), 'release test incomplete'
        after = json.loads(target('inventory-after', (HERE/'msd-inventory.py').read_text()))
        assert after['result'] == 'passed' and after['boot_id'] == result['boot_id'], after.get('error')
        target('privilege-after', (HERE/'msd-privilege-inventory.py').read_text())
        result.update(result='completed_pending_independent_review', end_monotonic=time.monotonic(), end_utc=time.time())
    except Exception as ex:
        result.update(result='failed', error=str(ex), failure_monotonic=time.monotonic())
        # Archive first. No reboot, daemon repair, or retry-to-pass follows this failure.
        atomic(root/'failure.json', result)
        try:
            target('failure-state', "import subprocess\nfor c in [['dmesg'],['systemctl','--failed','--no-pager'],['journalctl','-b','--no-pager','-n','400']]:\n p=subprocess.run(c,capture_output=True,text=True);print(p.stdout,p.stderr)\n")
        except Exception as capture_error:
            result['failure_capture_error'] = str(capture_error)
    finally:
        (root/'stop').touch()
        for proc in children[-2:]:
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                stop(proc)
        for proc in children:
            stop(proc)
        stop(off); stop(source)
        uart_stop.set()
        if uart:
            uart.join(timeout=3)
        result['uart_errors'] = uart_errors
        if h:
            h.result['result'] = result['result']
            h.finish()
        if source is not None:
            subprocess.run(['chvt', '1'], capture_output=True)
        atomic(root/'result.json', result)
    return result['result'] == 'completed_pending_independent_review'


if __name__ == '__main__':
    raise SystemExit(not main())
