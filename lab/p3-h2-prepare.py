#!/usr/bin/env python3
"""Generate H2 bridge context from the frozen P3 smoke, changing only I/O paths.

Run only on the bridge as root. Historical scripts and the old context remain
unchanged. No browser launch, target connection or lifecycle operation here.
"""
import hashlib
import os
from pathlib import Path
import runpy
import shutil
import sys

B = runpy.run_path(str(Path(__file__).with_name('p3-h2-boundary.py')))
SOURCE = Path('/home/user/blikvm-msd/p3-context')
BASE = Path('/var/lib/blikvm-p3-h2')
OLD = Path('/var/lib/blikvm-p3-browser')
PINS = {'msd-browser-hil.py': '9fca0e0ba0abbfa27aedc4584d80abbe2b28cdf4bdbaf116ee0b618359336046',
        'hid-browser-hil.py': '0946ce8bc41903176863d6b06784f0bb6c3f915c3c84ea9ea2262c1950cfae8a'}


def replace(text, old, new, count=1):
    B['require'](text.count(old) == count, 'patch context drift: '+old)
    return text.replace(old, new)


def transform(name, text):
    if name.startswith('hid'):
        text = replace(text, 'a.output.mkdir(parents=True,exist_ok=False)', 'a.output.mkdir(parents=True,exist_ok=True)')
    setup = "P3=runpy.run_path(str(Path(__file__).with_name('p3-h2-boundary.py')))\nLEAF=Path(os.environ['P3_BROWSER_LEAF'])\n"
    text = replace(text, 'import time\n', 'import time\n'+setup)
    text = replace(text, "['runuser','-u','user','--'", "['runuser','-u','p3-browser','--'")
    text = replace(text, "'p3-browser','--','env',", "'p3-browser','--','env','HOME='+str(LEAF/'runtime-home'),'P3_CONTROL='+str(a.output),")
    text = replace(text, 'str(a.output.resolve())', 'str(LEAF)')
    text = replace(text, "json.loads((a.output/'browser-result.json').read_text())", "P3['read_json'](LEAF/'browser-result.json')")
    if name.startswith('msd'):
        text = replace(text, '    os.chmod(a.output,0o777)\n', '')
        text = replace(text, "a.output.glob('*.ready')", "LEAF.glob('[0-9][0-9][0-9].ready')")
        text = replace(text, 'json.loads(stage.read_text())', "P3['read_json'](stage)")
        text = replace(text, "temp=stage.with_suffix('.ok.tmp');temp.write_text(json.dumps(check));temp.rename(stage.with_suffix('.ok'))",
                       "P3['publish'](a.output/stage.with_suffix('.ok').name,check,0o644)")
    else:
        text = replace(text, "user=pwd.getpwnam('user');os.chown(a.output,user.pw_uid,user.pw_gid)\n", '')
        text = replace(text, "ready=stem.with_suffix('.ready')", "ready=LEAF/(stem.name+'.ready')")
        text = replace(text, 'json.loads(ready.read_text())', "P3['read_json'](ready)")
        text = replace(text, "stem.with_suffix('.go').write_text('go')", "P3['publish'](stem.with_suffix('.go'),'go',0o644)")
        text = replace(text, "stem.with_suffix('.done').exists()", "(LEAF/(stem.name+'.done')).exists()")
        text = replace(text, "json.loads(stem.with_suffix('.done').read_text())", "P3['read_json'](LEAF/(stem.name+'.done'))")
        text = replace(text, "stem.with_suffix('.ok.tmp').write_text(json.dumps({'result':check['result'],'error':check.get('error')}))\n   stem.with_suffix('.ok.tmp').rename(stem.with_suffix('.ok'))",
                       "P3['publish'](stem.with_suffix('.ok'),{'result':check['result'],'error':check.get('error')},0o644)")
    return text


def transform_js(text, hid):
    # Only acknowledgement reads move to the controller-owned namespace.
    for suffix in (['go','ok'] if hid else ['ok']):
        text = text.replace("stem+'."+suffix+"'", "path.join(process.env.P3_CONTROL,path.basename(stem))+'."+suffix+"'")
    return text


def prepare():
    B['require'](os.geteuid() == 0, 'root controller required')
    B['browser_idle']()
    os.umask(0o022)
    BASE.mkdir(mode=0o755)
    shutil.copytree(SOURCE/'lab', BASE/'lab')
    for n in ('build','initramfs'):
        (BASE/n).symlink_to((SOURCE/n).resolve(strict=True))
    (BASE/'out').mkdir()
    (BASE/'out/kvmd-web').mkdir()
    (BASE/'out/kvmd-web/browser').symlink_to((OLD/'out/kvmd-web/browser').resolve(strict=True))
    (BASE/'private').symlink_to(OLD/'private')
    changes = {}
    for name, pin in PINS.items():
        p = BASE/'lab'/name
        B['require'](hashlib.sha256(p.read_bytes()).hexdigest() == pin, 'frozen P3 source drift')
        original = p.read_text()
        p.write_text(transform(name, original))
        changes[name] = dict(before=pin, after=hashlib.sha256(p.read_bytes()).hexdigest())
    p = BASE/'lab/msd-hil.py'
    original = p.read_bytes()
    p.write_text(replace(original.decode(), 'output.mkdir(parents=True,exist_ok=False)', 'output.mkdir(parents=True,exist_ok=True)'))
    changes[p.name] = dict(before=hashlib.sha256(original).hexdigest(), after=hashlib.sha256(p.read_bytes()).hexdigest())
    for name in ('msd-browser.mjs','hid-browser.mjs'):
        p = BASE/'lab'/name
        original = p.read_bytes()
        p.write_text(transform_js(original.decode(), name.startswith('hid')))
        changes[name] = dict(before=hashlib.sha256(original).hexdigest(),
                             after=hashlib.sha256(p.read_bytes()).hexdigest())
    shutil.copyfile(Path(__file__).with_name('p3-h2-boundary.py'), BASE/'lab/p3-h2-boundary.py')
    (BASE/'attempt').mkdir(mode=0o755)
    for n in ('controller', 'archives'):
        (BASE/'attempt'/n).mkdir(mode=0o700)
    B['publish'](BASE/'installation.json', dict(scope='bridge_only', changes=changes))
    print('H2 context prepared; browser and target not contacted')


if __name__ == '__main__':
    prepare()
