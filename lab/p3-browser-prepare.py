#!/usr/bin/env python3
"""Install an isolated bridge browser context; never contacts the target."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

BASE = Path('/var/lib/blikvm-p3-browser')
SOURCE = Path('/home/user/blikvm-msd/p3-context')
USER = 'p3-browser'

def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def prepare():
    assert os.geteuid() == 0
    assert not BASE.exists(), 'context must be fresh'
    try:
        pwd.getpwnam(USER)
    except KeyError:
        subprocess.run(['useradd','--system','--user-group','--home-dir',str(BASE/'home'),
                        '--shell','/usr/sbin/nologin',USER],check=True)
    user = pwd.getpwnam(USER)
    assert os.getgrouplist(USER,user.pw_gid) == [user.pw_gid], 'unexpected supplemental groups'
    os.umask(0o077)
    BASE.mkdir(mode=0o755); BASE.chmod(0o755)
    home=Path('/home/user'); old_mode=home.stat().st_mode & 0o777
    # Search only for the dependency tree; no directory listing or write grant.
    home.chmod(old_mode | 0o001)
    (BASE/'home').mkdir(mode=0o700); os.chown(BASE/'home',user.pw_uid,user.pw_gid)
    (BASE/'private').mkdir(mode=0o750)
    os.chown(BASE/'private',0,user.pw_gid); (BASE/'private').chmod(0o750)
    private_before={str(p):digest(p) for p in (SOURCE/'private').iterdir() if p.is_file()}
    for name in ('credentials.json','ca.crt','server.crt'):
        dest=BASE/'private'/name
        shutil.copyfile(SOURCE/'private'/name,dest)
        os.chown(dest,0,user.pw_gid); dest.chmod(0o640)
        assert digest(dest)==private_before[str(SOURCE/'private'/name)]
    shutil.copytree(SOURCE/'lab',BASE/'lab')
    for name in ('build','initramfs'):
        (BASE/name).symlink_to((SOURCE/name).resolve())
    (BASE/'out').mkdir(mode=0o755); (BASE/'out').chmod(0o755)
    (BASE/'out/kvmd-web').mkdir(mode=0o755); (BASE/'out/kvmd-web').chmod(0o755)
    (BASE/'out/kvmd-web/browser').symlink_to((SOURCE/'out/kvmd-web/browser').resolve())
    expected={'msd-browser-hil.py':'9fca0e0ba0abbfa27aedc4584d80abbe2b28cdf4bdbaf116ee0b618359336046',
              'hid-browser-hil.py':'0946ce8bc41903176863d6b06784f0bb6c3f915c3c84ea9ea2262c1950cfae8a'}
    changes={}
    for name,sha in expected.items():
        path=BASE/'lab'/name
        assert digest(path)==sha, name+' source drift'
        text=path.read_text()
        if name.startswith('msd'):
            old='    os.chmod(a.output,0o777)'
            new="    runpy.run_path(str(Path(__file__).with_name('p3-browser-permissions.py')))['inventory'](a.output)"
            assert text.count(old)==1
            text=text.replace(old,new)
            old="temp=stage.with_suffix('.ok.tmp');temp.write_text(json.dumps(check));temp.rename(stage.with_suffix('.ok'))"
            new="temp=stage.with_suffix('.ok.tmp');temp.write_text(json.dumps(check));temp.chmod(0o644);temp.rename(stage.with_suffix('.ok'))"
            assert text.count(old)==1
            text=text.replace(old,new)
        else:
            text=text.replace("pwd.getpwnam('user')", "pwd.getpwnam('p3-browser')")
            old="  browser=subprocess.Popen("
            assert text.count(old)==1
            text=text.replace(old,"  runpy.run_path(str(Path(__file__).with_name('p3-browser-permissions.py')))['inventory'](a.output)\n"+old)
            old="   stem.with_suffix('.ok.tmp').rename(stem.with_suffix('.ok'))"
            assert text.count(old)==1
            text=text.replace(old,"   stem.with_suffix('.ok.tmp').chmod(0o644)\n"+old)
            old="   stem.with_suffix('.go').write_text('go')"
            assert text.count(old)==1
            text=text.replace(old,old+";stem.with_suffix('.go').chmod(0o644)")
        old="['runuser','-u','user','--'"
        assert text.count(old)==1
        text=text.replace(old,"['runuser','-u','p3-browser','--'")
        path.write_text(text)
        changes[name]={'before':sha,'after':digest(path)}
    helper=Path(__file__).with_name('p3-browser-permissions.py')
    shutil.copyfile(helper,BASE/'lab'/helper.name)
    (BASE/'lab'/helper.name).chmod(0o644)
    # Initialize fresh NSS trust with only the enrolled public CA, no private keys.
    dest=BASE/'home/.pki/nssdb'
    dest.mkdir(parents=True,mode=0o700)
    for p in (dest.parent,dest):
        os.chown(p,user.pw_uid,user.pw_gid); p.chmod(0o700)
    subprocess.run(['runuser','-u',USER,'--','certutil','-N','-d','sql:'+str(dest),'--empty-password'],check=True)
    subprocess.run(['runuser','-u',USER,'--','certutil','-A','-d','sql:'+str(dest),
                    '-n','BliKVM enrolled CA','-t','C,,','-i',str(BASE/'private/ca.crt')],check=True)
    assert private_before=={str(p):digest(p) for p in (SOURCE/'private').iterdir() if p.is_file()}
    result={'scope':'bridge-only browser permission handling', 'target_contacted':False,
            'uid':user.pw_uid,'gid':user.pw_gid,'home_search_mode_before':oct(old_mode),
            'home_search_mode_after':oct(home.stat().st_mode&0o777),'source_changes':changes,
            'original_private_hashes':private_before}
    (BASE/'installation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='original_private_hashes'}))

if __name__=='__main__':
    prepare()
