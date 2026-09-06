"""G4: frozen G3 HID tests plus one strictly identified disposable RO LUN."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import json
import os
import mmap
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time
import threading

G3 = runpy.run_path(str(Path(__file__).with_name('relativelab.py')))
# Reuse accepted HID report generators, descriptors, event verifiers unchanged.
for _name in ('G1', 'read', 'exact_descriptors', 'Capture', 'mouse_caps', 'relative_caps',
              'IDENTITY_KEYS', 'parse_mapping', 'concurrent_setup_commands',
              'concurrent_command', 'mouse_command', 'relative_command'):
    globals()[_name] = G3[_name]
IMAGE = runpy.run_path(str(Path(__file__).resolve().parents[1]/'build/make-storage-image.py'))
EXPECTED = IMAGE['manifest']()

def details(device):
    record = G3['details'](device)
    expected = [('03','01','01','usbhid'), ('03','00','00','usbhid'),
                ('03','00','00','usbhid'), ('08','06','50','usb-storage')]
    actual = [(p['class'],p['subclass'],p['protocol'],p['driver']) for p in record['interfaces']]
    record['passed'] = record['speed'] == '480' and actual == expected
    return record

def wait_device(present, timeout):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        device = G1['keyboard_device']()
        if not present and device is None:
            return None
        if present and device is not None and details(device)['passed']:
            return device
        time.sleep(.1)
    raise TimeoutError('G4 composite did not '+('enumerate' if present else 'disconnect'))

def mapping_command(bound):
    return G3['mapping_command'](bound).replace(
        'ls "$g/functions" | sort', 'ls "$g/functions" | grep \'^hid\\.\' | sort')

def valid_functions(output):
    groups = re.findall(r'functions_begin\s+(.*?)\s+functions_end', output.replace('\r',''), re.S)
    return bool(groups) and all(set(s.split()) ==
        {'hid.keyboard','hid.absolute','hid.relative','mass_storage.g4'} for s in groups)

def command(recorder, name, argv, check=True):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=25)
    recorder.save_text(name+'.log', json.dumps({'argv': argv, 'returncode': p.returncode,
                        'stdout': p.stdout, 'stderr': p.stderr}, indent=2))
    if check and p.returncode:
        raise RuntimeError(name+': '+p.stderr)
    return p

def block_identity(device, timeout=15):
    deadline = time.monotonic()+timeout
    interface = (device.parent/(device.name+':1.3')).resolve()
    while time.monotonic()<deadline:
        nodes = [p for p in Path('/sys/class/block').iterdir()
                 if interface in p.resolve().parents]
        if len(nodes)==1:
            p = nodes[0]
            if (p/'partition').exists():
                raise RuntimeError('unexpected partition')
            scsi = (p/'device').resolve()
            sg = list((scsi/'scsi_generic').glob('sg*'))
            if len(sg)==1 and Path('/dev/'+p.name).exists():
                attrs = {a:read(p/a) for a in ('dev','ro','size','queue/logical_block_size')}
                attrs.update({a: read(scsi/a) for a in ('vendor','model','rev','type')})
                if (attrs['ro'],attrs['size'],attrs['queue/logical_block_size'],attrs['type']) != ('1','16384','512','0'):
                    time.sleep(.1)
                    continue
                if (attrs['vendor'],attrs['model'],attrs['rev']) != ('BliKVM','G4 RAM RO','0001'):
                    raise RuntimeError('unexpected SCSI inquiry identity: '+str(attrs))
                if (scsi/'driver').resolve().name != 'sd':
                    raise RuntimeError('SCSI disk driver missing')
                return dict(attrs,node='/dev/'+p.name,sysfs=str(p.resolve()),
                            scsi=str(scsi),sg='/dev/'+sg[0].name,usb=str(device.resolve()),
                            interface=str(interface))
        elif len(nodes)>1:
            raise RuntimeError('expected exactly one whole-disk LUN, no partitions')
        time.sleep(.1)
    raise RuntimeError('missing single SCSI disk/sg binding')

def assert_absent(identity, recorder, suffix):
    for key in ('node','sysfs','sg','scsi'):
        if Path(identity[key]).exists():
            raise RuntimeError('stale storage object: '+identity[key])
    mounts = Path('/proc/self/mountinfo').read_text()
    if any(line.split()[2] == identity['dev'] for line in mounts.splitlines()):
        raise RuntimeError('stale storage mount')
    recorder.save_text('storage-absent-'+suffix+'.json',json.dumps({'passed':True,'identity':identity,'mountinfo':mounts},indent=2))

def read_image_direct(node):
    # Bypass the host page cache: every qualification hash reads USB media.
    fd=os.open(node, os.O_RDONLY | os.O_DIRECT)
    try:
        with mmap.mmap(-1, EXPECTED['size']+512) as buf:
            count=os.readv(fd,[buf])
            return buf[:count]
    finally:
        os.close(fd)


def storage_test(device, recorder, suffix):
    identity = block_identity(device)
    prefix = 'storage-'+suffix
    result = {'identity':identity, 'expected':EXPECTED}
    def save():
        recorder.save_text(prefix+'.json',json.dumps(result,indent=2))
    def digest():
        # Re-resolve the USB/SCSI topology immediately before each block access.
        if block_identity(device) != identity:
            raise RuntimeError('storage identity changed')
        data = read_image_direct(identity['node'])
        if len(data)!=EXPECTED['size'] or hashlib.sha256(data).hexdigest()!=EXPECTED['sha256']:
            raise RuntimeError('full host image size/hash mismatch')
        return hashlib.sha256(data).hexdigest()
    mountpoint = recorder.path/(prefix+'-mount')
    mounted=False
    try:
        command(recorder,prefix+'-lsblk',['lsblk','--json','-b','-O',identity['node']])
        command(recorder,prefix+'-udev',['udevadm','info','--query=property','--path='+identity['sysfs']])
        command(recorder,prefix+'-scsi',['sg_inq',identity['sg']])
        command(recorder,prefix+'-capacity',['sg_readcap',identity['sg']])
        fs = command(recorder,prefix+'-blkid',['blkid','-p','-o','export',identity['node']]).stdout
        props=dict(line.split('=',1) for line in fs.splitlines() if '=' in line)
        if any(props.get(k)!=v for k,v in {'TYPE':'vfat','UUID':'4734-0001','LABEL':'BLIKVM_G4','VERSION':'FAT16'}.items()) or any(k.startswith('PTTYPE') for k in props):
            raise RuntimeError('filesystem identity mismatch')
        result['filesystem']=props
        result['image_sha256_before']=digest()
        mountpoint.mkdir()
        command(recorder,prefix+'-mount',['mount','-t','vfat','-o','ro,nosuid,nodev,noexec',identity['node'],str(mountpoint)])
        mounted=True
        mounts=Path('/proc/self/mountinfo').read_text()
        recorder.save_text(prefix+'-mountinfo.log',mounts)
        entries=[l.split() for l in mounts.splitlines() if l.split()[4]==str(mountpoint)]
        if len(entries)!=1 or 'ro' not in entries[0][5].split(',') or entries[0][2]!=identity['dev']:
            raise RuntimeError('mount not read-only or wrong source')
        files={p.name.upper():p for p in mountpoint.iterdir()}
        if set(files)!=set(EXPECTED['files']):
            raise RuntimeError('unexpected filesystem directory contents')
        result['files']={}
        for name, p in files.items():
            data=p.read_bytes()
            if data!=IMAGE['FILES'][name]:
                raise RuntimeError('file contents mismatch')
            result['files'][name]={'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        try:
            with (mountpoint/'REJECT.TXT').open('xb') as stream:
                stream.write(b'G4 must reject this write\n')
        except OSError as error:
            result['filesystem_write']={'errno':error.errno,'error':str(error),'rejected':error.errno==errno.EROFS}
        else:
            raise RuntimeError('filesystem write unexpectedly succeeded')
        if not result['filesystem_write']['rejected'] or (mountpoint/'REJECT.TXT').exists():
            raise RuntimeError('filesystem write not rejected with EROFS')
        command(recorder,prefix+'-umount',['umount',str(mountpoint)])
        mounted=False
        # This is deliberately the final unused sector of this exact expendable image.
        # SCSI pass-through exercises device write protection even though sd is RO.
        payload=recorder.path/(prefix+'-rejected-write.bin')
        payload.write_bytes(b'G4 REJECTED WRITE\n'.ljust(512,b'!'))
        if block_identity(device)!=identity:
            raise RuntimeError('identity changed before attempted SCSI WRITE')
        p=command(recorder,prefix+'-scsi-write',['sg_raw','--send=512','--infile='+str(payload),
                   identity['sg'],'2a','00','00','00','3f','ff','00','00','01','00'],False)
        result['scsi_write']={'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
        if p.returncode==0 or 'data protect' not in (p.stdout+p.stderr).lower() or 'write protected' not in (p.stdout+p.stderr).lower():
            raise RuntimeError('SCSI WRITE did not return DATA PROTECT / WRITE PROTECTED')
        result['image_sha256_after']=digest()
        result['passed']=True
        return result
    finally:
        try:
            if os.path.ismount(mountpoint):
                command(recorder,prefix+'-cleanup-umount',['umount',str(mountpoint)])
            if mountpoint.exists():
                mountpoint.rmdir()
        finally:
            save()


def storage_during_uvc(device, recorder, stopped):
    record = {'expected': EXPECTED, 'identity': block_identity(device),
              'mode': 'direct whole-image reads; mount and write tests run sequentially'}
    reads=[]
    while not stopped.is_set():
        identity=block_identity(device)
        started=time.time()
        data=read_image_direct(identity['node'])
        digest=hashlib.sha256(data).hexdigest()
        if len(data)!=EXPECTED['size'] or digest!=EXPECTED['sha256']:
            raise RuntimeError('concurrent whole-image read/hash failed')
        reads.append({'started':started,'finished':time.time(),'sha256':digest})
        stopped.wait(.1)
    if not reads:
        raise RuntimeError('no storage read loop during retained UVC test')
    record['continuous_reads']=reads
    record['passed']=True
    recorder.save_text('storage-concurrent-loop.json',json.dumps(record,indent=2))
    return record


def unexpected_resets(text):
    return [line for line in text.splitlines()
            if re.search(r'usb [0-9]+-[0-9.]+: reset .*USB device', line, re.I)]


def run_hid_test(console, recorder, args, run_uvc_test, capture):
    result = {'result': 'failed', 'slice': 'G4', 'failed_stage': 'setup', 'error': 'incomplete'}
    stage = 'setup'
    monitor = G1['HostMonitor'](recorder)

    def target(name, command):
        rc, output = capture(console, recorder, name + '.log', name.replace('-', '_'), command, 20)
        if rc:
            raise RuntimeError(name + ': target rc=' + str(rc))
        return output

    def state(suffix, bound):
        output = target('g4-state-' + suffix, 'gadget-storage state')
        required = ('absolute_subclass=0', 'absolute_protocol=0', 'absolute_report_length=5',
                    'absolute_no_out_endpoint=1', 'relative_subclass=0', 'relative_protocol=0',
                    'relative_report_length=3', 'relative_no_out_endpoint=1')
        if any(s not in output.replace('\r', '') for s in required) or not valid_functions(output):
            raise RuntimeError('unexpected target function state')
        if any(x not in output.replace('\r','').splitlines() for x in ('lun=lun.0', 'lun_ro=1', 'lun_cdrom=0', 'lun_removable=0', 'lun_nofua=0', 'lun_file=/usr/share/g4-storage.img')):
            raise RuntimeError('unexpected LUN attributes')
        if output.replace('\r','').splitlines().count('lun=lun.0') != 1 or len(re.findall(r'^lun=lun\.', output.replace('\r',''), re.M)) != 1:
            raise RuntimeError('expected exactly one LUN')
        if EXPECTED['sha256']+'  /usr/share/g4-storage.img' not in output:
            raise RuntimeError('target backing image hash changed')
        mapping = target('g4-mapping-' + suffix, mapping_command(bound))
        parsed = parse_mapping(mapping, bound)
        previous = result.setdefault('function_mapping', parsed if bound else None)
        if bound and previous != parsed:
            raise RuntimeError('function-to-hidg mapping changed')
        if bound and 'state=configured' not in output:
            raise RuntimeError('UDC not configured')
        return {'passed': True, 'bound': bound, 'mapping': parsed, 'backing_sha256': EXPECTED['sha256']}

    baseline = None
    def snapshot(suffix):
        nonlocal baseline
        device = wait_device(True, 15)
        record = details(device)
        stable = (record['identity'], record['usb_descriptors_sha256'])
        if baseline is not None and stable != baseline:
            raise RuntimeError('USB identity or descriptors changed')
        baseline = stable
        record['storage_identity'] = block_identity(device)
        record['reports'] = exact_descriptors(device, recorder, suffix)
        with Capture(device, recorder, 1) as mouse:
            record['mouse_identity'] = mouse.identity
            record['capabilities'] = mouse_caps(mouse.fd)
        with Capture(device, recorder, 2) as relative:
            record['relative_identity'] = relative.identity
            record['relative_capabilities'] = relative_caps(relative.fd)
        record['keyboard_identity'] = Capture(device, recorder, 0).identity
        identities = [record[k] for k in ('keyboard_identity', 'mouse_identity', 'relative_identity')]
        stable_inputs = [{k: v for k, v in i.items() if k not in ('node', 'sysfs')} for i in identities]
        if 'input_identity_baseline' in result and stable_inputs != result['input_identity_baseline']:
            raise RuntimeError('evdev identity/capabilities changed')
        result['input_identity_baseline'] = stable_inputs
        recorder.save_text('host-g4-' + suffix + '.json', json.dumps(record, indent=2))
        (recorder.path / ('host-usb-' + suffix + '.bin')).write_bytes((device / 'descriptors').read_bytes())
        G1['host_logs'](recorder, suffix)
        return device, record

    def functional(device, suffix, concurrent=False):
        with Capture(device, recorder, 0) as keyboard, Capture(device, recorder, 1) as mouse, Capture(device, recorder, 2) as relative:
            # All three devices are grabbed before *any* reports, including cleanup.
            target('g4-prime-' + suffix, 'hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep 0.2')
            keyboard.neutral()
            mouse.neutral()
            relative.neutral()
            try:
                if concurrent:
                    for name, command in concurrent_setup_commands():
                        target('g4-script-' + name, command)
                    stopped = threading.Event()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(storage_during_uvc, device, recorder, stopped)
                        try:
                            result['uvc'] = run_uvc_test(console, recorder, concurrent_hid=True,
                                hid_report_command=concurrent_command())
                        finally:
                            stopped.set()
                        result.setdefault('storage', {})[suffix] = future.result()
                else:
                    result.setdefault('storage', {})[suffix] = storage_test(device, recorder, suffix)
                    target('g4-reports-' + suffix, G1['modifier_command']() + ' && ' + mouse_command() + ' && ' + relative_command())
            finally:
                target('g4-release-' + suffix, 'hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep 0.2')
            record = {'keyboard': keyboard.verify(suffix + '-keyboard'),
                      'absolute_mouse': mouse.verify(suffix + '-mouse'),
                      'relative_mouse': relative.verify(suffix + '-relative')}
            if concurrent and (result['uvc']['result'] != 'passed' or
                    int(result['uvc']['capture_summary']['startup_error_frames']) != 0):
                raise RuntimeError('concurrent UVC failed or contained startup errors')
            return record

    try:
        monitor.start()
        G1['host_logs'](recorder, 'before')
        target('g4-quiet', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
        target('udc-before', 'hid-keyboard state')
        target('g4-setup', 'gadget-storage setup')
        target('g4-bind', 'hid-keyboard bind')
        stage = 'initial_enumeration_and_input'
        device, result['enumeration'] = snapshot('initial')
        state('initial', True)
        result['initial_input'] = functional(device, 'initial')
        stage = 'unbind_rebind'
        old_number = read(device / 'devnum')
        old_inputs = [result['enumeration'][k]['sysfs'] for k in IDENTITY_KEYS]
        target('g4-unbind', 'hid-keyboard unbind')
        wait_device(False, 10)
        if any(Path(p).exists() for p in old_inputs):
            raise RuntimeError('old HID input survived software unbind')
        assert_absent(result['enumeration']['storage_identity'], recorder, 'unbound')
        state('unbound', False)
        target('g4-rebind', 'hid-keyboard bind')
        device, record = snapshot('rebound')
        if read(device / 'devnum') == old_number:
            raise RuntimeError('device number unchanged after rebind')
        state('rebound', True)
        result['unbind_rebind'] = {'passed': True, 'before': old_number, 'after': read(device / 'devnum'),
                                  'enumeration': record, 'input': functional(device, 'rebound')}
        stage = 'physical_reconnect'
        if args.reconnect_evidence:
            prior = json.loads(args.reconnect_evidence.read_text())
            if prior.get('hid', {}).get('slice') != 'G4':
                raise RuntimeError('physical evidence is not G4')
            result['physical_reconnect'] = G1['prior_reconnect'](args.reconnect_evidence, recorder.metadata['artifacts'])
        else:
            old_number = read(device / 'devnum')
            old_inputs = [record[k]['sysfs'] for k in IDENTITY_KEYS]
            print(f'G4_RECONNECT_READY run={recorder.run_id}; unplug USB-PC only, wait 2 seconds, reconnect',
                  file=sys.stderr, flush=True)
            wait_device(False, args.reconnect_timeout)
            disconnected_at = time.time()
            recorder.save_text('host-disconnected.json', json.dumps({
                'time': disconnected_at, 'device_absent': G1['keyboard_device']() is None,
                'old_inputs_absent': [not Path(p).exists() for p in old_inputs]}))
            if any(Path(p).exists() for p in old_inputs):
                raise RuntimeError('old HID sysfs survived disconnect')
            assert_absent(record['storage_identity'], recorder, 'physical')
            device = wait_device(True, args.reconnect_timeout)
            if time.time()-disconnected_at < 2:
                raise RuntimeError('physical disconnect shorter than two seconds')
            number = read(device / 'devnum')
            time.sleep(3)
            if read(device / 'devnum') != number or not details(device)['passed']:
                raise RuntimeError('unstable physical re-enumeration')
            if read(device / 'devnum') == old_number:
                raise RuntimeError('device number unchanged after physical reconnect')
            result['physical_reconnect'] = {'passed': True, 'repeated_this_boot': True,
                'disconnected_at': disconnected_at, 'reconnected_at': time.time(),
                'before': old_number, 'after': read(device / 'devnum'), 'old_input_removed': True, 'old_storage_removed': True}
        device, result['reconnected_enumeration'] = snapshot('reconnected')
        state('reconnected', True)
        stage = 'reconnected_input'
        result['reconnected_input'] = functional(device, 'reconnected')
        stage = 'concurrent_uvc'
        result['concurrent_input'] = functional(device, 'concurrent', concurrent=True)
        # UVC restores console verbosity; suppress it again for marker transactions.
        target('g4-quiet-after-uvc', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
        result['final_state'] = state('final', True)
        _, result['final_enumeration'] = snapshot('final')
        stage = 'usb_errors'
        dmesg = target('g4-dmesg-after', 'dmesg')
        monitor.stop()
        errors = G1['usb_errors'](dmesg) + G1['usb_errors'](read(recorder.path / 'host-kernel-live.log'))
        errors += [line for line in read(recorder.path / 'host-kernel-live.log').splitlines()
                   if re.search(r'(?:scsi|sd |usb-storage).*(?:I/O error|timed out|reset|abort|offline)', line, re.I)
                   and 'Power-on or device reset occurred' not in line]
        errors += unexpected_resets(read(recorder.path / 'host-kernel-live.log'))
        result['usb_errors'] = {'passed': not errors, 'matching_lines': errors}
        if errors:
            raise RuntimeError('USB errors: ' + str(errors))
        result.update(result='passed', failed_stage=None, error=None)
    except Exception as error:
        result.update(result='failed', failed_stage=stage, error=str(error))
    finally:
        monitor.stop()
        try:
            target('g4-final-collection', 'dmesg; gadget-storage state')
            G1['host_logs'](recorder, 'after')
            target('g4-console-restore', 'dmesg -n 8; echo Y > /sys/module/printk/parameters/ignore_loglevel')
        except Exception as error:
            result['collection_error'] = str(error)
            if result['result'] == 'passed':
                result.update(result='failed', failed_stage='collect', error=str(error))
    return result
