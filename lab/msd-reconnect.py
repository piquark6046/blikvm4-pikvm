#!/usr/bin/env python3
"""Physical cable qualification; no software unbind, rebind, rescan or repair."""
import argparse,json,subprocess,sys,time,runpy
from pathlib import Path
M=runpy.run_path(str(Path(__file__).with_name('msd-hil.py')))
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-result',type=Path,required=True);a=p.parse_args()
h=M['Harness'](a.output,a.boot_result)
result={'result':'failed','manual_target_repair':False};monitor=M['H']['G1']['HostMonitor'](h.rec);targetmon=None
try:
    initial_inventory=h.target('before-inventory',Path('lab/msd-inventory.py').read_text())
    h.state('before-reconnect',True);h.media('before-reconnect')
    before=M['H']['G4']['exact_descriptors'](h.device,h.rec,'before')
    usb=M['H']['usb_descriptors'](h.device,h.rec,'before')
    hid_nodes=[p for root in ('/sys/class/input','/sys/class/hidraw') for p in Path(root).iterdir() if h.device.resolve() in p.resolve().parents]
    assert len([p for p in hid_nodes if p.name.startswith('event')])==3
    hid_dev=[Path('/dev/input')/p.name if p.name.startswith('event') else Path('/dev')/p.name for p in hid_nodes if p.name.startswith(('event','hidraw'))]
    result['hid_nodes_before']=[str(p) for p in hid_nodes+hid_dev]
    monitor.start()
    targetmon=subprocess.Popen(h.ssh+['sudo -n journalctl -kf --no-pager'],stdout=(a.output/'target-live.log').open('w'),stderr=(a.output/'target-live.stderr').open('w'))
    time.sleep(.5)
    (a.output/'ready.json').write_text(json.dumps({'ready':True,'connected':True,'identity':h.identity}))
    print('READY TO RECONNECT USB-PC',flush=True)
    M['H']['G4']['wait_device'](False,900)
    absent_paths=hid_nodes+hid_dev+[Path(h.identity[k]) for k in ('node','sysfs','sg','scsi')]
    deadline=time.monotonic()+5
    while any(p.exists() for p in absent_paths) and time.monotonic()<deadline:time.sleep(.05)
    M['H']['G4']['assert_absent'](h.identity,h.rec,'physical')
    assert not any(p.exists() for p in hid_nodes+hid_dev),'stale HID host object'
    h.rec.save_text('disconnected.json',json.dumps({'observed':True,'hid_objects_absent':True,'time':time.time()}))
    h.device=M['H']['G4']['wait_device'](True,900)
    h.identity=M['H']['G4']['block_identity'](h.device)
    after=M['H']['G4']['exact_descriptors'](h.device,h.rec,'after')
    assert before==after
    assert M['H']['usb_descriptors'](h.device,h.rec,'after')==usb
    result.update(before_descriptors=before,after_descriptors=after,usb_sha256=usb,identity_after=h.identity)
    h.state('physical-return',True);h.media('physical-return')
    for name,argv in [
        ('hid-api',[sys.executable,'lab/hid-api-hil.py','--private-dir','private','--output',str(a.output/'hid-api')]),
        ('msd-browser',[sys.executable,'lab/msd-browser-hil.py','--output',str(a.output/'msd-browser'),'--boot-result',str(a.boot_result)]),
        ('hid-browser',[sys.executable,'lab/hid-browser-hil.py','--output',str(a.output/'hid-browser'),'--boot-result',str(a.boot_result)])]:
        with (a.output/(name+'.log')).open('w') as log:p=subprocess.run(argv,stdout=log,stderr=log,timeout=700)
        assert p.returncode==0,name
    h.client.login();h.state('after-all-reconnect-checks',True);h.media('after-all-reconnect-checks')
    final_inventory=h.target('after-inventory',Path('lab/msd-inventory.py').read_text())
    assert initial_inventory['boot_id']==final_inventory['boot_id'] and initial_inventory['hid_mapping']==final_inventory['hid_mapping']
    result['result']='passed'
except Exception as ex:result['error']=str(ex)
finally:
    if targetmon:targetmon.terminate();targetmon.wait(timeout=10)
    monitor.stop();result['transitions']=h.result['transitions']
    h.rec.save_text('result.json',json.dumps(result,indent=2)+'\n')
print(json.dumps(result));raise SystemExit(result['result']!='passed')
