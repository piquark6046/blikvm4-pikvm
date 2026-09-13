#!/usr/bin/env python3
"""Freeze whole legacy roots, quarantine by ancestor, create clean H3 inputs.

Bridge root only. No target contact and no Chromium. Existing archive bytes
and descendant ownership/modes are preserved. No historical-leaf migration.
"""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tarfile

H=runpy.run_path(str(Path(__file__).with_name('p3-h3-boundary.py')))
require,publish,digest=H['require'],H['publish'],H['digest']
BASE,LEGACY=H['BASE'],H['LEGACY']
ROOTS=[Path('/home/user/blikvm-p3'),Path('/home/user/blikvm-msd/p3-context'),
       Path('/var/lib/blikvm-p3-browser'),Path('/var/lib/blikvm-p3-h2')]
PINS={'a01-evidence.tar.gz':'dde56c3bf3ab1d14006c601c8c8a05343c353b11c385f9b8a33755837ed5e57a',
      'a02-preflight01-evidence.tar.gz':'c528cd34d02e0a939edd4bbb7dfec7be6e7ff5dc83854472604154e4bfea0f6f',
      'a02-preflight02-evidence.tar.gz':'be15a52352e74b222e219a0ead96f10aa523eefc26d4f4bbe266afa4fad0d644',
      'h2-failed-evidence.tar.gz':'1bb8f7076d86de563381e2736169698589c03f728f5d09c6fac148943b42b332'}


def mkdir(p,mode=0o700):
    p.mkdir(mode=mode);p.chmod(mode)


def prepare():
    require(os.geteuid()==0,'root required');H['browser_idle']();os.umask(0o077)
    require(not BASE.exists() and not LEGACY.exists(),'namespace already exists; no retry')
    # Verify frozen immutable archives before touching any legacy metadata.
    for name,sha in PINS.items():
        require(digest(ROOTS[0]/name)==sha,'historical archive hash mismatch: '+name)
        with tarfile.open(ROOTS[0]/name) as t:
            for m in t:
                if m.isfile():
                    with t.extractfile(m) as f:
                        while f.read(1024*1024):pass
    mkdir(BASE,0o755)
    for n,mode in [('controller',0o700),('input',0o755),('active',0o711),('sealed',0o700)]:mkdir(BASE/n,mode)
    publish(BASE/'controller/canary',{'protected':'controller'})
    publish(BASE/'input/canary',{'protected':'input'},0o644)
    publish(BASE/'controller/existing-archives.json',PINS)
    records=[]
    for i,root in enumerate(ROOTS):
        records.append(H['archive'](root,BASE/'controller'/f'legacy-{i:02d}.tar.gz',
                                  BASE/'controller'/f'legacy-{i:02d}-metadata.json',legacy=True))
    # Freeze a complete metadata manifest before creating the quarantine boundary.
    publish(BASE/'controller/legacy-freeze.json',{'roots':[str(p) for p in ROOTS],'records':records})
    mkdir(LEGACY)
    for root in ROOTS:
        require(root.stat().st_dev==LEGACY.stat().st_dev,'cross-filesystem quarantine would not be a rename')
        os.rename(root,LEGACY/root.name)
        for parent in (root.parent,LEGACY):
            fd=H['trusted_dir'](parent);os.fsync(fd);os.close(fd)
    # No old-path aliases: the old paths cease to exist. All legacy access is
    # controller-only through the one root-owned 0700 ancestor.
    publish(BASE/'controller/quarantine.json',{'legacy':str(LEGACY),'metadata':H['no_acl'](LEGACY),
            'mapping':{str(p):str(LEGACY/p.name) for p in ROOTS},'descendant_chmod_chown':False})
    ctx=BASE/'input/context';mkdir(ctx,0o755)
    source=LEGACY/'p3-context'
    shutil.copytree(source/'lab',ctx/'lab')
    for n in ('build','initramfs'):
        shutil.copytree((source/n).resolve(strict=True),ctx/n,symlinks=False)
    mkdir(ctx/'out',0o755);mkdir(ctx/'out/kvmd-web',0o755)
    shutil.copytree(Path('/home/user/blikvm-msd/out/kvmd-web/browser').resolve(strict=True),
                    ctx/'out/kvmd-web/browser',symlinks=False)
    shutil.copytree(LEGACY/'blikvm-p3-browser/private',ctx/'private')
    shutil.copytree(LEGACY/'blikvm-p3-browser/home/.pki/nssdb',BASE/'input/nssdb')
    # Source transformation is built on the VM and applied to pinned P3 inputs.
    T=runpy.run_path(str(Path(__file__).with_name('p3-h2-prepare.py')))
    changes={}
    for name,pin in T['PINS'].items():
        p=ctx/'lab'/name;require(digest(p)==pin,'P3 source drift')
        text=T['transform'](name,p.read_text())
        text=text.replace("'P3_CONTROL='+str(a.output)","'P3_CONTROL='+os.environ['P3_CONTROL']")
        text=text.replace("P3['publish'](a.output/stage.with_suffix('.ok').name", "P3['publish'](Path(os.environ['P3_CONTROL'])/stage.with_suffix('.ok').name")
        text=text.replace("P3['publish'](stem.with_suffix('.go')", "P3['publish'](Path(os.environ['P3_CONTROL'])/stem.with_suffix('.go').name")
        text=text.replace("P3['publish'](stem.with_suffix('.ok')", "P3['publish'](Path(os.environ['P3_CONTROL'])/stem.with_suffix('.ok').name")
        p.write_text(text);changes[name]={'before':pin,'after':digest(p)}
    p=ctx/'lab/msd-hil.py';p.write_text(T['replace'](p.read_text(),'output.mkdir(parents=True,exist_ok=False)','output.mkdir(parents=True,exist_ok=True)'))
    for name in ('msd-browser.mjs','hid-browser.mjs'):
        p=ctx/'lab'/name;old=digest(p)
        p.write_text(T['transform_js'](p.read_text(),name.startswith('hid')))
        changes[name]={'before':old,'after':digest(p)}
    require('kvmd-restart-cleanup' not in (ctx/'lab/hid-browser.mjs').read_text(),'non-P3 HID smoke includes restart')
    shutil.copyfile(Path(__file__).with_name('p3-h2-boundary.py'),ctx/'lab/p3-h2-boundary.py')
    # These are fresh input copies, not historical evidence descendants.
    for p in [ctx,BASE/'input/nssdb',*ctx.rglob('*'),*(BASE/'input/nssdb').rglob('*')]:
        require(not p.is_symlink(),'copy contains a symlink')
        os.chown(p,0,0);p.chmod(0o755 if p.is_dir() else (0o755 if p.stat().st_mode&0o111 else 0o644))
    for p in [ctx/'private',*(ctx/'private').iterdir()]:
        os.chown(p,0,983);p.chmod(0o750 if p.is_dir() else 0o640)
    mkdir(BASE/'input/acks',0o755)
    # Keep private/controller-only transport separate from browser inputs.
    prep=BASE/'controller/preparation'
    shutil.copytree(LEGACY/'blikvm-p3/preparation',prep,ignore=shutil.ignore_patterns('__pycache__'))
    p=prep/'collect.py'
    p.write_text(p.read_text().replace('/home/user/blikvm-p3/preparation',str(prep)))
    config={'legacy':str(LEGACY),'reads':[str(ctx/'private/ca.crt'),str(ctx/'private/credentials.json'),
            str(ctx/'lab/msd-browser.mjs'),str(ctx/'lab/hid-browser.mjs'),str(BASE/'input/canary')],
            'protected_roots':[str(Path('/home/user/blikvm-msd/private').resolve(strict=True)),
              '/home/user/.local/share/blikvm-m7','/home/user/blikvm-msd/lab',
              '/home/user/blikvm-msd/build','/home/user/blikvm-msd/initramfs'],
            'protected_files':['/home/user/.local/share/blikvm-m7/id_ed25519'],
            'cross_run':[str(LEGACY/'p3-context/a01-smoke/browser-msd')]}
    publish(BASE/'controller/config.json',config)
    publish(BASE/'controller/installation.json',{'scope':'P3-H3 bridge only','changes':changes,
            'target_contacted':False,'reboots':0,'qualification_credit':0,
            'input_manifest':H['manifest'](BASE/'input')})
    print('H3 prepared, legacy roots quarantined; target and Chromium not contacted',flush=True)


if __name__=='__main__':prepare()
