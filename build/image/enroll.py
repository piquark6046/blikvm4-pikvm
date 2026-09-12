#!/usr/bin/env python3
"""Apply only approved offline enrollment to an exact validated public image."""
import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import assemble as A


def enroll(base, inputs, destination):
    if os.geteuid() != 0:
        raise ValueError('root required for read-only validation')
    os.umask(0o077)
    base = base.resolve(); inputs = inputs.resolve(); dest = destination.resolve()
    assert dest.is_relative_to(A.REPO/'out/p1/private') and not dest.exists()
    A.regular(base/'blikvm-v4-pikvm.img')
    manifest = json.loads((base/'manifest.json').read_text())
    lock = A.check_inputs()
    assert manifest['acceptance_commit'] == lock['acceptance_commit']
    assert manifest['qualified_candidate'] == lock['qualified_candidate']
    assert A.digest(base/'blikvm-v4-pikvm.img') == manifest['image_sha256']
    assert A.digest(base/'filesystem-manifest.json') == manifest['rootfs_inventory_sha256']
    assert json.loads((base/'validation.json').read_text())['result'] == 'passed'
    source = json.loads((inputs/'provenance.json').read_text())
    assert set(source['files']) == set(A.ENROLL)
    for name in A.ENROLL:
        p = inputs/name; A.regular(p)
        assert p.stat().st_size > 0 and A.digest(p) == source['files'][name]['sha256']
    # Ensure credentials are syntactically usable, without printing them.
    cert = inputs/'etc/kvmd/nginx/ssl/server.crt'; key = inputs/'etc/kvmd/nginx/ssl/server.key'
    pub_cert = A.run(['openssl','x509','-in',cert,'-pubkey','-noout']).stdout
    pub_key = A.run(['openssl','pkey','-in',key,'-pubout']).stdout
    assert pub_cert == pub_key
    A.run(['openssl','x509','-in',cert,'-noout','-checkhost','blikvm-v4.lab'])
    A.run(['openssl','x509','-in',cert,'-noout','-checkip','192.168.88.2'])
    A.run(['openssl','x509','-in',cert,'-noout','-checkend','86400'])
    A.run(['ssh-keygen','-l','-f',inputs/'home/blikvm/.ssh/authorized_keys'])
    # Preserve the accepted salted SHA-512 htpasswd encoding.
    auth_lines = (inputs/'etc/kvmd/htpasswd').read_bytes().splitlines()
    assert auth_lines
    for line in auth_lines:
        fields = line.split(b':')
        assert len(fields) == 2 and fields[0] and fields[1].startswith(b'{SSHA512}')
        assert len(base64.b64decode(fields[1][9:], validate=True)) == 80
    dest.mkdir(parents=True, mode=0o700); work=dest/'work'; work.mkdir(mode=0o700)
    image=dest/'blikvm-v4-pikvm-enrolled.img'
    # Copy the exact base, then change only the partition through a regular file.
    with (base/'blikvm-v4-pikvm.img').open('rb') as f, image.open('xb') as out:
        shutil.copyfileobj(f,out,1024**2)
    fs=work/'root.ext4'
    with image.open('rb') as f, fs.open('xb') as out:
        f.seek(A.OFFSET);shutil.copyfileobj(f,out,1024**2)
    expected=json.loads((base/'filesystem-manifest.json').read_text())
    old=copy.deepcopy(expected)
    directory='etc/kvmd/nginx/ssl'
    assert directory not in expected
    commands=[f'mkdir /{directory}']
    expected[directory]={'mode':0o755,'uid':0,'gid':0,'mtime':A.EPOCH,'type':stat.S_IFDIR}
    changed=[directory]
    for name,(mode,uid,gid) in A.ENROLL.items():
        if name in expected:
            commands.append(f'rm /{name}')
        path=inputs/name
        assert '"' not in str(path) and '\n' not in str(path)
        commands.append(f'write "{path}" /{name}')
        expected[name]={'mode':mode,'uid':uid,'gid':gid,'mtime':A.EPOCH,'type':stat.S_IFREG,
                        'nlink':1,'size':path.stat().st_size,'sha256':A.digest(path)}
        changed.append(name)
    for name in changed:
        item=expected[name]
        for field,value in [('mode',item['type']|item['mode']),('uid',item['uid']),('gid',item['gid']),('generation',0)]:
            commands.append(f'set_inode_field /{name} {field} {value}')
        for field in ['mtime','atime','ctime','crtime']:
            commands.append(f'set_inode_field /{name} {field} @{A.EPOCH}')
            commands.append(f'set_inode_field /{name} {field}_extra 0')
    batch=work/'enroll.debugfs';batch.write_text('\n'.join(commands)+'\n')
    result=A.run(['debugfs','-w','-f',batch,fs]);(work/'enroll.log').write_bytes(result.stdout+result.stderr)
    assert not result.stderr.decode().splitlines()[1:]
    with image.open('r+b') as out, fs.open('rb') as f:
        out.seek(A.OFFSET);shutil.copyfileobj(f,out,1024**2);out.flush();os.fsync(out.fileno())
    vendor=json.loads((base/'bootloader-layout.json').read_text())
    validation=A.validate(image,work,expected,lock,vendor,enrolled=True)
    actual_changes=sorted(n for n in set(old)|set(expected) if old.get(n)!=expected.get(n))
    assert actual_changes == sorted(changed)
    assert A.digest(base/'blikvm-v4-pikvm.img') == manifest['image_sha256']
    A.save(dest/'filesystem-manifest.json',expected)
    A.save(dest/'validation.json',validation)
    A.save(dest/'enrollment-receipt.json',{'result':'passed','base_image_sha256':manifest['image_sha256'],
           'enrolled_image_sha256':A.digest(image),'source_provenance':source,
           'transform_sha256':A.digest(Path(__file__)),'approved_files':list(A.ENROLL),
           'necessary_directory':directory,'exact_filesystem_changes':actual_changes,
           'all_other_files_and_metadata_identical':True,'base_unchanged':True,
           'private_artifact':True,'physical_sd_written':False,'standalone_boot':'NOT_TESTED'})
    (dest/'SHA256SUMS').write_text(f'{A.digest(image)}  {image.name}\n')
    print(json.dumps({'result':'passed','private_output':str(dest),'changed_files':len(A.ENROLL),
                      'new_parent_directories':1,'receipt_sha256':A.digest(dest/'enrollment-receipt.json')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();enroll(a.base,a.inputs,a.output)
