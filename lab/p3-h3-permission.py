#!/usr/bin/env python3
"""Three H3 permission-only transitions. No Chromium and no target contact."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

H=runpy.run_path(str(Path(__file__).with_name('p3-h3-boundary.py')))
BASE=H['BASE'];require=H['require'];publish=H['publish']


def new_leaf(name):
    require(not list((BASE/'active').iterdir()),'previous active output not sealed')
    p=BASE/'active'/name;p.mkdir(mode=0o700);os.chown(p,995,983);return p


def main():
    require(os.geteuid()==0,'root required');os.umask(0o077);H['browser_idle']()
    require(not (BASE/'controller/FAILED.json').exists(),'failed H3 latch; no retry')
    config=H['read_json'](BASE/'controller/config.json')
    r={'scope':'P3-H3 permission-only','qualification_credit':0,'accepted_cycles':0,
       'target_contacted':False,'chromium_launched':False,'reboots':0,'transitions':[]}
    try:
        for i in range(1,4):
            name=f'perm-{i:03d}';leaf=new_leaf(name)
            config['cross_run'] += [str(p) for p in (BASE/'sealed').iterdir() if str(p) not in config['cross_run']]
            H['audit'](leaf,BASE/'controller'/(name+'-before-audit.json'),config)
            # Deliberately retain a browser-owned 0777 descendant. Future auditing
            # must block the entire sealed ancestor without relying on its name.
            code="from pathlib import Path; import os,sys; p=Path(sys.argv[1]); q=p/'unknown-0777';q.mkdir();q.chmod(0o777); f=q/'fixture';f.write_bytes(b'harmless fixture'); fd=os.open(f,os.O_RDONLY);os.fsync(fd);os.close(fd)"
            subprocess.run(['runuser','-u','p3-browser','--',sys.executable,'-c',code,str(leaf)],check=True)
            sealed=H['seal'](leaf)
            config['cross_run'].append(str(BASE/'sealed'/name/'unknown-0777'))
            H['audit'](None,BASE/'controller'/(name+'-after-audit.json'),config)
            r['transitions'].append(sealed)
        r['result']='PERMISSION_ONLY_PASS_PENDING_INDEPENDENT_REPLAY'
    except BaseException as e:
        r.update(result='FAILED',error=repr(e));publish(BASE/'controller/FAILED.json',r)
        raise
    finally:
        publish(BASE/'controller/permission-result.json',r)
    print(json.dumps({'result':r['result'],'transitions':len(r['transitions']),'qualification_credit':0}),flush=True)


if __name__=='__main__':main()
