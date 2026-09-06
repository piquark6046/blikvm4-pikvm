#!/usr/bin/env python3
"""M7.5 bridge qualification: real MJPEG, source interruption and frozen M5."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
from pathlib import Path
import runpy
import re
import sys
import shlex
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
LAB = runpy.run_path(str(HERE/'labctl'))
G4 = runpy.run_path(str(HERE/'storagelab.py'))
CLIENT = runpy.run_path(str(HERE/'stream-client.py'))


def main(a):
    prior = json.loads(a.boot_result.read_text())
    if prior.get('result') != 'passed' or prior.get('stage') != 'ubuntu_network_ssh':
        raise RuntimeError('qualified Ubuntu boot required')
    bootdir = Path(prior['run_directory'])
    r = LAB['RunRecorder']('ustreamer-hil', a.out_root)
    r.save_text('runner.py', Path(__file__).read_text())
    for name in ('ustreamer-hil.py','stream-client.py','hdmi-off.py'):
        data=(HERE/name).read_bytes()
        r.save_text('source-'+name,data.decode())
        r.metadata.setdefault('automation_sha256',{})['lab/'+name]=hashlib.sha256(data).hexdigest()
    meta = json.loads((bootdir/'metadata.json').read_text())
    r.metadata.update(artifacts=meta['artifacts'], build_source=meta['build_source'], boot_run=prior['run_id'])
    ssh = ['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes',
           '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(bootdir/'known_hosts'),
           '-o','ConnectTimeout=10','blikvm@192.168.88.2']
    result = dict(result='failed', stage='preflight', boot_run=prior['run_id'])
    source = None
    off_process = None
    monitor = G4['G1']['HostMonitor'](r)
    source_logs = []
    uart_stop=threading.Event()
    uart_thread=None
    uart_errors=[]
    def collect_uart():
        try:
            with LAB['SerialConsole'](Path('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'),r) as console:
                r.save_text('uart-monitor.log','Passive UART capture active; no target commands sent.\n')
                while not uart_stop.is_set(): console.read_for(.2)
        except Exception as error:
            uart_errors.append(str(error))
    def target(name, command, timeout=30, check=True):
        p = subprocess.run(ssh+['sudo -n /bin/bash -c '+shlex.quote('set -e; '+command)],
                           capture_output=True,text=True,timeout=timeout)
        r.save_text(name+'.log',p.stdout+p.stderr)
        if check and p.returncode:
            raise RuntimeError(name+': '+p.stdout[-1500:]+p.stderr[-1500:])
        return p.stdout.strip()
    def host(name, cmd):
        return G4['command'](r,name,cmd).stdout
    def start_source(label):
        nonlocal source
        host('source-dpms-on-'+label,['modetest','-M','i915','-w',f'{connector}:DPMS:0'])
        log=(r.path/('source-'+label+'.log')).open('w'); source_logs.append(log)
        argv=['gst-launch-1.0','-q','videotestsrc','is-live=true','pattern=ball','animation-mode=frames',
              '!','video/x-raw,width=1920,height=1080,framerate=30/1','!','videoconvert','!',
              'kmssink',f'connector-id={connector}','force-modesetting=true','restore-crtc=true']
        r.save_text('source-command-'+label+'.json',json.dumps(argv))
        source=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT)
        time.sleep(3)
        if source.poll() is not None:
            raise RuntimeError('moving HDMI source failed')
        host('hdmi-active-'+label,['modetest','-M','i915','-p'])
    def stop_source():
        nonlocal source
        if source is not None:
            source.terminate()
            try: source.wait(timeout=10)
            except subprocess.TimeoutExpired:
                source.kill(); source.wait()
            source=None
    def stream(label, seconds):
        command=ssh+['sudo -n curl --silent --show-error --no-buffer --include --max-time '+str(seconds+10)+
                     ' --unix-socket /run/kvmd/ustreamer/ustreamer.sock http://localhost/stream']
        value=CLIENT['qualify'](command,seconds,r.path/label)
        if value['result']!='passed':
            raise RuntimeError(label+': '+str(value))
        return value
    def pid(label):
        return target(label,'systemctl show ustreamer -p MainPID --value')
    try:
        identity=target('identity','cat /proc/sys/kernel/random/boot_id; uname -a; cat /etc/blikvm-build; dpkg-query -W ustreamer; /usr/bin/ustreamer --version; sha256sum /usr/bin/ustreamer')
        if identity.splitlines()[0] not in (bootdir/'identity.log').read_text().splitlines():
            raise RuntimeError('boot identity mismatch')
        result['boot_id']=identity.splitlines()[0]
        uart_thread=threading.Thread(target=collect_uart,daemon=True)
        uart_thread.start()
        connector=int(Path('/sys/class/drm/card0-HDMI-A-2/connector_id').read_text())
        connectors=host('hdmi-before',['modetest','-M','i915','-c'])
        connector_section=connectors.split(f'{connector}\t',1)[1]
        dpms_property=int(re.search(r'\n\s*(\d+) DPMS:',connector_section)[1])
        host('vt-source',['chvt','3'])
        target('video-identity','readlink -f /dev/kvmd-video; udevadm info -q property -n /dev/kvmd-video; v4l2-ctl -d /dev/kvmd-video --all; v4l2-ctl -d /dev/kvmd-video --list-formats-ext')
        props=target('video-properties','udevadm info -q property -n /dev/kvmd-video')
        for expected in ('ID_VENDOR_ID=345f','ID_MODEL_ID=2131','ID_SERIAL_SHORT=29404080','ID_V4L_CAPABILITIES=:capture:'):
            if expected not in props.splitlines(): raise RuntimeError('wrong capture identity: '+expected)
        target('video-permissions', 'runuser -u ustreamer -- v4l2-ctl -d /dev/kvmd-video --all; for node in /dev/video*; do if [ "$node" != "$(readlink -f /dev/kvmd-video)" ]; then ! runuser -u ustreamer -- test -r "$node"; fi; done')
        target('auto-service','systemctl is-active ustreamer; systemctl is-enabled ustreamer; systemctl status ustreamer --no-pager; systemctl cat ustreamer; id ustreamer; test "$(systemctl show ustreamer -p User --value)" = ustreamer')
        monitor.start()
        start_source('initial')
        result['stage']='sustained_stream'
        mode=target('negotiated-before','v4l2-ctl -d /dev/kvmd-video --get-fmt-video --get-parm')
        if not all(value in mode for value in ('1920/1080', "'MJPG'", '30.000')):
            raise RuntimeError('device did not negotiate MJPEG 1920x1080 at 30 fps')
        usage_command='for n in $(seq 1 '+str(int(a.seconds)+5)+'); do date -u +%FT%TZ; ps -p "$(systemctl show ustreamer -p MainPID --value)" -o pid,ppid,user,etimes,time,pcpu,rss,vsz; systemctl show ustreamer -p CPUUsageNSec -p MemoryCurrent -p TasksCurrent; sleep 1; done'
        with (r.path/'resources.log').open('w') as log:
            usage=subprocess.Popen(ssh+['sudo -n /bin/bash -c '+shlex.quote(usage_command)],stdout=log,stderr=log)
            try:
                result['sustained']=stream('sustained',a.seconds)
                if result['sustained']['frames'] < a.seconds*27:
                    raise RuntimeError('sustained delivery below 90 percent of requested 30 fps')
            finally:
                usage.terminate(); usage.wait(timeout=5)
        target('negotiated-after','v4l2-ctl -d /dev/kvmd-video --get-fmt-video --get-parm; curl -sS --unix-socket /run/kvmd/ustreamer/ustreamer.sock http://localhost/state')
        result['stage']='service_lifecycle'
        result['restarts']=[]
        for i in range(3):
            old=pid(f'pid-before-stop-{i}')
            target(f'stop-{i}','systemctl stop ustreamer; for exe in /proc/[0-9]*/exe; do if [ "$(readlink "$exe")" = /usr/bin/ustreamer ]; then exit 1; fi; done; test ! -e /run/kvmd/ustreamer/ustreamer.sock')
            target(f'start-{i}','systemctl start ustreamer; systemctl is-active ustreamer')
            result['restarts'].append(stream(f'start-stream-{i}',10))
            target(f'restart-{i}','systemctl restart ustreamer; systemctl is-active ustreamer')
            if pid(f'pid-after-restart-{i}') == old: raise RuntimeError('restart retained old PID')
            result['restarts'].append(stream(f'restart-stream-{i}',10))
        result['stage']='signal_loss'
        result['signal_cycles']=[]
        for i in range(3):
            before=pid(f'signal-pid-before-{i}')
            stop_source()
            off_log=(r.path/f'hdmi-off-{i}.log').open('w'); source_logs.append(off_log)
            off_process=subprocess.Popen([sys.executable,str(HERE/'hdmi-off.py'),'--connector',str(connector),
                                          '--property',str(dpms_property)],stdout=off_log,stderr=off_log)
            time.sleep(2)
            if off_process.poll() is not None: raise RuntimeError('HDMI off holder failed')
            off=host(f'hdmi-off-state-{i}',['modetest','-M','i915','-c'])
            section=off.split(f'{connector}\t',1)[1]
            if 'value: 3' not in section.split('5 link-status',1)[0]:
                raise RuntimeError('HDMI DPMS off not verified')
            # Frozen/absent video is expected during intentional no-signal, retained verbatim.
            command=ssh+['sudo -n curl -sS -N -i --max-time 15 --unix-socket /run/kvmd/ustreamer/ustreamer.sock http://localhost/stream']
            loss=CLIENT['qualify'](command,10,r.path/f'no-signal-{i}')
            target(f'no-signal-state-{i}','v4l2-ctl -d /dev/kvmd-video --all; curl -sS --unix-socket /run/kvmd/ustreamer/ustreamer.sock http://localhost/state')
            off_process.terminate(); off_process.wait(timeout=5); off_process=None
            start_source(f'recovery-{i}')
            recovery=stream(f'recovery-{i}',15)
            after=pid(f'signal-pid-after-{i}')
            if before != after: raise RuntimeError('signal recovery restarted uStreamer')
            result['signal_cycles'].append(dict(loss=loss,recovery=recovery,pid=before,automatic=True))
        result['stage']='m5_regression'
        target('hardware','ip -br addr; ping -c 5 -W 2 192.168.88.1; lsusb; lsusb -t; ls -l /sys/class/udc; test "$(cat /sys/bus/usb/devices/1-1/serial)" = 29404080; test "$(cat /sys/bus/usb/devices/1-1/speed)" = 480; gadget-storage setup; hid-keyboard bind')
        d=G4['wait_device'](True,20)
        G4['exact_descriptors'](d,r,'ustreamer')
        G4['G1']['host_logs'](r,'ustreamer')
        state=target('gadget-state','gadget-storage state; '+G4['mapping_command'](True))
        if not G4['valid_functions'](state): raise RuntimeError('gadget function mismatch')
        result['storage']=G4['storage_test'](d,r,'ustreamer')
        with G4['Capture'](d,r,0) as keyboard, G4['Capture'](d,r,1) as absolute, G4['Capture'](d,r,2) as relative:
            G4['mouse_caps'](absolute.fd); G4['relative_caps'](relative.fd)
            target('neutral','hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep .2')
            for capture in (keyboard,absolute,relative): capture.neutral()
            stopped=threading.Event()
            with ThreadPoolExecutor(max_workers=2) as pool:
                video=pool.submit(stream,'concurrent-gadget-stream',15)
                storage=pool.submit(G4['storage_during_uvc'],d,r,stopped)
                try:
                    target('hid-reports',G4['G1']['modifier_command']()+' && '+G4['mouse_command']()+' && '+G4['relative_command']())
                    result['concurrent_stream']=video.result()
                finally: stopped.set()
                result['concurrent_storage']=storage.result()
            target('release','hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep .2')
            result['hid']={name:cap.verify(name) for name,cap in [('keyboard',keyboard),('absolute',absolute),('relative',relative)]}
        target('final-service','systemctl status ustreamer --no-pager; systemctl --failed --no-pager; test "$(systemctl --failed --no-legend --plain | wc -l)" -eq 0; pid=$(systemctl show ustreamer -p MainPID --value); test "$pid" -gt 0; test "$(readlink /proc/$pid/exe)" = /usr/bin/ustreamer; count=0; for exe in /proc/[0-9]*/exe; do if [ "$(readlink "$exe")" = /usr/bin/ustreamer ]; then count=$((count+1)); fi; done; test "$count" = 1; test "$(cat /sys/fs/cgroup$(systemctl show ustreamer -p ControlGroup --value)/cgroup.procs)" = "$pid"')
        dmesg=target('dmesg','dmesg')
        journal=target('journal','journalctl -b -u ustreamer --no-pager')
        monitor.stop()
        hostlog=(r.path/'host-kernel-live.log').read_text()
        errors=G4['G1']['usb_errors'](dmesg)+G4['G1']['usb_errors'](hostlog)+G4['unexpected_resets'](hostlog)
        if errors: raise RuntimeError('USB errors: '+str(errors))
        result.update(result='passed',stage='ustreamer_qualification',usb_errors=[])
    except Exception as error:
        result['error']=str(error)
    finally:
        for name,command in [('final-dmesg','dmesg'),('final-journal','journalctl -b -u ustreamer --no-pager'),('final-state','systemctl status ustreamer --no-pager; ls -l /dev/kvmd-video')]:
            try: target(name,command,check=False)
            except Exception as error: r.save_text(name+'-error.log',str(error))
        monitor.stop(); stop_source()
        if off_process is not None:
            off_process.terminate(); off_process.wait(timeout=5)
        if 'connector' in locals():
            try:
                host('hdmi-restore',['modetest','-M','i915','-w',f'{connector}:DPMS:0'])
                host('vt-restore',['chvt','1'])
            except Exception as error: result['cleanup_error']=str(error); result['result']='failed'
        for log in source_logs: log.close()
        uart_stop.set()
        if uart_thread is not None: uart_thread.join(timeout=3)
        if uart_errors:
            result['uart_errors']=uart_errors
            result['result']='failed'
    print(json.dumps(r.finish(result)),flush=True)
    return result['result']=='passed'


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--boot-result',type=Path,required=True)
    p.add_argument('--out-root',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=120)
    a=p.parse_args()
    if a.seconds<30: p.error('sustained interval must be at least 30 seconds')
    raise SystemExit(0 if main(a) else 1)
